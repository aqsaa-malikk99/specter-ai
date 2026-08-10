"""Response models for read endpoints.

Kept separate from the ORM models (app/models.py) so the API never
serializes a SQLAlchemy instance directly - that risks pulling in lazy-loaded
relationships (client_profile <-> contracts) and internal SQLAlchemy state.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class ClientProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    current_stage: str | None
    error: str | None
    created_by: str | None
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
    contract_id: str | None
    agent_name: str
    input_hash: str
    output: dict
    confidence: float | None
    input_tokens: int | None
    output_tokens: int | None
    performed_by: str | None
    created_at: datetime


class AuditHistoryEntryOut(BaseModel):
    """A single audit row enriched with contract/client context, for the
    cross-client history panel (a bare AuditLogOut isn't identifiable on
    its own once you're looking across many contracts)."""

    id: str
    contract_id: str | None
    client_name: str | None
    contract_type: str | None
    agent_name: str
    confidence: float | None
    input_tokens: int | None
    output_tokens: int | None
    performed_by: str | None
    created_at: datetime


class UsageByAgent(BaseModel):
    agent_name: str
    calls: int
    input_tokens: int
    output_tokens: int


class UsageSummaryOut(BaseModel):
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    by_agent: list[UsageByAgent]
