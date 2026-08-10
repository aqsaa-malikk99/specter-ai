from langchain_core.prompts import ChatPromptTemplate

from app.agents.schemas import IntakeResult
from app.llm_gateway import get_llm

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


def run(contract_text: str, provider: str | None = None, model: str | None = None) -> IntakeResult:
    llm = get_llm(provider, model).with_structured_output(IntakeResult)
    chain = _prompt | llm
    return chain.invoke({"contract_text": contract_text})
