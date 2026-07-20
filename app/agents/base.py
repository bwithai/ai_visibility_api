from langchain_openai import ChatOpenAI
from app.core.config import settings
import logging
import json
from typing import Any, Dict, Optional


MAX_KEYWORD_CHARS = 80
MAX_KEYWORD_WORDS = 10


def get_llm() -> ChatOpenAI:
    """Get a configured LLM instance.
    Returns:
        ChatOpenAI instance
    """
    return ChatOpenAI(
        model=settings.DEFAULT_MODEL,
        temperature=settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
        api_key=settings.OPENAI_API_KEY
    )


def extract_tokens(response: Any) -> int:
    """Extract total token usage from a LangChain LLM response."""
    usage = getattr(response, "usage_metadata", None)
    if usage:
        return int(usage.get("total_tokens", 0) or 0)
    token_usage = getattr(response, "response_metadata", {}).get("token_usage", {})
    return int(token_usage.get("total_tokens", 0) or 0)


def log_agent_action(logger: logging.Logger, agent_name: str, action: str, details: Optional[Dict[str, Any]] = None):
    """Log an agent action with structured information.
    
    Args:
        logger: Logger instance
        agent_name: Name of the agent performing the action
        action: Description of the action
        details: Optional dictionary with additional details
    """
    message = f"[{agent_name}] {action}"
    if details:
        message += f" | Details: {json.dumps(details, indent=2)}"
    logger.info(message)
