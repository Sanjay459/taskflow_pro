"""
agent/memory.py
---------------
Session-scoped conversation memory for the TaskFlow Pro Support Agent.

Conversation history is persisted in the configured database
(SQLite for local dev, Neon PostgreSQL for production) via
SQLChatMessageHistory — it survives server restarts and re-deploys.

The sliding window (window_k) caps how many turns are passed to the LLM
as context per invocation, keeping prompt sizes manageable.
"""

import uuid
from datetime import datetime, timezone

from langchain_community.chat_message_histories import SQLChatMessageHistory

from agent.db import get_engine


class AgentMemory:
    """
    Per-session conversation memory backed by the configured database.
    Also tracks ephemeral escalation state (resets on server restart — intentional).
    """

    def __init__(self, session_id: str = "", window_k: int = 10):
        self.session_id: str = session_id or str(uuid.uuid4())
        self._window_k = window_k
        self.unresolved_turns: int = 0
        self._session_start = datetime.now(timezone.utc).isoformat()

        # DB-backed message store — creates 'message_store' table automatically
        self._chat_history = SQLChatMessageHistory(
            session_id=self.session_id,
            connection=get_engine(),
        )

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------

    def add_interaction(self, user_input: str, ai_response: str) -> None:
        """Append a user/AI message pair to the DB-backed history."""
        self._chat_history.add_user_message(user_input)
        self._chat_history.add_ai_message(ai_response)

    def get_history(self) -> list:
        """Return the last window_k turns as a LangChain message list."""
        messages = self._chat_history.messages
        cap = self._window_k * 2
        return messages[-cap:] if len(messages) > cap else messages

    def reset(self) -> None:
        """Clear all stored history for this session."""
        self._chat_history.clear()
        self.unresolved_turns = 0

    # ------------------------------------------------------------------
    # Escalation tracking (ephemeral — resets on server restart)
    # ------------------------------------------------------------------

    def mark_unresolved(self) -> bool:
        """Increment counter. Returns True when auto-escalation threshold (≥2) reached."""
        self.unresolved_turns += 1
        return self.unresolved_turns >= 2

    def mark_resolved(self) -> None:
        self.unresolved_turns = 0
