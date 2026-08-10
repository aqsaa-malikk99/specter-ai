from langchain_core.prompts import ChatPromptTemplate

from app.agents.schemas import IntakeResult
from app.llm_gateway import get_llm, invoke_structured

SYSTEM_PROMPT = """You are the Intake & Classification Agent in a contract review pipeline.
Given raw contract text, extract the contracting parties, contract type, effective date,
term length, and identify which party is the client (the firm's own client, not the counterparty).
If a field cannot be determined, use null rather than guessing."""

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "Contract text:\n\n{contract_text}"),
    ]
)


def run(
    contract_text: str, provider: str | None = None, model: str | None = None
) -> tuple[IntakeResult, dict]:
    llm = get_llm(provider, model)
    return invoke_structured(_prompt, llm, IntakeResult, {"contract_text": contract_text})
