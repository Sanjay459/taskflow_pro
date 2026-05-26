# TaskFlow Pro Support Agent — High-Level Design & Flow

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Component Descriptions](#3-component-descriptions)
4. [Request Flow — REST API](#4-request-flow--rest-api)
5. [Request Flow — Gradio Chat UI](#5-request-flow--gradio-chat-ui)
6. [Agent Decision Flow (ReAct Loop)](#6-agent-decision-flow-react-loop)
7. [Data Flow & Persistence](#7-data-flow--persistence)
8. [External Integrations Flow](#8-external-integrations-flow)
9. [Safety & Guardrails Flow](#9-safety--guardrails-flow)
10. [Startup Sequence](#10-startup-sequence)

---

## 1. System Overview

TaskFlow Pro Support Agent is a multi-turn AI support agent for the TaskFlow Pro SaaS platform. It serves two interfaces — a REST API and an embedded Gradio chat UI — from a single FastAPI process. The agent uses a LangGraph ReAct loop to reason over tools, retrieves answers from a Pinecone vector knowledge base, and persists all conversation state to a database (Neon PostgreSQL in production, SQLite in development).

**Key capabilities:**
- Semantic search over product documentation (Pinecone RAG)
- Ticket creation, status check, and human escalation (tool use)
- Multi-turn, session-scoped conversation memory (DB-backed)
- Prompt injection immunity, PII masking, language detection
- Slack notifications and Google Sheets audit logging
- LangSmith observability for every agent run

---

## 2. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                              │
│                                                              │
│   Browser / cURL           Browser                          │
│   POST /api/chat           GET /chat                        │
└────────────┬───────────────────────┬────────────────────────┘
             │                       │
             ▼                       ▼
┌──────────────────────────────────────────────────────────────┐
│                  FastAPI Application  (main.py)              │
│                                                              │
│   /api/chat  ──► ChatRequest handler                        │
│   /api/health ─► health check                               │
│   /chat  ──────► Gradio Blocks UI (gr.mount_gradio_app)     │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                    AGENT LAYER  (agent/)                     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Guardrails (pre-check)                              │    │
│  │  • check_safety()  • check_injection()              │    │
│  │  • detect_language()  • mask_pii()                  │    │
│  └───────────────────────┬─────────────────────────────┘    │
│                          │ (safe input only)                 │
│  ┌───────────────────────▼─────────────────────────────┐    │
│  │  AgentMemory  (memory.py)                            │    │
│  │  • Loads session history from DB                    │    │
│  │  • Sliding window (last 10 turns)                   │    │
│  │  • Escalation counter                               │    │
│  └───────────────────────┬─────────────────────────────┘    │
│                          │                                   │
│  ┌───────────────────────▼─────────────────────────────┐    │
│  │  LangGraph ReAct Agent  (agent.py)                  │    │
│  │  • Model: GPT-4o (ChatOpenAI)                       │    │
│  │  • System prompt: identity, rules, language         │    │
│  │  • Tool selection loop (Reason → Act → Observe)     │    │
│  └──┬──────────────────┬───────────────────┬───────────┘    │
│     │                  │                   │                 │
│     ▼                  ▼                   ▼                 │
│  search_kb       check_ticket      create_ticket /          │
│  (retriever.py)  (tools.py + db)   escalate_to_human        │
└────────────────────────────────────────────────────────────-─┘
         │                   │                    │
         ▼                   ▼                    ▼
┌─────────────┐   ┌─────────────────┐   ┌────────────────────┐
│  Pinecone   │   │  Database       │   │  External Services │
│  Vector DB  │   │  (Neon / SQLite)│   │                    │
│             │   │  • tickets      │   │  • Slack           │
│  87 chunks  │   │  • interactions │   │  • Google Sheets   │
│  1536-dim   │   │  • message_store│   │  • LangSmith       │
│  cosine     │   │                 │   │  • OpenAI API      │
└─────────────┘   └─────────────────┘   └────────────────────┘
```

---

## 3. Component Descriptions

### 3.1 `main.py` — Application Entry Point
- Bootstraps the FastAPI application with a lifespan hook
- Calls `init_schema()` on startup to create DB tables
- Builds the singleton agent executor (`build_agent()`)
- Mounts the Gradio app at `/chat` via `gr.mount_gradio_app()`
- Maintains a `sessions` dict mapping `session_id → AgentMemory` for REST callers

### 3.2 `ui/gradio_app.py` — Gradio Chat Interface
- `gr.Blocks` layout with a `gr.Chatbot` component (Gradio 6.0 messages format)
- Session state is a `gr.State(AgentMemory)` instance — one per browser tab
- `respond()` calls `run_agent_turn()` and appends `{"role", "content"}` dicts to history
- Clear button calls `memory.reset()` to wipe DB history for the session

### 3.3 `agent/agent.py` — LangGraph ReAct Agent
- Assembles the four tools (KB search, ticket check, ticket create, escalate)
- Creates a `create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)` graph
- Wraps the graph in `_AgentWrapper` for a clean `invoke()` interface
- `run_agent_turn()` orchestrates: guardrail check → history load → agent invoke → memory save → audit log

### 3.4 `agent/tools.py` — Tool Definitions
| Tool | Description |
|---|---|
| `search_knowledge_base` | LangChain `create_retriever_tool` over Pinecone retriever |
| `check_ticket_status` | Looks up ticket by ID from the `tickets` DB table |
| `create_support_ticket` | Writes a new ticket to DB + fires Slack notification |
| `escalate_to_human` | Generates escalation ID + fires Slack notification |

### 3.5 `agent/retriever.py` — Pinecone Vector Store
- Loads `.txt` files from `data/product_docs/` using `DirectoryLoader`
- Splits into 500-char chunks with 50-char overlap (`RecursiveCharacterTextSplitter`)
- Embeds with `text-embedding-3-small` (1536 dimensions)
- Upserts to Pinecone only when the index is empty (idempotent)
- Returns a LangChain `VectorStoreRetriever` (top-4 results, cosine similarity)

### 3.6 `agent/memory.py` — Session Memory
- `AgentMemory` wraps `SQLChatMessageHistory` with a session-scoped sliding window
- Persists to `message_store` table in the configured database
- Window size: last 10 turns (20 messages) passed to the LLM per invocation
- Tracks `unresolved_turns` for auto-escalation logic (ephemeral — resets on restart)

### 3.7 `agent/guardrails.py` — Safety Layer
- `check_safety()` — blocks policy-violating requests (hacking, legal threats, account deletion)
- `check_injection()` — detects 5 categories of prompt injection / jailbreak attempts
- `detect_language()` — identifies user language using `langdetect` (40+ languages)
- `mask_pii()` — redacts credit card numbers, emails, phone numbers before logging

### 3.8 `agent/db.py` — Database Layer
- `get_engine()` singleton — SQLite (dev) or Neon PostgreSQL (prod)
- `init_schema()` — creates `tickets`, `interactions`, `message_store` tables
- `get_ticket()` / `save_ticket()` — ticket CRUD
- `log_interaction()` — writes audit record (session, user input, response, language, category, latency)

### 3.9 `agent/tracing.py` — LangSmith Observability
- Configures `LANGCHAIN_TRACING_V2` and project name from environment variables
- `get_run_metadata()` returns tags and metadata dict injected into each agent invocation
- Every `run_agent_turn()` call produces a full trace in LangSmith with tool calls, token counts, and latency

### 3.10 `agent/slack_notifier.py` — Slack Integration
- `notify_ticket_created()` — posts a formatted message to `SLACK_ESCALATION_CHANNEL` when a ticket is created
- `notify_escalation()` — posts an escalation alert with ID and context summary
- Graceful no-op if `SLACK_BOT_TOKEN` or `SLACK_ESCALATION_CHANNEL` are unset

### 3.11 `agent/sheets_logger.py` — Google Sheets Audit Log
- `log_turn()` — appends one row per conversation turn to a Google Sheet
- Columns: timestamp, session ID, user input, agent response, category, language, latency, resolution status
- Graceful no-op if Google credentials are unset

---

## 4. Request Flow — REST API

```
Client
  │
  │  POST /api/chat  {"message": "...", "session_id": "abc"}
  │
  ▼
FastAPI handler (main.py)
  │
  ├─ Validate: message not empty
  ├─ Resolve or create session_id
  ├─ Load or create AgentMemory for session
  │
  └─► run_agent_turn(executor, memory, message, session_id)
        │
        ├─ 1. check_safety(message)       ──► BLOCKED? return safety message
        ├─ 2. check_injection(message)    ──► BLOCKED? return rejection message
        ├─ 3. detect_language(message)    ──► language tag (e.g. "Spanish")
        ├─ 4. memory.get_history()        ──► last N messages from DB
        ├─ 5. executor.invoke(input, chat_history, language)
        │       │
        │       └─► LangGraph ReAct loop (see Section 6)
        │
        ├─ 6. memory.add_interaction(message, response)  ──► write to DB
        ├─ 7. log_interaction(...)                        ──► write to interactions table
        ├─ 8. log_turn(...)                               ──► write to Google Sheets (async)
        │
        └─► return response string
  │
  ▼
ChatResponse {"response": "...", "session_id": "abc", "latency_ms": 1243}
```

---

## 5. Request Flow — Gradio Chat UI

```
Browser (GET /chat)
  │
  ▼
Gradio Blocks UI (ui/gradio_app.py)
  │
  │  User types message → clicks Send
  │
  ▼
respond(user_message, history, session_memory)
  │
  ├─ Skip if message is blank
  ├─ Get executor from _get_executor() singleton
  │
  └─► run_agent_turn(executor, session_memory, message)
        │
        └─► [same guardrails → memory → ReAct → logging pipeline as REST]
  │
  ├─ Append {"role": "user", "content": ...}
  │         {"role": "assistant", "content": ...}
  │         to history list
  │
  ▼
Updated Chatbot display + cleared input box
```

---

## 6. Agent Decision Flow (ReAct Loop)

```
System Prompt + Chat History + User Message
  │
  ▼
GPT-4o (Reason)
  │
  ├── "I need to search the knowledge base"
  │       └─► search_knowledge_base(query)
  │               └─► Pinecone similarity search → top 4 chunks
  │               └─► chunks returned as tool observation
  │
  ├── "User gave a ticket ID — check it"
  │       └─► check_ticket_status(ticket_id)
  │               └─► DB lookup → ticket JSON or not-found message
  │
  ├── "Self-service failed — create a ticket"
  │       └─► create_support_ticket(subject, description, priority)
  │               └─► Write to DB tickets table
  │               └─► Slack notification (notify_ticket_created)
  │               └─► Return ticket ID + next steps
  │
  ├── "Issue unresolvable / user asked for human"
  │       └─► escalate_to_human(reason, context_summary)
  │               └─► Generate ESC-XXXXXX ID
  │               └─► Slack escalation alert (notify_escalation)
  │               └─► Return escalation ID + ETA
  │
  └── "I have enough information to answer directly"
          └─► Final answer (no tool call)
  │
  ▼
GPT-4o (Observe tool result → Reason again if needed)
  │
  ▼
Final response string returned to run_agent_turn()
```

---

## 7. Data Flow & Persistence

```
┌─────────────────────────────────────────────────────┐
│             Database  (Neon PostgreSQL / SQLite)     │
│                                                      │
│  Table: message_store                                │
│  ├── session_id  (text)                             │
│  ├── id          (integer, PK)                      │
│  ├── type        ("human" | "ai")                   │
│  └── content     (text)                             │
│  Managed by: SQLChatMessageHistory (LangChain)       │
│                                                      │
│  Table: tickets                                      │
│  ├── ticket_id   (text, PK)  e.g. TF-A1B2C3        │
│  ├── subject     (text, max 200 chars)              │
│  ├── description (text, max 1000 chars, no PII)     │
│  ├── priority    (low | medium | high | critical)   │
│  ├── status      (open | in_progress | resolved)    │
│  └── created_at  (ISO 8601 UTC timestamp)           │
│  Managed by: agent/db.py                            │
│                                                      │
│  Table: interactions                                 │
│  ├── id          (integer, PK, autoincrement)       │
│  ├── session_id  (text)                             │
│  ├── user_input  (text, PII masked)                 │
│  ├── ai_response (text, PII masked)                 │
│  ├── language    (text)                             │
│  ├── category    (text)                             │
│  ├── latency_ms  (float)                            │
│  └── created_at  (ISO 8601 UTC timestamp)           │
│  Managed by: agent/db.py                            │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│             Pinecone Vector Index  (taskflow-kb)     │
│                                                      │
│  • ~87 vectors (500-char document chunks)           │
│  • 1536 dimensions  (text-embedding-3-small)        │
│  • Metric: cosine similarity                        │
│  • Serverless (AWS us-east-1)                       │
│  • Auto-created on first start; idempotent upsert   │
└─────────────────────────────────────────────────────┘
```

---

## 8. External Integrations Flow

```
Agent turn completes
  │
  ├── Tool: create_support_ticket()
  │       └─► slack_notifier.notify_ticket_created()
  │               ├── SLACK_BOT_TOKEN set?  ──No──► silent no-op
  │               └── Yes → POST chat.postMessage to #support-escalations
  │                         {"ticket_id", "subject", "priority"}
  │
  ├── Tool: escalate_to_human()
  │       └─► slack_notifier.notify_escalation()
  │               ├── SLACK_BOT_TOKEN set?  ──No──► silent no-op
  │               └── Yes → POST chat.postMessage to #support-escalations
  │                         {"escalation_id", "reason", "context_summary"}
  │
  ├── Every turn: log_turn()  (sheets_logger.py)
  │       ├── GOOGLE_SHEETS_ID set?  ──No──► silent no-op
  │       └── Yes → gspread append_row()
  │                 [timestamp, session_id, user_input, response,
  │                  category, language, latency_ms, resolution]
  │
  └── Every turn: LangSmith trace (tracing.py)
          ├── LANGSMITH_TRACING=true?  ──No──► no-op
          └── Yes → full ReAct trace appears in smith.langchain.com
                    includes: tool calls, LLM inputs/outputs,
                    token counts, latency, tags, session metadata
```

---

## 9. Safety & Guardrails Flow

```
Incoming user message
  │
  ▼
check_safety(message)
  ├── Matches UNSAFE_PATTERNS?  ──Yes──► return "BLOCKED: <reason>"  (no LLM call)
  └── No
  │
  ▼
check_injection(message)
  ├── Matches INJECTION_PATTERNS?  ──Yes──► return rejection response  (no LLM call)
  └── No
  │
  ▼
detect_language(message)
  └── langdetect → language string (e.g. "Spanish")
      Fallback: "English" if detection fails
  │
  ▼
Agent invoked with language tag injected into system prompt
  │
  ▼
Response generated
  │
  ▼
mask_pii(user_input)  +  mask_pii(ai_response)
  └── Redact: credit cards, emails, phone numbers → "[REDACTED]"
  │
  ▼
log_interaction(masked_input, masked_response, ...)  →  DB interactions table
log_turn(masked_input, masked_response, ...)          →  Google Sheets
```

**Guardrail Categories:**

| Check | Patterns | Blocked Before LLM? |
|---|---|---|
| Unsafe content | Hacking, legal threats, account deletion | Yes |
| Prompt injection | Instruction override, role hijack, DAN-style | Yes |
| PII in logs | Credit cards, emails, phone numbers | Masked (not blocked) |
| Language detection | 40+ languages | N/A — informs response language |

---

## 10. Startup Sequence

```
uvicorn main:app --host 0.0.0.0 --port $PORT
  │
  ▼
1. load_dotenv()                        — load environment variables
2. configure_tracing()                  — set LANGCHAIN_TRACING_V2 env vars
3. FastAPI lifespan hook starts
  │
  ├─ 4. init_schema()
  │       └─► get_engine()             — connect to Neon or create SQLite
  │       └─► CREATE TABLE IF NOT EXISTS tickets / interactions / message_store
  │
  ├─ 5. build_agent()
  │       ├─► get_retriever()
  │       │     ├─► Pinecone.connect()
  │       │     ├─► _ensure_index()    — create index if missing
  │       │     ├─► load + split docs  — from data/product_docs/
  │       │     ├─► embed + upsert     — skipped if index already has vectors
  │       │     └─► return retriever
  │       ├─► create_retriever_tool(retriever)
  │       ├─► [check_ticket_status, create_support_ticket, escalate_to_human]
  │       ├─► ChatOpenAI(model="gpt-4o")
  │       └─► create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)
  │
  └─ 6. build_gradio_app()             — mount Gradio Blocks at /chat
  │
  ▼
Server ready — accepting requests on port 8000
```

**Typical startup times:**

| Scenario | Duration |
|---|---|
| First ever start (empty Pinecone index, upsert required) | 45–90 seconds |
| Subsequent starts (index populated, upsert skipped) | 5–10 seconds |
| Render cold start after 15 min inactivity | ~30 seconds |
