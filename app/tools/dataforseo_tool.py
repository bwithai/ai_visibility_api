"""DataForSEO API tools for keyword metrics and AI visibility."""

import base64
import logging
import re
from typing import Any
from urllib.parse import urlparse

import requests
from langchain_core.tools import tool

from app.core.config import settings

logger = logging.getLogger(__name__)

DATAFORSEO_BASE_URL = "https://api.dataforseo.com/v3"
KEYWORDS_SEARCH_VOLUME_URL = (
    f"{DATAFORSEO_BASE_URL}/keywords_data/google_ads/search_volume/live"
)
LLM_MENTIONS_SEARCH_URL = (
    f"{DATAFORSEO_BASE_URL}/ai_optimization/llm_mentions/search/live"
)

MAX_KEYWORD_CHARS = 80
MAX_KEYWORD_WORDS = 10
US_LOCATION_CODE = 2840


def _normalize_domain(domain: str) -> str:
    """Normalize domain to bare hostname (no scheme/www)."""
    value = domain.strip().lower()
    if "://" in value:
        value = urlparse(value).netloc or value
    if value.startswith("www."):
        value = value[4:]
    return value.rstrip("/")


def _domain_matches(candidate: str, target_domain: str) -> bool:
    """Return True when candidate hostname matches the target domain."""
    if not candidate:
        return False
    candidate = _normalize_domain(candidate)
    target = _normalize_domain(target_domain)
    return candidate == target or candidate.endswith(f".{target}")


def sanitize_keyword_for_google_ads(keyword: str) -> str:
    """Normalize a natural-language query for Google Ads Keywords API limits."""
    cleaned = keyword.strip()
    for char in "?!:;,.'\"()[]{}""''":
        cleaned = cleaned.replace(char, " ")
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    words = cleaned.split()[:MAX_KEYWORD_WORDS]
    cleaned = " ".join(words)[:MAX_KEYWORD_CHARS]
    if not cleaned:
        raise ValueError(f"Keyword empty after sanitization: {keyword!r}")
    return cleaned


def _get_auth_header() -> dict[str, str]:
    if not settings.DATAFORSEO_LOGIN or not settings.DATAFORSEO_PASSWORD:
        raise ValueError(
            "DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD must be set in .env "
            "for visibility scoring."
        )
    credentials = f"{settings.DATAFORSEO_LOGIN}:{settings.DATAFORSEO_PASSWORD}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {encoded}", "Content-Type": "application/json"}


def _post_dataforseo(url: str, payload: list[dict[str, Any]]) -> dict[str, Any]:
    """POST to DataForSEO and return parsed JSON or raise with API detail."""
    response = requests.post(
        url,
        headers=_get_auth_header(),
        json=payload,
        timeout=120,
    )
    if not response.ok:
        detail = response.text.strip() or response.reason
        raise RuntimeError(f"DataForSEO HTTP {response.status_code}: {detail}")

    data = response.json()
    if data.get("status_code") != 20000:
        raise RuntimeError(
            f"DataForSEO API error: {data.get('status_message', 'Unknown error')}"
        )

    tasks = data.get("tasks", [])
    if not tasks or tasks[0].get("status_code") != 20000:
        task_msg = tasks[0].get("status_message") if tasks else "No tasks returned"
        raise RuntimeError(f"DataForSEO task error: {task_msg}")

    return data


DEFAULT_KEYWORD_DIFFICULTY = 50

_COMPETITION_TO_INDEX = {"LOW": 25, "MEDIUM": 50, "HIGH": 75}


def _competition_label_to_index(competition: str | None) -> int | None:
    if not competition:
        return None
    return _COMPETITION_TO_INDEX.get(competition.strip().upper())


KeywordMetrics = dict[str, int | None | str]


def _parse_google_ads_item(
    item: dict[str, Any], api_keyword: str, label: str
) -> KeywordMetrics:
    """Parse search volume and difficulty from one Google Ads API result item."""
    search_volume_raw = item.get("search_volume")
    search_volume = int(search_volume_raw) if search_volume_raw is not None else None

    competition_index = item.get("competition_index")
    if competition_index is not None:
        difficulty = int(competition_index)
        difficulty_source = "google_ads"
    else:
        competition_mapped = _competition_label_to_index(item.get("competition"))
        if competition_mapped is not None:
            difficulty = competition_mapped
            difficulty_source = "google_ads"
        else:
            difficulty = DEFAULT_KEYWORD_DIFFICULTY
            difficulty_source = "estimated"
            logger.warning(
                "No keyword difficulty from Google Ads for %r "
                "(original query: %r); using default %s.",
                api_keyword,
                label,
                DEFAULT_KEYWORD_DIFFICULTY,
            )

    if not 0 <= difficulty <= 100:
        raise RuntimeError(f"Keyword difficulty out of range (0-100): {difficulty}")

    return {
        "search_volume": search_volume,
        "difficulty": difficulty,
        "difficulty_source": difficulty_source,
    }


