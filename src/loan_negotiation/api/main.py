import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from loan_negotiation.api.schemas import (
    BorrowerTermsIn,
    DealTermsIn,
    LenderTermsIn,
    NegotiateRequest,
)
from loan_negotiation.api.serialize import workflow_run_to_dict
from loan_negotiation.config import get_settings, settings_with_model
from loan_negotiation.models.loan_terms import BorrowerTerms, DealTerms, LenderTerms
from loan_negotiation.services.contract_pdf import (
    ContractExtractionError,
    extract_opening_offer_from_pdf,
)
from loan_negotiation.services.gpu_runtime import gpu_visible
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
from loan_negotiation.workflow.orchestrator import run_negotiation
from loan_negotiation.workflow.samples import sample_borrower, sample_lender

app = FastAPI(title="Loan Negotiation API", version="0.1.0")

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


def _to_borrower_terms(data: BorrowerTermsIn) -> BorrowerTerms:
    return BorrowerTerms.model_validate(data.model_dump())


def _to_lender_terms(data: LenderTermsIn) -> LenderTerms:
    return LenderTerms.model_validate(data.model_dump())


def _to_deal_terms(data: DealTermsIn | None) -> DealTerms | None:
    if data is None:
        return None
    return DealTerms.model_validate(data.model_dump()).model_copy(
        update={"consensus_reached": False}
    )


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
    borrower = sample_borrower()
    lender = sample_lender()
    return {
        "borrower": borrower.model_dump(),
        "lender": lender.model_dump(),
    }


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
        # API-only setups can still list free API models without Ollama.

    catalog = catalog_with_availability(installed)
    if not any(row["available"] for row in catalog) and ollama_error and not settings.resolved_api_key():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Cannot reach Ollama at {settings.ollama_base_url}: {ollama_error}. "
                "Set GOOGLE_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY, or start Ollama for the local model."
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
            "groq": bool(settings.groq_api_key),
            "openrouter": bool(settings.openrouter_api_key),
        },
    }


@app.post("/api/parse-offer-pdf")
async def parse_offer_pdf(file: UploadFile = File(...)) -> dict:
    """Extract a lender opening offer from an uploaded PDF contract."""
    filename = (file.filename or "").lower()
    if filename and not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        offer, text = await extract_opening_offer_from_pdf(data, use_llm=True)
    except ContractExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OllamaModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract offer from PDF: {exc}",
        ) from exc

    preview = text if len(text) <= 1500 else text[:1500] + "…"
    return {
        "opening_offer": offer.model_dump(),
        "source_filename": file.filename,
        "text_preview": preview,
    }


@app.post("/api/negotiate")
async def negotiate(request: NegotiateRequest) -> StreamingResponse:
    borrower = _to_borrower_terms(request.borrower)
    lender = _to_lender_terms(request.lender)
    opening_offer = _to_deal_terms(request.opening_offer)
    settings = settings_with_model(request.llm_model)

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
                    opening_offer=opening_offer,
                    llm_model=request.llm_model,
                )
                await queue.put(
                    {
                        "type": "complete",
                        "result": workflow_run_to_dict(workflow),
                    }
                )
            except OllamaModelNotFoundError as exc:
                await queue.put({"type": "error", "message": str(exc)})
            except Exception as exc:
                await queue.put({"type": "error", "message": f"Negotiation failed: {exc}"})
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
