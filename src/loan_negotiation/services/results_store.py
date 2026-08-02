"""Persist negotiation outcomes to results/interactions.json.

Path is always <repo>/results/interactions.json next to pyproject.toml / src/.
Override with env INTERACTIONS_JSON if needed.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from loan_negotiation.models.workflow import WorkflowResult

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_JSON = _REPO_ROOT / "results" / "interactions.json"


def results_json_path() -> Path:
    override = os.environ.get("INTERACTIONS_JSON", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _DEFAULT_JSON.resolve()


def _empty_store() -> dict:
    return {"interactions": []}


def _read_store(path: Path) -> dict:
    if not path.exists():
        return _empty_store()
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.warning("Could not read %s (%s) — starting fresh", path, exc)
        return _empty_store()
    if not raw:
        return _empty_store()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Corrupt %s — starting fresh", path)
        return _empty_store()
    if isinstance(data, list):
        return {"interactions": data}
    if isinstance(data, dict):
        rows = data.get("interactions")
        if not isinstance(rows, list):
            data["interactions"] = []
        return data
    return _empty_store()


def _write_store(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2) + "\n"
    # Replace file so editors pick up a new inode and permissions stay readable.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, 0o644)
    tmp.replace(path)


def ensure_results_json(path: Path | None = None) -> Path:
    target = path or results_json_path()
    if not target.exists() or not target.read_text(encoding="utf-8").strip():
        _write_store(target, _empty_store())
    return target


def build_record(
    result: WorkflowResult,
    *,
    model_id: str,
    persona_id: str | None = None,
    persona_name: str | None = None,
    attempt: int | None = None,
    error: str | None = None,
) -> dict:
    metrics = result.llm_metrics
    scores = result.scores
    deal = result.deal
    gap = None
    if scores is not None:
        gap = round(abs(scores.borrower_score - scores.lender_score), 1)
    record: dict = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "persona_id": persona_id,
        "persona_name": persona_name,
        "attempt": attempt,
        "status": result.status.value,
        "deal_status": result.status.value,
        "rounds": result.rounds,
        "error": error,
        "borrower_score": scores.borrower_score if scores else None,
        "lender_score": scores.lender_score if scores else None,
        "score_gap": gap,
        "consensus_reached": bool(deal.consensus_reached) if deal else False,
        "prompt_tokens": metrics.prompt_tokens if metrics else None,
        "completion_tokens": metrics.completion_tokens if metrics else None,
        "total_tokens": metrics.total_tokens if metrics else None,
        "duration_ms": metrics.duration_ms if metrics else None,
        "ttft_ms": metrics.time_to_first_token_ms if metrics else None,
        "reasons": list(result.reasons),
        "deal": None,
    }
    if deal is not None:
        record["deal"] = {
            "downpayment": deal.downpayment,
            "interest_rate_pct": deal.interest_rate_pct,
            "loan_length_years": deal.loan_length_years,
            "rate_type": deal.rate_type,
            "initial_period_years": deal.initial_period_years,
            "arrangement_fee": deal.arrangement_fee,
            "cashback": deal.cashback,
            "overpayment_allowance_pct": deal.overpayment_allowance_pct,
            "erc_pct": deal.erc_pct,
            "repayment_type": deal.repayment_type,
            "portable": deal.portable,
            "free_valuation": deal.free_valuation,
            "free_legal": deal.free_legal,
        }
    return record


def append_interaction(
    result: WorkflowResult,
    *,
    model_id: str,
    persona_id: str | None = None,
    persona_name: str | None = None,
    attempt: int | None = None,
    error: str | None = None,
    path: Path | None = None,
) -> dict:
    """Append one row to results/interactions.json. Always writes to disk."""
    target = (path or results_json_path()).resolve()
    record = build_record(
        result,
        model_id=model_id,
        persona_id=persona_id,
        persona_name=persona_name,
        attempt=attempt,
        error=error,
    )
    data = _read_store(target)
    rows = data.setdefault("interactions", [])
    if not isinstance(rows, list):
        rows = []
        data["interactions"] = rows
    rows.append(record)
    _write_store(target, data)
    logger.info(
        "Saved interaction %s status=%s → %s (n=%d)",
        record["id"],
        record["status"],
        target,
        len(rows),
    )
    return record


# Back-compat aliases used during the rewrite
record_interaction = append_interaction
interactions_path = results_json_path
ensure_interactions_file = ensure_results_json
build_interaction_record = build_record
