"""
main.py — TaskFlow Pro Support Agent API + Gradio UI
Run: uvicorn main:app --reload --port 8000

Endpoints:
  POST /api/chat          — REST chat API
  GET  /api/health        — health check
  GET  /chat              — Gradio multi-turn chat UI
"""
import os
import time
import uuid
import logging
from contextlib import asynccontextmanager
import gradio as gr
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from agent.agent import build_agent, run_agent_turn
from agent.db import init_schema
from agent.memory import AgentMemory
from agent.tracing import configure_tracing
from ui.gradio_app import build_gradio_app

# ── LangSmith tracing (toggle via LANGSMITH_TRACING=true in .env) ──
configure_tracing(environment=os.environ.get("ENVIRONMENT", "production"))

# ── Logging setup ────────────────────────────────────────────────
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("taskflow_agent")

# ── State shared across requests ──────────────────────────────────
executor = None
sessions: dict = {}   # session_id → AgentMemory


@asynccontextmanager
async def lifespan(app: FastAPI):
    global executor
    init_schema()                  # create DB tables if they don't exist
    logger.info("Building agent...")
    executor = build_agent(verbose=False)
    logger.info("Agent ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(title="TaskFlow Pro Support Agent", version="1.0.0", lifespan=lifespan)

# ── Mount Gradio UI at /chat ──────────────────────────────────────
gradio_app = build_gradio_app()
app = gr.mount_gradio_app(app, gradio_app, path="/chat")


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""


class ChatResponse(BaseModel):
    response: str
    session_id: str
    latency_ms: float


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    session_id = req.session_id or str(uuid.uuid4())
    if session_id not in sessions:
        sessions[session_id] = AgentMemory(session_id=session_id)

    memory = sessions[session_id]
    start = time.perf_counter()

    try:
        response = run_agent_turn(executor, memory, req.message, session_id=session_id)
    except Exception as exc:  # graceful failure
        logger.error("Agent error for session %s: %s", session_id, exc)
        response = (
            "I encountered an unexpected error. Your query has been logged. "
            "Please try again or contact support@taskflowpro.com."
        )

    latency_ms = (time.perf_counter() - start) * 1000
    logger.info("session=%s latency=%.1fms", session_id, latency_ms)
    return ChatResponse(response=response, session_id=session_id, latency_ms=round(latency_ms, 1))


@app.delete("/session/{session_id}")
async def end_session(session_id: str):
    if session_id in sessions:
        sessions[session_id].reset()
        del sessions[session_id]
    return {"status": "session cleared"}


@app.get("/api/health")
async def health():
    return {"status": "ok", "active_sessions": len(sessions)}