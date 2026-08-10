"""Orchestrator: routes a contract through the agent pipeline.

Design principle from the spec: agents are specialists, the orchestrator is
dumb on purpose. Each node calls one agent and merges its structured output
into state; the graph just sequences them (and, from Phase 2 onward, branches
on whether a prior contract version exists).
"""
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents import deadline, extraction, intake
from app.agents.schemas import ClauseExtractionResult, DeadlineResult, IntakeResult


class PipelineState(TypedDict, total=False):
    contract_text: str
    provider: str | None
    model: str | None
    intake: IntakeResult
    clauses: ClauseExtractionResult
    deadline: DeadlineResult


def _run_intake(state: PipelineState) -> dict[str, Any]:
    result = intake.run(state["contract_text"], state.get("provider"), state.get("model"))
    return {"intake": result}


def _run_extraction(state: PipelineState) -> dict[str, Any]:
    result = extraction.run(state["contract_text"], state.get("provider"), state.get("model"))
    return {"clauses": result}


def _run_deadline(state: PipelineState) -> dict[str, Any]:
    result = deadline.compute_deadline(
        effective_date=state["intake"].effective_date,
        term_length_months=state["intake"].term_length_months,
        auto_renewal=state["clauses"].auto_renewal,
    )
    return {"deadline": result}


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("intake", _run_intake)
    graph.add_node("extraction", _run_extraction)
    graph.add_node("deadline", _run_deadline)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "extraction")
    graph.add_edge("extraction", "deadline")
    graph.add_edge("deadline", END)

    return graph.compile()


pipeline = build_pipeline()
