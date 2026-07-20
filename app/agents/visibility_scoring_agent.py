"""Visibility Scoring Agent — scores queries with real DataForSEO metrics."""

import logging
from typing import Callable

from app.schemas.agents import (
    DiscoveredQuery,
    PipelineState,
    ScoredQuery,
    compute_opportunity_score,
)
from app.tools.dataforseo_tool import (
    fetch_ai_visibility,
    fetch_keyword_metrics_batch,
    sanitize_keyword_for_google_ads,
)
from app.agents.base import log_agent_action

logger = logging.getLogger(__name__)

AGENT_NAME = "VisibilityScoringAgent"


def _combine_query_metrics(
    query,
    domain: str,
    keyword_metrics_map: dict[str, dict],
) -> dict:
    """Combine pre-fetched keyword metrics with per-query AI visibility."""
    api_keyword = sanitize_keyword_for_google_ads(query.api_keyword)
    keyword_metrics = keyword_metrics_map.get(api_keyword)
    if keyword_metrics is None:
        raise RuntimeError(
            f"No Google Ads metrics for keyword {api_keyword!r} "
            f"(query: {query.query_text!r})."
        )

    visibility = fetch_ai_visibility(query.query_text, domain)

    volume = keyword_metrics["search_volume"]
    volume_source = "google_ads"
    if volume is None:
        ai_volume = visibility.get("ai_search_volume")
        if ai_volume is None:
            raise RuntimeError(
                "No search volume from Google Ads and no ai_search_volume "
                f"from LLM Mentions API for query {query.query_text!r}."
            )
        volume = int(ai_volume)
        volume_source = "ai_search_volume"

    return {
        "query": query,
        "volume": volume,
        "volume_source": volume_source,
        "difficulty": keyword_metrics["difficulty"],
        "difficulty_source": keyword_metrics["difficulty_source"],
        "visibility": visibility,
    }


def score_single_query(
    query: DiscoveredQuery,
    domain: str,
    *,
    max_volume: int | None = None,
) -> ScoredQuery:
    """Score one query for recheck flows using the same logic as the pipeline node."""
    api_keyword = sanitize_keyword_for_google_ads(query.api_keyword)
    keyword_metrics_map = fetch_keyword_metrics_batch(
        [api_keyword],
        labels={api_keyword: query.query_text},
    )
    item = _combine_query_metrics(query, domain, keyword_metrics_map)
    visibility = item["visibility"]
    volume = item["volume"]
    score_max_volume = max(max_volume or 0, volume, 1)

    opportunity_score = compute_opportunity_score(
        volume=volume,
        difficulty=item["difficulty"],
        domain_visible=visibility["domain_visible"],
        commercial_intent=query.commercial_intent,
        max_volume=score_max_volume,
    )

    return ScoredQuery(
        query_uuid=query.query_uuid,
        query_text=query.query_text,
        commercial_intent=query.commercial_intent,
        estimated_search_volume=volume,
        search_volume_source=item["volume_source"],
        competitive_difficulty=item["difficulty"],
        difficulty_source=item["difficulty_source"],
        domain_visible=visibility["domain_visible"],
        visibility_position=visibility["visibility_position"],
        visibility_reason=visibility["visibility_reason"],
        ai_search_volume=visibility.get("ai_search_volume"),
        opportunity_score=opportunity_score,
    )


def create_visibility_scoring_node() -> Callable[[PipelineState], dict]:
    """Create a LangGraph node that scores queries using DataForSEO APIs only."""

    def visibility_scoring_node(state: PipelineState) -> dict:
        if state.get("status") == "failed":
            return {}

        profile = state["profile"]
        queries = state.get("queries", [])
        if not queries:
            return {"status": "failed", "error": "No queries to score"}

        # Production: score every discovered query.
        # queries_to_score = queries

        # Dev/testing — limit LLM Mentions API calls to save credits.
        # Uncomment the block below and comment out `queries_to_score = queries` above.
        import random
        MAX_QUERIES_TO_SCORE = 1  # DataForSEO live endpoint: 12 req/min
        queries_to_score = random.sample(
            queries, min(MAX_QUERIES_TO_SCORE, len(queries))
        )

        log_agent_action(
            logger,
            AGENT_NAME,
            "Scoring visibility",
            {
                "domain": profile.domain,
                "discovered_count": len(queries),
                "scoring_count": len(queries_to_score),
                "queries": [q.query_text for q in queries_to_score],
            },
        )

        keyword_labels: dict[str, str] = {}
        for query in queries_to_score:
            api_keyword = sanitize_keyword_for_google_ads(query.api_keyword)
            keyword_labels.setdefault(api_keyword, query.query_text)

        try:
            keyword_metrics_map = fetch_keyword_metrics_batch(
                list(keyword_labels.keys()),
                labels=keyword_labels,
            )
        except Exception as e:
            error = f"Failed to fetch batched keyword metrics: {e}"
            logger.error("[%s] %s", AGENT_NAME, error, exc_info=True)
            return {"status": "failed", "error": error}

        raw_metrics: list[dict] = []
        skipped_queries: list[dict[str, str]] = []

        for query in queries_to_score:
            try:
                raw_metrics.append(
                    _combine_query_metrics(
                        query, profile.domain, keyword_metrics_map
                    )
                )
            except Exception as e:
                error_reason = str(e)
                skipped_queries.append(
                    {
                        "query_uuid": query.query_uuid,
                        "query_text": query.query_text,
                        "error": error_reason,
                    }
                )
                log_agent_action(
                    logger,
                    AGENT_NAME,
                    "Query skipped due to scoring failure",
                    {
                        "query": query.query_text,
                        "query_uuid": query.query_uuid,
                        "error": error_reason,
                    },
                )
                logger.warning(
                    "[%s] Skipping query %r: %s",
                    AGENT_NAME,
                    query.query_text,
                    error_reason,
                    exc_info=True,
                )

        if not raw_metrics:
            skipped_summary = "; ".join(
                f"{item['query_text']!r}: {item['error']}" for item in skipped_queries
            )
            error = (
                "All queries failed to score."
                if skipped_queries
                else "No query metrics were collected."
            )
            if skipped_summary:
                error = f"{error} Details: {skipped_summary}"
            logger.error("[%s] %s", AGENT_NAME, error)
            return {"status": "failed", "error": error}

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
            {
                "scored_count": len(scored_queries),
                "skipped_count": len(skipped_queries),
                "skipped_queries": skipped_queries,
            },
        )

        return {"scored_queries": scored_queries}

    return visibility_scoring_node
