"""Runs the agent pipeline in the background and persists progress after
every single stage — not just at the end.

This is the resilience mechanism: the Contract row is created (status
"processing") before the pipeline starts, and each node's output is written
and committed to that same row as soon as the node finishes. If the client's
connection drops, or the process itself dies mid-run, whatever stages
already completed are safely on disk and visible in the UI/history — only
the remaining stages are lost, not the whole job.
"""
import logging

from app.db import SessionLocal
from app.graph import pipeline
from app.models import Contract

logger = logging.getLogger(__name__)

# Maps a LangGraph node name to a function that copies its output onto the
# Contract row. Plain attribute assignment (not __dict__.update) so
# SQLAlchemy's instrumentation actually registers the change as dirty.
def _apply_intake(contract: Contract, output: dict) -> None:
    result = output["intake"]
    contract.contract_type = result.contract_type
    contract.parties = result.parties
    contract.effective_date = result.effective_date
    contract.term_length_months = result.term_length_months


def _apply_match_client(contract: Contract, output: dict) -> None:
    contract.client_profile_id = output["client_profile_id"]
    contract.is_renewal_of = output.get("is_renewal_of")


def _apply_extraction(contract: Contract, output: dict) -> None:
    contract.extracted_clauses = output["clauses"].model_dump()


def _apply_diff(contract: Contract, output: dict) -> None:
    contract.diff = output["diff"].model_dump()


def _apply_risk(contract: Contract, output: dict) -> None:
    contract.risk_flags = output["risk"].model_dump()


def _apply_deadline(contract: Contract, output: dict) -> None:
    contract.deadline = output["deadline"].model_dump()


def _apply_notify(contract: Contract, output: dict) -> None:
    contract.draft_email = output["draft_email"].model_dump()


_STAGE_APPLIERS = {
    "intake": _apply_intake,
    "match_client": _apply_match_client,
    "extraction": _apply_extraction,
    "diff": _apply_diff,
    "risk": _apply_risk,
    "deadline": _apply_deadline,
    "notify": _apply_notify,
}


def run_pipeline_background(
    contract_id: str,
    contract_text: str,
    provider: str | None,
    model: str | None,
    request_id: str,
    performed_by: str | None,
) -> None:
    db = SessionLocal()
    try:
        contract = db.get(Contract, contract_id)
        if contract is None:
            logger.error("Contract %s vanished before pipeline could run", contract_id)
            return

        state = {
            "contract_text": contract_text,
            "provider": provider,
            "model": model,
            "db": db,
            "request_id": request_id,
            "contract_id": contract_id,
            "performed_by": performed_by,
        }

        for step in pipeline.stream(state):
            for node_name, output in step.items():
                applier = _STAGE_APPLIERS.get(node_name)
                if applier:
                    applier(contract, output)
                contract.current_stage = node_name
                db.commit()

        contract.status = "completed"
        contract.current_stage = "done"
        db.commit()

    except Exception as exc:  # noqa: BLE001 - this is the top-level job boundary
        logger.exception("Pipeline failed for contract %s", contract_id)
        db.rollback()
        failed_contract = db.get(Contract, contract_id)
        if failed_contract is not None:
            failed_contract.status = "failed"
            failed_contract.error = str(exc)[:2000]
            db.commit()
    finally:
        db.close()
