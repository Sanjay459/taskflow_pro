"""
agent/tracing.py
----------------
LangSmith observability configuration for the TaskFlow Pro Support Agent.

Usage:
    from agent.tracing import configure_tracing
    configure_tracing()   # call once at process start

Controlled by .env:
    LANGSMITH_TRACING=true       # set to "true" to enable
    LANGSMITH_API_KEY=...
    LANGSMITH_PROJECT=taskflow-pro-agent
    LANGSMITH_ENDPOINT=https://api.smith.langchain.com
"""

import logging
import os

logger = logging.getLogger("taskflow_agent.tracing")


def configure_tracing(environment: str = "development") -> bool:
    """
    Configure LangSmith tracing from environment variables.

    LangSmith reads these standard env vars automatically whenever a
    LangChain/LangGraph call is made:
        LANGCHAIN_TRACING_V2   — enables tracing
        LANGCHAIN_API_KEY      — authenticates to LangSmith
        LANGCHAIN_PROJECT      — project/workspace name in LangSmith UI
        LANGCHAIN_ENDPOINT     — LangSmith API endpoint

    This function maps the project's LANGSMITH_* vars to the
    LANGCHAIN_* names that the SDK expects, then logs the result.

    Returns:
        True if tracing was enabled, False otherwise.
    """
    enabled = os.environ.get("LANGSMITH_TRACING", "false").lower() == "true"

    if not enabled:
        # Explicitly disable so stale env vars from a parent process don't leak in
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        logger.info("LangSmith tracing is DISABLED (set LANGSMITH_TRACING=true to enable).")
        return False

    api_key = os.environ.get("LANGSMITH_API_KEY", "")
    if not api_key or api_key == "your-langsmith-api-key-here":
        logger.warning(
            "LANGSMITH_TRACING=true but LANGSMITH_API_KEY is not set. "
            "Tracing will not work until a valid key is provided."
        )

    # Map to the names that langsmith / langchain SDK reads
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGCHAIN_PROJECT"] = os.environ.get(
        "LANGSMITH_PROJECT", "taskflow-pro-agent"
    )
    os.environ["LANGCHAIN_ENDPOINT"] = os.environ.get(
        "LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"
    )

    project = os.environ["LANGCHAIN_PROJECT"]
    endpoint = os.environ["LANGCHAIN_ENDPOINT"]
    logger.info(
        "LangSmith tracing ENABLED — project='%s' endpoint='%s' environment='%s'",
        project, endpoint, environment,
    )
    return True


def get_run_metadata(session_id: str = "", query_category: str = "general") -> dict:
    """
    Return a metadata dict to attach to every traced run.

    Pass this as the `metadata` kwarg to any LangChain/LangGraph invocation
    to enrich traces with custom tags visible in the LangSmith UI.

    Args:
        session_id:      The user session identifier.
        query_category:  Category inferred from the query (billing, feature, etc.)

    Returns:
        dict with keys: session_id, query_category, environment, service.
    """
    return {
        "session_id": session_id or "anonymous",
        "query_category": query_category,
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "service": "taskflow-pro-support-agent",
    }
