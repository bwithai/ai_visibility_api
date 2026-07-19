from typing import Literal

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from app.agents.base import get_llm
from app.agents.content_recommendation_agent import create_content_recommendation_node
from app.agents.query_discovery_agent import create_query_discovery_node
from app.agents.visibility_scoring_agent import create_visibility_scoring_node
from app.schemas.agents import BusinessProfile, PipelineRunResult, PipelineState


def _route_on_status(state: PipelineState) -> Literal["continue", "end"]:
    if state.get("status") == "failed":
        return "end"
    return "continue"


def _resolve_pipeline_status(final_state: PipelineState) -> str:
    if final_state.get("error"):
        return "failed"
    status = final_state.get("status", "running")
    if status in ("running", "completed"):
        return "completed"
    return status


def create_collaborative_workflow(llm: ChatOpenAI):
    """Create a LangGraph workflow for the 3-agent pipeline.

    Sequence: Query Discovery → Visibility Scoring → Content Recommendation
    """

    graph = StateGraph(PipelineState)

    graph.add_node("discover_queries", create_query_discovery_node(llm))
    graph.add_node("score_visibility", create_visibility_scoring_node())
    graph.add_node("recommend_content", create_content_recommendation_node(llm))

    graph.set_entry_point("discover_queries")
    graph.add_conditional_edges(
        "discover_queries",
        _route_on_status,
        {"continue": "score_visibility", "end": END},
    )
    graph.add_conditional_edges(
        "score_visibility",
        _route_on_status,
        {"continue": "recommend_content", "end": END},
    )
    graph.add_edge("recommend_content", END)

    return graph.compile()


def run_pipeline(profile: BusinessProfile, llm: ChatOpenAI = get_llm()) -> PipelineRunResult:
    """Run the full pipeline and return a structured result."""
    from uuid import uuid4

    pipeline_run_uuid = str(uuid4())
    workflow = create_collaborative_workflow(llm)

    initial_state: PipelineState = {
        "profile": profile,
        "queries": [],
        "scored_queries": [],
        "recommendations": [],
        "pipeline_run_uuid": pipeline_run_uuid,
        "status": "running",
        "total_tokens": 0,
        "error": None,
    }

    final_state = workflow.invoke(initial_state)

    status = _resolve_pipeline_status(final_state)

    scored_queries = final_state.get("scored_queries", [])
    top_opportunity = sorted(
        scored_queries, key=lambda q: q.opportunity_score, reverse=True
    )[:3]

    return PipelineRunResult(
        pipeline_run_uuid=pipeline_run_uuid,
        status=status,
        queries_discovered_count=len(final_state.get("queries", [])),
        queries_scored_count=len(scored_queries),
        top_opportunity_queries=top_opportunity,
        content_recommendations=final_state.get("recommendations", []),
        total_tokens_used=final_state.get("total_tokens", 0),
        error=final_state.get("error"),
    )