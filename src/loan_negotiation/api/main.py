import asyncio
import json
from collections.abc import AsyncIterator

import logging

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from loan_negotiation.api.schemas import NegotiateRequest, PartyTermsIn
from loan_negotiation.config import get_settings, settings_with_model
from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms
from loan_negotiation.models.workflow import WorkflowResult, WorkflowStatus
from loan_negotiation.services.contract_pdf import (
    ContractExtractionError,
    extract_text_from_pdf,
)
from loan_negotiation.services.gpu_runtime import gpu_visible
from loan_negotiation.services.results_store import (
    append_interaction,
    ensure_results_json,
    results_json_path,
)
from loan_negotiation.services.model_catalog import (
    api_credentials_configured,
    catalog_with_availability,
    default_comparison_model,
)
from loan_negotiation.services.ollama_check import (
    OllamaModelNotFoundError,
    ensure_model_ready,
    list_ollama_models,
)
from loan_negotiation.services.opening_offer import (
    OpeningOfferExtractionError,
    extract_opening_offer_with_local_llama,
    format_opening_offer_announcement,
)
from loan_negotiation.workflow.orchestrator import run_negotiation
from loan_negotiation.workflow.personas import demo_persona, get_persona, list_personas

logger = logging.getLogger(__name__)

app = FastAPI(title="Loan Negotiation API", version="0.1.0")


@app.on_event("startup")
def _ensure_interaction_log() -> None:
    path = ensure_results_json()
    logger.info("Interaction log ready at %s", path)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _to_party_terms(data: PartyTermsIn, model: type[BorrowerTerms | LenderTerms]):
    return model.model_validate(data.model_dump())

@app.get("/api/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "model": settings.model,
        "ollama_num_gpu": settings.resolved_ollama_num_gpu(),
        "gpu_visible": gpu_visible(),
    }


@app.get("/api/demo")
def demo_terms() -> dict:
    """Back-compat alias for the Demo persona."""
    return demo_persona().to_api_dict()


@app.get("/api/personas")
def personas_index() -> dict:
    return {"personas": list_personas()}


@app.get("/api/personas/{persona_id}")
def persona_terms(persona_id: str) -> dict:
    try:
        return get_persona(persona_id).to_api_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown persona: {persona_id}") from exc


@app.get("/api/models")
def list_models() -> dict:
    """Curated comparison catalog + availability (API key and/or Ollama)."""
    settings = get_settings()
    installed: list[str] = []
    ollama_error: str | None = None
    try:
        installed = list_ollama_models(settings.ollama_base_url)
    except Exception as exc:  # noqa: BLE001
        ollama_error = str(exc)

    catalog = catalog_with_availability(installed)
    if not any(row["available"] for row in catalog) and ollama_error and not settings.resolved_api_key():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Cannot reach Ollama at {settings.ollama_base_url}: {ollama_error}. "
                "Set GOOGLE_API_KEY / MISTRAL_API_KEY, or start Ollama for the local model."
            ),
        )

    default = default_comparison_model(installed, settings.model)
    for row in catalog:
        if row["resolved_name"] == default or row["id"] == default or row.get("model_id") == default:
            if row["available"]:
                default = row["resolved_name"]
            break

    return {
        "default": default,
        "catalog": catalog,
        "installed": installed,
        "ollama_base_url": settings.ollama_base_url,
        "api_configured": api_credentials_configured(),
        "keys": {
            "google": bool(settings.google_api_key),
            "mistral": bool(settings.mistral_api_key),
        },
    }


