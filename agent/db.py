"""
agent/db.py
-----------
Database layer — single source of truth for structured persistence.

  Production : Neon serverless PostgreSQL
               DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
  Local dev  : SQLite (zero setup, auto-created in project root)
               DATABASE_URL=sqlite:///taskflow.db  OR leave DATABASE_URL unset

Tables (created automatically on first start):
  tickets       — support ticket records (replaces the in-memory dict)
  interactions  — per-turn audit log     (replaces the JSONL flat file)
  message_store — managed by SQLChatMessageHistory (conversation history)
"""

import logging
import os
import re
from datetime import datetime, timezone

from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text, create_engine
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_SQLITE = f"sqlite:///{os.path.join(_PROJECT_ROOT, 'taskflow.db')}"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def get_database_url() -> str:
    """
    Resolve DATABASE_URL from the environment.
    Normalises  postgres://  →  postgresql+psycopg2://  for SQLAlchemy.
    Falls back to a local SQLite file when DATABASE_URL is not set.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return _DEFAULT_SQLITE
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg2" not in url:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the module-level SQLAlchemy engine (lazy-initialised singleton)."""
    global _engine
    if _engine is None:
        url = get_database_url()
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
        safe = url.split("@")[-1] if "@" in url else url
        logger.info("DB engine ready: %s", safe)
    return _engine


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_metadata = MetaData()

tickets_table = Table(
    "tickets", _metadata,
    Column("ticket_id",   String(20),  primary_key=True),
    Column("subject",     String(200), nullable=False),
    Column("description", Text),
    Column("priority",    String(20),  default="medium"),
    Column("status",      String(20),  default="open"),
    Column("created_at",  String(30),  nullable=False),
)

interactions_table = Table(
    "interactions", _metadata,
    Column("id",          Integer,    primary_key=True, autoincrement=True),
    Column("timestamp",   String(30), nullable=False),
    Column("session_id",  String(100)),
    Column("category",    String(50)),
    Column("language",    String(50)),
    Column("user_query",  Text),
    Column("resolution",  String(30)),
    Column("ticket_id",   String(20)),
    Column("latency_ms",  Float),
)


def init_schema() -> None:
    """Create all application tables if they do not already exist."""
    _metadata.create_all(get_engine())
    logger.info("DB schema ready.")


# ---------------------------------------------------------------------------
# Ticket operations
# ---------------------------------------------------------------------------

def get_ticket(ticket_id: str) -> dict | None:
    """Fetch a ticket by ID. Returns a dict or None."""
    with get_engine().connect() as conn:
        row = conn.execute(
            tickets_table.select().where(
                tickets_table.c.ticket_id == ticket_id.strip().upper()
            )
        ).mappings().first()
    return dict(row) if row else None


def save_ticket(ticket: dict) -> None:
    """Persist a new ticket record to the database."""
    with get_engine().begin() as conn:
        conn.execute(tickets_table.insert().values(**ticket))


# ---------------------------------------------------------------------------
# Interaction audit log
# ---------------------------------------------------------------------------

_TICKET_RE = re.compile(r"\bTF-[A-Z0-9]{6}\b")
_ESC_RE    = re.compile(r"\bESC-[A-Z0-9]{6}\b")


def _infer_resolution(response: str) -> tuple[str, str]:
    m = _TICKET_RE.search(response)
    if m:
        return "ticket_created", m.group(0)
    m = _ESC_RE.search(response)
    if m:
        return "escalated", m.group(0)
    return "responded", ""


def log_interaction(
    session_id: str,
    category: str,
    language: str,
    user_query: str,        # should already be PII-masked before calling
    response: str,
    latency_ms: float,
) -> None:
    """
    Append one interaction row to the interactions table.
    Fire-and-forget: failures are logged as warnings and never propagate.
    """
    resolution, ref_id = _infer_resolution(response)
    try:
        with get_engine().begin() as conn:
            conn.execute(interactions_table.insert().values(
                timestamp  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                session_id = session_id or "anonymous",
                category   = category,
                language   = language,
                user_query = user_query[:200],
                resolution = resolution,
                ticket_id  = ref_id,
                latency_ms = round(latency_ms, 1),
            ))
    except Exception as exc:
        logger.warning("DB interaction log failed: %s", exc)
