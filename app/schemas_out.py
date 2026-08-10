"""Response models for read endpoints.

Kept separate from the ORM models (app/models.py) so the API never
serializes a SQLAlchemy instance directly - that risks pulling in lazy-loaded
relationships (client_profile <-> contracts) and internal SQLAlchemy state.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClientProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_profile_id: str | None
    is_renewal_of: str | None
    contract_type: str | None
    parties: list | None
    effective_date: str | None
    term_length_months: int | None
    extracted_clauses: dict | None
    deadline: dict | None
    diff: dict | None
    risk_flags: dict | None
    draft_email: dict | None
    created_at: datetime


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_name: str
    input_hash: str
    output: dict
    confidence: float | None
    created_at: datetime
