"""Content Recommendation Agent — recommends content for visibility gaps."""

import logging
from typing import Callable
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.schemas.agents import (
    ContentRecommendation,
    ContentType,
    PipelineState,
    Priority,
    ScoredQuery,
)
from app.agents.base import extract_tokens, log_agent_action

logger = logging.getLogger(__name__)

AGENT_NAME = "ContentRecommendationAgent"


class RecommendationItem(BaseModel):
    target_query_uuid: str
    content_type: ContentType
    title: str
    rationale: str
    target_keywords: list[str]
    priority: Priority


class ContentRecommendationOutput(BaseModel):
    recommendations: list[RecommendationItem] = Field(min_length=3, max_length=5)


def _format_gap_queries(queries: list[ScoredQuery]) -> str:
    lines = []
    for q in queries:
        lines.append(
            f"- UUID: {q.query_uuid}\n"
            f"  Query: {q.query_text}\n"
            f"  Opportunity score: {q.opportunity_score}\n"
            f"  Volume: {q.estimated_search_volume}, Difficulty: {q.competitive_difficulty}"
        )
    return "\n".join(lines)


def create_content_recommendation_node(
    llm: ChatOpenAI,
) -> Callable[[PipelineState], dict]:
    """Create a LangGraph node that generates 3–5 content recommendations."""

    structured_llm = llm.with_structured_output(
        ContentRecommendationOutput, include_raw=True
    )

    def content_recommendation_node(state: PipelineState) -> dict:
        if state.get("status") == "failed":
            return {}

        profile = state["profile"]
        scored_queries = state.get("scored_queries", [])

        gap_queries = [q for q in scored_queries if not q.domain_visible]
        gap_queries.sort(key=lambda q: q.opportunity_score, reverse=True)
        top_gaps = gap_queries[:10]

        if not top_gaps:
            log_agent_action(
                logger,
                AGENT_NAME,
                "No visibility gaps found — skipping recommendations",
            )
            return {"recommendations": [], "status": "completed"}

        log_agent_action(
            logger,
            AGENT_NAME,
            "Generating content recommendations",
            {"gap_count": len(top_gaps)},
        )

        system_prompt = (
            "You are a content strategist specializing in AI search visibility. "
            "Given queries where a domain is NOT appearing in AI answers, "
            "recommend specific, actionable content pieces that would address "
            "each visibility gap."
        )
        user_prompt = (
            f"Target domain: {profile.domain}\n"
            f"Industry: {profile.industry}\n\n"
            f"Top visibility-gap queries:\n{_format_gap_queries(top_gaps)}\n\n"
            "Generate 3–5 content recommendations. Each must reference a "
            "target_query_uuid from the list above. Include content_type "
            "(blog_post, landing_page, faq, comparison, guide), title, "
            "rationale, target_keywords, and priority (high/medium/low)."
        )

        try:
            result = structured_llm.invoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
            )
            parsed: ContentRecommendationOutput = result["parsed"]
            tokens = extract_tokens(result["raw"])

            valid_uuids = {q.query_uuid for q in top_gaps}
            invalid_uuids = [
                item.target_query_uuid
                for item in parsed.recommendations
                if item.target_query_uuid not in valid_uuids
            ]
            if invalid_uuids:
                raise ValueError(
                    f"Recommendations reference unknown target_query_uuid(s): {invalid_uuids}"
                )

            recommendations = [
                ContentRecommendation(
                    recommendation_uuid=str(uuid4()),
                    target_query_uuid=item.target_query_uuid,
                    content_type=item.content_type,
                    title=item.title,
                    rationale=item.rationale,
                    target_keywords=item.target_keywords,
                    priority=item.priority,
                )
                for item in parsed.recommendations
            ]

            log_agent_action(
                logger,
                AGENT_NAME,
                "Recommendations generated",
                {"count": len(recommendations)},
            )

            return {
                "recommendations": recommendations,
                "total_tokens": state.get("total_tokens", 0) + tokens,
                "status": "completed",
            }
        except Exception as e:
            logger.error(f"[{AGENT_NAME}] Failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    return content_recommendation_node
