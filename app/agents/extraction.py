from langchain_core.prompts import ChatPromptTemplate

from app.agents.schemas import ClauseExtractionResult
from app.llm_gateway import get_llm

SYSTEM_PROMPT = """You are the Clause Extraction Agent in a contract review pipeline.
Extract the following risk-relevant clauses from the contract text, each with a confidence
score (0-1). For Phase 1, focus most carefully on the auto-renewal clause and its notice
window language, since that drives the deadline calculation - convert stated notice periods
(e.g. "90 days", "three months") into notice_window_days as an integer.
If a clause is absent, mark it appropriately rather than fabricating text. List any clause
types you are unsure about in low_confidence_flags."""

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "Contract text:\n\n{contract_text}"),
    ]
)


def run(contract_text: str, provider: str | None = None, model: str | None = None) -> ClauseExtractionResult:
    llm = get_llm(provider, model).with_structured_output(ClauseExtractionResult)
    chain = _prompt | llm
    return chain.invoke({"contract_text": contract_text})
