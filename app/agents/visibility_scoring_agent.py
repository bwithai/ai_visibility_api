"""Visibility Scoring Agent — scores queries with real DataForSEO metrics."""

import logging
import random
from typing import Callable

from app.schemas.agents import (
    PipelineState,
    ScoredQuery,
    compute_opportunity_score,
)
from app.tools.dataforseo_tool import fetch_ai_visibility, fetch_keyword_metrics
from app.agents.base import log_agent_action

logger = logging.getLogger(__name__)

AGENT_NAME = "VisibilityScoringAgent"
MAX_QUERIES_TO_SCORE = 1  # DataForSEO live endpoint: 12 req/min; score one query per run


def create_visibility_scoring_node() -> Callable[[PipelineState], dict]:
    """Create a LangGraph node that scores queries using DataForSEO APIs only."""

    def visibility_scoring_node(state: PipelineState) -> dict:
        if state.get("status") == "failed":
            return {}

        profile = state["profile"]
        queries = state.get("queries", [])
        if not queries:
            return {"status": "failed", "error": "No queries to score"}

        queries_to_score = random.sample(
            queries, min(MAX_QUERIES_TO_SCORE, len(queries))
        )
        selected_query = queries_to_score[0]

        log_agent_action(
            logger,
            AGENT_NAME,
            "Scoring visibility",
            {
                "domain": profile.domain,
                "discovered_count": len(queries),
                "scoring_count": len(queries_to_score),
                "selected_query": selected_query.query_text,
            },
        )

        try:
            raw_metrics: list[dict] = []
            for query in queries_to_score:
                visibility = fetch_ai_visibility(query.query_text, profile.domain)
                keyword_metrics = fetch_keyword_metrics(
                    query.api_keyword, original_query=query.query_text
                )

                volume = keyword_metrics["search_volume"]
                volume_source = "google_ads"
                if volume is None:
                    ai_volume = visibility.get("ai_search_volume")
                    if ai_volume is None:
                        raise RuntimeError(
                            f"No search volume from Google Ads and no ai_search_volume "
                            f"from LLM Mentions API for query {query.query_text!r}."
                        )
                    volume = int(ai_volume)
                    volume_source = "ai_search_volume"

                raw_metrics.append(
                    {
                        "query": query,
                        "volume": volume,
                        "volume_source": volume_source,
                        "difficulty": keyword_metrics["difficulty"],
                        "difficulty_source": keyword_metrics["difficulty_source"],
                        "visibility": visibility,
                    }
                )

            max_volume = max((m["volume"] for m in raw_metrics), default=1)
            scored_queries: list[ScoredQuery] = []

            for item in raw_metrics:
                query = item["query"]
                visibility = item["visibility"]

                opportunity_score = compute_opportunity_score(
                    volume=item["volume"],
                    difficulty=item["difficulty"],
                    domain_visible=visibility["domain_visible"],
                    commercial_intent=query.commercial_intent,
                    max_volume=max_volume,
                )

                scored_queries.append(
                    ScoredQuery(
                        query_uuid=query.query_uuid,
                        query_text=query.query_text,
                        commercial_intent=query.commercial_intent,
                        estimated_search_volume=item["volume"],
                        search_volume_source=item["volume_source"],
                        competitive_difficulty=item["difficulty"],
                        difficulty_source=item["difficulty_source"],
                        domain_visible=visibility["domain_visible"],
                        visibility_position=visibility["visibility_position"],
                        visibility_reason=visibility["visibility_reason"],
                        ai_search_volume=visibility.get("ai_search_volume"),
                        opportunity_score=opportunity_score,
                    )
                )

                log_agent_action(
                    logger,
                    AGENT_NAME,
                    "Query scored",
                    {
                        "query": query.query_text,
                        "domain_visible": visibility["domain_visible"],
                        "visibility_reason": visibility["visibility_reason"],
                        "opportunity_score": opportunity_score,
                    },
                )

            scored_queries.sort(key=lambda q: q.opportunity_score, reverse=True)

            log_agent_action(
                logger,
                AGENT_NAME,
                "Scoring complete",
                {"scored_count": len(scored_queries)},
            )

            return {"scored_queries": scored_queries}
        except Exception as e:
            logger.error(f"[{AGENT_NAME}] Failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    return visibility_scoring_node