def fetch_keyword_metrics_batch(
    keywords: list[str],
    *,
    labels: dict[str, str] | None = None,
) -> dict[str, KeywordMetrics]:
    """Fetch search volume and difficulty for multiple keywords in one API call."""
    if not keywords:
        return {}

    labels = labels or {}
    unique_keywords = list(dict.fromkeys(keywords))

    data = _post_dataforseo(
        KEYWORDS_SEARCH_VOLUME_URL,
        [
            {
                "keywords": unique_keywords,
                "location_code": US_LOCATION_CODE,
                "language_code": "en",
            }
        ],
    )

    results = data["tasks"][0].get("result") or []
    if not results:
        raise RuntimeError(
            "Google Ads Keywords API returned no data for batch keyword request."
        )

    metrics_by_keyword: dict[str, KeywordMetrics] = {}
    for item in results:
        api_keyword = item.get("keyword")
        if not api_keyword:
            continue
        label = labels.get(api_keyword, api_keyword)
        metrics_by_keyword[api_keyword] = _parse_google_ads_item(
            item, api_keyword, label
        )

    missing = [kw for kw in unique_keywords if kw not in metrics_by_keyword]
    if missing:
        raise RuntimeError(
            "Google Ads Keywords API returned no data for keyword(s): "
            + ", ".join(repr(kw) for kw in missing)
        )

    return metrics_by_keyword


def fetch_keyword_metrics(
    keyword: str, *, original_query: str | None = None
) -> KeywordMetrics:
    """Fetch search volume and difficulty for a single keyword via Google Ads API."""
    api_keyword = sanitize_keyword_for_google_ads(keyword)
    label = original_query or keyword
    if api_keyword != keyword.strip():
        logger.info(
            "Sanitized keyword for Google Ads API: %r -> %r", keyword, api_keyword
        )

    metrics_by_keyword = fetch_keyword_metrics_batch(
        [api_keyword], labels={api_keyword: label}
    )
    return metrics_by_keyword[api_keyword]


def _find_domain_in_item(
    item: dict[str, Any], target_domain: str
) -> tuple[int | None, str] | None:
    """Return (position, reason) if target domain appears in an LLM mention item."""
    for source in item.get("sources") or []:
        if _domain_matches(source.get("domain", ""), target_domain):
            position = source.get("position")
            cited = _normalize_domain(source.get("domain", ""))
            return (
                int(position) if position is not None else None,
                f"Cited in Google AI Overview sources at position {position} ({cited})",
            )

    for result in item.get("search_results") or []:
        if _domain_matches(result.get("domain", ""), target_domain):
            position = result.get("position")
            cited = _normalize_domain(result.get("domain", ""))
            return (
                int(position) if position is not None else None,
                f"Present in AI Overview search results at position {position} ({cited})",
            )

    for brand in item.get("brand_entities") or []:
        title = brand.get("title") or ""
        if _domain_matches(title, target_domain) or target_domain.split(".")[0] in title.lower():
            position = brand.get("position")
            return (
                int(position) if position is not None else None,
                f"Mentioned as brand entity at position {position} ({title})",
            )

    return None


def fetch_ai_visibility(query_text: str, domain: str) -> dict[str, Any]:
    """Check AI visibility via DataForSEO LLM Mentions Search API (Google AI Overview)."""
    target_domain = _normalize_domain(domain)
    query = query_text.strip()
    if not query:
        raise ValueError("Query text is required for AI visibility check.")

    payload = [
        {
            "location_code": US_LOCATION_CODE,
            "language_code": "en",
            "platform": "google",
            "target": [
                {
                    "keyword": query,
                    "search_scope": ["question"],
                    "match_type": "word_match",
                },
                {
                    "domain": target_domain,
                    "search_filter": "include",
                    "search_scope": ["any"],
                    "include_subdomains": True,
                },
            ],
            "limit": 10,
        }
    ]

    data = _post_dataforseo(LLM_MENTIONS_SEARCH_URL, payload)
    result_block = (data["tasks"][0].get("result") or [{}])[0]
    items = result_block.get("items") or []
    total_count = int(result_block.get("total_count") or 0)
    ai_search_volume = items[0].get("ai_search_volume") if items else None

    if total_count == 0 or not items:
        return {
            "domain_visible": False,
            "visibility_position": None,
            "visibility_reason": (
                "DataForSEO LLM Mentions API: no Google AI Overview records found "
                f"for query {query!r}."
            ),
            "ai_search_volume": ai_search_volume,
        }

    best_position: int | None = None
    reasons: list[str] = []

    for item in items:
        match = _find_domain_in_item(item, target_domain)
        if match is None:
            continue
        position, reason = match
        reasons.append(reason)
        if position is not None and (best_position is None or position < best_position):
            best_position = position

    if reasons:
        return {
            "domain_visible": True,
            "visibility_position": best_position,
            "visibility_reason": "; ".join(reasons),
            "ai_search_volume": ai_search_volume,
        }

    return {
        "domain_visible": False,
        "visibility_position": None,
        "visibility_reason": (
            f"DataForSEO LLM Mentions API: {total_count} AI Overview record(s) exist "
            f"for this query, but {target_domain} is not cited in sources, search "
            "results, or brand entities."
        ),
        "ai_search_volume": ai_search_volume,
    }


@tool
def get_keyword_metrics(keyword: str) -> dict[str, Any]:
    """Get real search volume and competitive difficulty for a keyword via DataForSEO."""
    return fetch_keyword_metrics(keyword)