async def _negotiate_stream(
    borrower: BorrowerTerms,
    lender: LenderTerms,
    *,
    llm_model: str | None,
    contract_text: str | None,
    persona_id: str | None = None,
    persona_name: str | None = None,
    attempt: int | None = None,
) -> StreamingResponse:
    settings = settings_with_model(llm_model)
    model_label = llm_model or settings.model

    async def event_stream() -> AsyncIterator[str]:
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        def on_message(stage: str, agent: str, output: str) -> None:
            queue.put_nowait(
                {
                    "type": "event",
                    "stage": stage,
                    "agent": agent,
                    "output": output,
                }
            )

        async def run_workflow() -> None:
            try:
                ensure_model_ready(settings)
                workflow = await run_negotiation(
                    borrower,
                    lender,
                    settings=settings,
                    on_message=on_message,
                    contract_text=contract_text,
                    llm_model=llm_model,
                    persona_id=persona_id,
                    persona_name=persona_name,
                    attempt=attempt,
                    save_interaction=True,
                )
                log_meta = {
                    "interaction_log_path": str(results_json_path()),
                }
                payload = {
                    "type": "complete",
                    "result": workflow.result.to_api_dict(),
                    **log_meta,
                }
                await queue.put(payload)
            except OllamaModelNotFoundError as exc:
                try:
                    append_interaction(
                        WorkflowResult(status=WorkflowStatus.NO_DEAL, reasons=[str(exc)]),
                        model_id=model_label,
                        persona_id=persona_id,
                        persona_name=persona_name,
                        attempt=attempt,
                        error=str(exc),
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to append %s", results_json_path())
                await queue.put({"type": "error", "message": str(exc)})
            except Exception as exc:
                message = f"Negotiation failed: {exc}"
                try:
                    append_interaction(
                        WorkflowResult(status=WorkflowStatus.NO_DEAL, reasons=[message]),
                        model_id=model_label,
                        persona_id=persona_id,
                        persona_name=persona_name,
                        attempt=attempt,
                        error=message,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to append %s", results_json_path())
                await queue.put({"type": "error", "message": message})
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_workflow())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/negotiate")
async def negotiate(request: NegotiateRequest) -> StreamingResponse:
    borrower = _to_party_terms(request.borrower, BorrowerTerms)
    lender = _to_party_terms(request.lender, LenderTerms)
    return await _negotiate_stream(
        borrower,
        lender,
        llm_model=request.llm_model,
        contract_text=request.contract_text,
        persona_id=request.persona_id,
        persona_name=request.persona_name,
        attempt=request.attempt,
    )


@app.post("/api/preview-opening-offer")
async def preview_opening_offer(file: UploadFile = File(...)) -> dict:
    """Extract a structured lender opening offer from a PDF using local Llama 3.2."""
    filename = (file.filename or "").lower()
    if filename and not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        contract_text = extract_text_from_pdf(data)
    except ContractExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        offer = await extract_opening_offer_with_local_llama(contract_text)
    except OllamaModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OpeningOfferExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Local Llama could not preview this offer: {exc}",
        ) from exc

    return {
        "model": "ollama-local",
        "filename": file.filename,
        "announcement": format_opening_offer_announcement(offer),
        "deal": offer.model_dump(),
    }


@app.post("/api/negotiate-with-pdf")
async def negotiate_with_pdf(
    borrower: str = Form(...),
    lender: str = Form(...),
    llm_model: str | None = Form(None),
    persona_id: str | None = Form(None),
    persona_name: str | None = Form(None),
    attempt: int | None = Form(None),
    file: UploadFile = File(...),
) -> StreamingResponse:
    """Start negotiation with a lender PDF; local Llama 3.2 reads the offer in-workflow."""
    filename = (file.filename or "").lower()
    if filename and not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    try:
        borrower_terms = _to_party_terms(PartyTermsIn.model_validate_json(borrower), BorrowerTerms)
        lender_terms = _to_party_terms(PartyTermsIn.model_validate_json(lender), LenderTerms)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid terms payload: {exc}") from exc

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        contract_text = extract_text_from_pdf(data)
    except ContractExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return await _negotiate_stream(
        borrower_terms,
        lender_terms,
        llm_model=llm_model,
        contract_text=contract_text,
        persona_id=persona_id,
        persona_name=persona_name,
        attempt=attempt,
    )


def main() -> None:
    import uvicorn

    uvicorn.run(
        "loan_negotiation.api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
