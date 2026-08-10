"""Risk & Ambiguity Agent.

Flags clauses that fall outside the firm's playbook, plus anything the
Clause Extraction Agent scored below a confidence threshold (i.e. flagged
in low_confidence_flags) — low-confidence extractions get surfaced for
human review rather than silently asserted.
"""
import json

from langchain_core.prompts import ChatPromptTemplate

from app.agents.schemas import ClauseExtractionResult, RiskAssessmentResult
from app.llm_gateway import get_llm, invoke_structured

SYSTEM_PROMPT = """You are the Risk & Ambiguity Agent in a contract review pipeline.
You are given the extracted clause values for a contract and the firm's playbook -
a list of acceptable fallback positions. Compare each relevant clause against the
matching playbook rule and flag anything that falls outside it.

Also flag every clause_type listed in low_confidence_extractions - these are
clauses the extraction agent was not confident about, and a human should verify
them before this analysis is relied upon.

Severity guide:
- critical: a missing protection with real financial/legal exposure (e.g. no liability cap, one-sided indemnification)
- warn: outside the playbook but not severe (e.g. notice window slightly off, unusually long confidentiality tail)
- info: low-confidence extraction that needs human verification, or a minor ambiguity

Do not flag a clause that is within the playbook's stated bounds. If nothing is
flagged, return an empty flags list and say so plainly in the summary."""

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        (
            "human",
            "Playbook:\n{playbook}\n\nExtracted clauses:\n{clauses}\n\n"
            "Low-confidence extractions to flag regardless of playbook fit:\n{low_confidence}",
        ),
    ]
)


def run(
    clauses: ClauseExtractionResult,
    playbook: list[dict],
    provider: str | None = None,
    model: str | None = None,
) -> tuple[RiskAssessmentResult, dict]:
    llm = get_llm(provider, model)
    return invoke_structured(
        _prompt,
        llm,
        RiskAssessmentResult,
        {
            "playbook": json.dumps(playbook, indent=2),
            "clauses": json.dumps(clauses.model_dump(), indent=2),
            "low_confidence": json.dumps(clauses.low_confidence_flags),
        },
    )
