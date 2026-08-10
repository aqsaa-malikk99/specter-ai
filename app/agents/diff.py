"""Diff Agent — runs only when a prior version of the contract is on file.

Compares extracted clause values, not raw text, so a reworded-but-equivalent
clause doesn't false-flag as a change (per the spec: raw text diff on legal
documents is noisy and useless).
"""
import json

from langchain_core.prompts import ChatPromptTemplate

from app.agents.schemas import ClauseExtractionResult, DiffResult
from app.llm_gateway import get_llm

SYSTEM_PROMPT = """You are the Diff Agent in a contract review pipeline. You are given the
extracted clause values from two versions of the same contract - a prior version and a new
(renewal) version. Compare them clause by clause and produce a plain-English changelog.

Only include a clause in `changes` if its substance actually differs between versions.
Mark materiality as 'cosmetic' if the clause was reworded but the underlying rights and
obligations are equivalent, or 'substantive' if the actual terms changed (e.g. notice window
shortened, liability cap added or removed, indemnification became one-sided)."""

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        (
            "human",
            "Prior version extracted clauses:\n{old_clauses}\n\n"
            "New version extracted clauses:\n{new_clauses}",
        ),
    ]
)


def run(
    old_clauses: ClauseExtractionResult | dict,
    new_clauses: ClauseExtractionResult,
    provider: str | None = None,
    model: str | None = None,
) -> DiffResult:
    old_json = old_clauses if isinstance(old_clauses, dict) else old_clauses.model_dump()
    llm = get_llm(provider, model).with_structured_output(DiffResult)
    chain = _prompt | llm
    return chain.invoke(
        {
            "old_clauses": json.dumps(old_json, indent=2),
            "new_clauses": json.dumps(new_clauses.model_dump(), indent=2),
        }
    )
