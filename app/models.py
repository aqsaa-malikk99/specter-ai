import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ClientProfile(Base):
    __tablename__ = "client_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contracts: Mapped[list["Contract"]] = relationship(back_populates="client_profile")


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    client_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("client_profiles.id"), nullable=True
    )
    is_renewal_of: Mapped[str | None] = mapped_column(
        ForeignKey("contracts.id"), nullable=True
    )

    # Pipeline lifecycle: created "processing" immediately on upload, then
    # updated after every single graph stage - not just at the end - so a
    # dropped connection or a mid-run crash loses nothing already computed.
    status: Mapped[str] = mapped_column(String, default="processing")  # processing | completed | failed
    current_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)

    raw_text: Mapped[str] = mapped_column(String)
    contract_type: Mapped[str | None] = mapped_column(String, nullable=True)
    parties: Mapped[list | None] = mapped_column(JSON, nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String, nullable=True)
    term_length_months: Mapped[int | None] = mapped_column(nullable=True)

    extracted_clauses: Mapped[list | None] = mapped_column(JSON, nullable=True)
    deadline: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    diff: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_flags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    draft_email: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    client_profile: Mapped[ClientProfile | None] = relationship(back_populates="contracts")


class AuditLog(Base):
    """One row per agent invocation: who/what knew this and when.

    Written during the pipeline run (keyed by request_id, since the Contract
    row doesn't exist yet) and backfilled with contract_id once the contract
    is persisted. This answers the spec's audit requirement without coupling
    logging to a contract that may not exist yet if the pipeline errors out.
    """

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    request_id: Mapped[str] = mapped_column(String, index=True)
    contract_id: Mapped[str | None] = mapped_column(
        ForeignKey("contracts.id"), nullable=True, index=True
    )
    agent_name: Mapped[str] = mapped_column(String, index=True)
    input_hash: Mapped[str] = mapped_column(String)
    output: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    performed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
