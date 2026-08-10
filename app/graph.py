"""Orchestrator: routes a contract through the agent pipeline.

Design principle from the spec: agents are specialists, the orchestrator is
dumb on purpose. Each node calls one agent and merges its structured output
into state; the graph just sequences them and branches on whether a prior
contract version exists (skip the Diff Agent entirely when there isn't one).
"""
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents import deadline, diff, extraction, intake, notify, risk
from app.agents.schemas import (
    ClauseExtractionResult,
    DeadlineResult,
    DiffResult,
    DraftEmail,
    IntakeResult,
    RiskAssessmentResult,
)
from app.services.client_matching import find_or_create_client_profile
from app.services.playbook import load_playbook
from app.services.renewal_detection import find_prior_contract


class PipelineState(TypedDict, total=False):
    contract_text: str
    provider: str | None
    model: str | None
    db: Session  # not persisted - passed through so nodes can query/create rows mid-pipeline

    intake: IntakeResult
    client_profile_id: str
    is_renewal_of: str | None
    prior_clauses: dict | None

    clauses: ClauseExtractionResult
    diff: DiffResult | None
    risk: RiskAssessmentResult
    deadline: DeadlineResult
    draft_email: DraftEmail


def _run_intake(state: PipelineState) -> dict[str, Any]:
    result = intake.run(state["contract_text"], state.get("provider"), state.get("model"))
    return {"intake": result}


def _run_match_client(state: PipelineState) -> dict[str, Any]:
    db = state["db"]
    profile = find_or_create_client_profile(db, state["intake"].client_name)
    prior = find_prior_contract(db, profile.id, state["intake"].contract_type)
    return {
        "client_profile_id": profile.id,
        "is_renewal_of": prior.id if prior else None,
        "prior_clauses": prior.extracted_clauses if prior else None,
    }


def _run_extraction(state: PipelineState) -> dict[str, Any]:
    result = extraction.run(state["contract_text"], state.get("provider"), state.get("model"))
    return {"clauses": result}


def _has_prior_version(state: PipelineState) -> str:
    return "diff" if state.get("prior_clauses") else "risk"


def _run_diff(state: PipelineState) -> dict[str, Any]:
    result = diff.run(
        old_clauses=state["prior_clauses"],
        new_clauses=state["clauses"],
        provider=state.get("provider"),
        model=state.get("model"),
    )
    return {"diff": result}


def _run_risk(state: PipelineState) -> dict[str, Any]:
    result = risk.run(
        clauses=state["clauses"],
        playbook=load_playbook(),
        provider=state.get("provider"),
        model=state.get("model"),
    )
    return {"risk": result}


def _run_deadline(state: PipelineState) -> dict[str, Any]:
    result = deadline.compute_deadline(
        effective_date=state["intake"].effective_date,
        term_length_months=state["intake"].term_length_months,
        auto_renewal=state["clauses"].auto_renewal,
    )
    return {"deadline": result}


def _run_notify(state: PipelineState) -> dict[str, Any]:
    result = notify.run(
        intake=state["intake"],
        clauses=state["clauses"],
        diff=state.get("diff"),
        risk=state["risk"],
        deadline=state["deadline"],
        provider=state.get("provider"),
        model=state.get("model"),
    )
    return {"draft_email": result}


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("intake", _run_intake)
    graph.add_node("match_client", _run_match_client)
    graph.add_node("extraction", _run_extraction)
    graph.add_node("diff", _run_diff)
    graph.add_node("risk", _run_risk)
    graph.add_node("deadline", _run_deadline)
    graph.add_node("notify", _run_notify)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "match_client")
    graph.add_edge("match_client", "extraction")
    graph.add_conditional_edges(
        "extraction", _has_prior_version, {"diff": "diff", "risk": "risk"}
    )
    graph.add_edge("diff", "risk")
    graph.add_edge("risk", "deadline")
    graph.add_edge("deadline", "notify")
    graph.add_edge("notify", END)

    return graph.compile()


pipeline = build_pipeline()
