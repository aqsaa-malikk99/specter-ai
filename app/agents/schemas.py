from typing import Literal

from pydantic import BaseModel, Field


class IntakeResult(BaseModel):
    contract_type: str = Field(description="e.g. 'SaaS Subscription Agreement', 'MSA', 'NDA'")
    parties: list[str] = Field(description="Names of the contracting parties")
    effective_date: str | None = Field(default=None, description="ISO date, or null if not found")
    term_length_months: int | None = Field(default=None, description="Initial term length in months, if stated")
    client_name: str = Field(description="The party this firm represents / files the contract under")


class AutoRenewalClause(BaseModel):
    present: bool
    notice_window_days: int | None = Field(default=None, description="Days before renewal that cancellation notice is due")
    notice_window_text: str | None = Field(default=None, description="Exact clause language describing the notice window")
    renewal_term_months: int | None = None
    section_ref: str | None = None
    confidence: float = Field(ge=0, le=1)


class ClauseExtractionResult(BaseModel):
    auto_renewal: AutoRenewalClause
    indemnification_text: str | None = None
    indemnification_mutual: bool | None = None
    liability_cap_present: bool | None = None
    liability_cap_text: str | None = None
    termination_rights_text: str | None = None
    confidentiality_term_months: int | None = None
    low_confidence_flags: list[str] = Field(default_factory=list, description="Clause types the model was unsure about")


class DeadlineResult(BaseModel):
    cancel_by_date: str | None = Field(default=None, description="ISO date - the actual must-cancel-by date, computed from effective_date + term_length_months - notice_window_days")
    reminder_dates: list[str] = Field(default_factory=list, description="ISO dates for 90/30/7 day reminders before cancel_by_date")
    reasoning: str = Field(description="One or two sentences showing the date arithmetic")


class ClauseDiff(BaseModel):
    clause_type: str = Field(description="e.g. 'auto_renewal', 'indemnification', 'liability_cap'")
    old_value: str = Field(description="Plain-English summary of the clause in the prior contract version")
    new_value: str = Field(description="Plain-English summary of the clause in the new contract version")
    materiality: Literal["cosmetic", "substantive"] = Field(
        description="'cosmetic' if reworded-but-equivalent, 'substantive' if the actual rights/obligations changed"
    )


class DiffResult(BaseModel):
    changes: list[ClauseDiff] = Field(default_factory=list, description="Only clauses that actually changed between versions")
    summary: str = Field(description="One or two sentence plain-English summary of what changed overall")


class RiskFlag(BaseModel):
    clause_type: str
    issue: str = Field(description="Plain-English description of why this falls outside the playbook, or why confidence was too low to trust")
    severity: Literal["info", "warn", "critical"]


class RiskAssessmentResult(BaseModel):
    flags: list[RiskFlag] = Field(default_factory=list)
    summary: str = Field(description="One or two sentence overall risk summary")


class DraftEmailContent(BaseModel):
    """What the LLM actually produces. `status` is deliberately not part of
    this schema - it's a fixed constant, not a model judgment call, and a
    single-value Literal field has been observed to trip up structured output
    on weaker models. It's attached in Python after parsing (see DraftEmail)."""

    subject: str
    body: str = Field(description="Plain-text email body summarizing the changelog, flagged risks, and upcoming deadline")


class DraftEmail(BaseModel):
    subject: str
    body: str
    status: Literal["draft_awaiting_approval"] = "draft_awaiting_approval"
