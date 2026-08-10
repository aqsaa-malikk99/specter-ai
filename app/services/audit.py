"""Append-only audit trail: one row per agent invocation (timestamp, input
hash, output, confidence). Per the spec, this is what answers "who/what knew
this and when" for SRA-style accountability — every node in the pipeline
graph logs through here.
"""
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def _hash_input(input_data: Any) -> str:
    canonical = json.dumps(input_data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def log_agent_call(
    db: Session,
    request_id: str,
    agent_name: str,
    input_data: Any,
    output_data: Any,
    confidence: float | None = None,
) -> None:
    db.add(
        AuditLog(
            request_id=request_id,
            agent_name=agent_name,
            input_hash=_hash_input(input_data),
            output=output_data,
            confidence=confidence,
        )
    )
    db.flush()


def backfill_contract_id(db: Session, request_id: str, contract_id: str) -> None:
    db.query(AuditLog).filter(AuditLog.request_id == request_id).update(
        {AuditLog.contract_id: contract_id}
    )
