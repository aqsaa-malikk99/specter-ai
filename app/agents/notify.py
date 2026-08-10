"""Notify / Report Agent.

Compiles the outputs of the extraction, diff, risk, and deadline agents into
a single draft email for a human to review and send. This agent never sends
anything itself — every response carries status="draft_awaiting_approval",
and nothing downstream of this call touches email infrastructure. See the
spec's human-in-the-loop boundary: every agent output here is a draft or a
flag, and a person signs off before anything leaves the system.
"""
import json

from langchain_core.prompts import ChatPromptTemplate

from app.agents.schemas import (
    ClauseExtractionResult,
    DeadlineResult,
    DiffResult,
    DraftEmail,
    IntakeResult,
    RiskAssessmentResult,
)
from app.llm_gateway import get_llm

SYSTEM_PROMPT = """You are the Notify/Report Agent in a contract review pipeline. You are
given the structured outputs of the earlier agents in this pipeline (intake, clause
extraction, an optional diff against a prior version, risk flags, and the computed
renewal deadline). Compile these into a single, concise internal email a lawyer can
skim, review, and send on to whoever needs to act.

Use only the facts given to you - do not invent clauses, dates, or risks that were
not provided. If diff is null, this is the first version of the contract on file and
there is nothing to compare against - say so rather than omitting the section
silently. Structure the body with short sections: Deadline, What Changed (if
applicable), Flagged Risks, and a one-line bottom-line recommendation.

This is a draft only. Never claim the email has been sent or the deadline has been
added to a calendar - it has not, and won't be until a human approves it."""

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        (
            "human",
            "Intake:\n{intake}\n\nDiff against prior version (null if none):\n{diff}\n\n"
            "Risk flags:\n{risk}\n\nDeadline:\n{deadline}",
        ),
    ]
)


def run(
    intake: IntakeResult,
    clauses: ClauseExtractionResult,
    diff: DiffResult | None,
    risk: RiskAssessmentResult,
    deadline: DeadlineResult,
    provider: str | None = None,
    model: str | None = None,
) -> DraftEmail:
    llm = get_llm(provider, model).with_structured_output(DraftEmail)
    chain = _prompt | llm
    return chain.invoke(
        {
            "intake": json.dumps(intake.model_dump(), indent=2),
            "diff": json.dumps(diff.model_dump(), indent=2) if diff else "null",
            "risk": json.dumps(risk.model_dump(), indent=2),
            "deadline": json.dumps(deadline.model_dump(), indent=2),
        }
    )
