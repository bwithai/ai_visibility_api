"""Query Discovery Agent — generates commercially relevant AI-search queries."""

import logging
from typing import Callable
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.schemas.agents import CommercialIntent, DiscoveredQuery, PipelineState
from app.tools.dataforseo_tool import sanitize_keyword_for_google_ads
from app.agents.base import extract_tokens, log_agent_action

logger = logging.getLogger(__name__)

AGENT_NAME = "QueryDiscoveryAgent"


class QueryItem(BaseModel):
    query_text: str
    api_keyword: str = Field(
        description="Short keyword for SEO APIs: max 10 words, no punctuation, e.g. 'surfer seo vs frase'"
    )
    commercial_intent: CommercialIntent


class QueryDiscoveryOutput(BaseModel):
    queries: list[QueryItem] = Field(min_length=10, max_length=20)


def create_query_discovery_node(llm: ChatOpenAI) -> Callable[[PipelineState], dict]:
    """Create a LangGraph node that discovers 10–20 queries from a business profile."""

    structured_llm = llm.with_structured_output(QueryDiscoveryOutput, include_raw=True)

    def query_discovery_node(state: PipelineState) -> dict:
        profile = state["profile"]
        competitors_str = ", ".join(profile.competitors)

        system_prompt = (
            "You are a query discovery specialist for AI search visibility. "
            "Generate realistic natural-language questions users ask AI assistants "
            "when searching for products or services in a given industry. "
            "Focus on commercially relevant queries: comparisons, best-of lists, "
            "and high-intent informational questions."
        )
        user_prompt = (
            f"Business domain: {profile.domain}\n"
            f"Industry: {profile.industry}\n"
            f"Competitors: {competitors_str}\n\n"
            "Generate 10–20 unique queries. For each query provide:\n"
            "- query_text: full natural-language question\n"
            "- api_keyword: short keyword phrase for SEO metric APIs (max 10 words, "
            "letters/numbers/spaces only, no punctuation)\n"
            "- commercial_intent: 'comparison', 'best_of', or 'informational'"
        )

        log_agent_action(logger, AGENT_NAME, "Discovering queries", {"domain": profile.domain})

        try:
            result = structured_llm.invoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
            )
            parsed: QueryDiscoveryOutput = result["parsed"]
            raw = result["raw"]
            tokens = extract_tokens(raw)

            queries = [
                DiscoveredQuery(
                    query_uuid=str(uuid4()),
                    query_text=item.query_text,
                    api_keyword=sanitize_keyword_for_google_ads(item.api_keyword),
                    commercial_intent=item.commercial_intent,
                )
                for item in parsed.queries
            ]

            log_agent_action(
                logger,
                AGENT_NAME,
                "Queries discovered",
                {"count": len(queries)},
            )

            return {
                "queries": queries,
                "total_tokens": state.get("total_tokens", 0) + tokens,
            }
        except Exception as e:
            logger.error(f"[{AGENT_NAME}] Failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    return query_discovery_node
