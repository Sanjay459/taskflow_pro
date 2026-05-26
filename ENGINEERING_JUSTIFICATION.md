# TaskFlow Pro Support Agent — Engineering & Product Justification

Design decisions, tradeoffs, safety approach, and deployment assumptions.

---

## 1. Design Decisions

### 1.1 LangGraph ReAct Agent over a Simple Chain

A `create_react_agent` (LangGraph) was chosen over a plain `LLMChain` or `ConversationalRetrievalChain` because the support use-case requires **conditional tool dispatch**: the agent must decide at runtime whether to search the knowledge base, create a ticket, check ticket status, or escalate — sometimes chaining multiple steps. A simple chain can only follow a fixed sequence and cannot reason about which tool to invoke. LangGraph's ReAct loop (Reason → Act → Observe) handles this naturally while keeping the control flow transparent and traceable via LangSmith.

### 1.2 Pinecone as Primary Vector Store (ChromaDB as Local Fallback)

Pinecone serverless was chosen for production because it:
- Scales to millions of vectors with sub-100ms query latency
- Requires no infrastructure management (serverless billing)
- Persists across Render's ephemeral filesystem restarts

ChromaDB is retained as a local-dev fallback so the project runs fully offline without a Pinecone key, which lowers the onboarding friction for contributors and reviewers.

### 1.3 FastAPI + Gradio in a Single Process

Both the REST API (`/api/chat`) and the Gradio chat UI (`/chat`) are mounted on the same FastAPI application via `gr.mount_gradio_app()`. This decision was made to:
- Keep the Render deployment to **one Web Service** (one dyno, one bill)
- Share the agent executor and database connection pool across both interfaces
- Avoid cross-origin complexity that would arise if they were separate services

The tradeoff is that a Gradio UI crash can affect the API; in a production system these would be split into separate services behind a load balancer.

### 1.4 Neon PostgreSQL for Persistence (SQLite as Local Fallback)

`SQLChatMessageHistory` with a SQLAlchemy engine was chosen for three tables: `message_store` (conversation history), `tickets` (support records), and `interactions` (audit log). Neon was selected because:
- It is serverless and free-tier, matching the Render deployment model
- It supports `?sslmode=require`, satisfying encryption-in-transit requirements
- Auto-wakes from idle (2-second cold start acceptable for demo scale)

SQLite is the automatic fallback when `DATABASE_URL` is unset, so local development requires no external services.

### 1.5 Modular Agent Architecture

The `agent/` package is split into single-responsibility modules:

| Module | Responsibility |
|---|---|
| `agent.py` | LangGraph graph construction, `run_agent_turn()` |
| `tools.py` | Tool definitions and DB-backed ticket operations |
| `memory.py` | `AgentMemory` — sliding-window `SQLChatMessageHistory` |
| `guardrails.py` | Injection detection, language detection, PII masking |
| `retriever.py` | Pinecone index management and retriever factory |
| `tracing.py` | LangSmith configuration |
| `slack_notifier.py` | Slack notifications (graceful no-op if unconfigured) |
| `sheets_logger.py` | Google Sheets audit log (graceful no-op if unconfigured) |
| `db.py` | Engine singleton, schema init, CRUD helpers |

This separation means each module can be tested, swapped, or disabled independently. Integrations (Slack, Sheets) activate only when their environment variables are present — zero code changes required.

### 1.6 GPT-4o as the LLM

GPT-4o was chosen over GPT-3.5-turbo or smaller open-source models because:
- Multi-step tool calling accuracy is significantly higher
- It handles ambiguous user intent well (e.g. "nothing works" → escalate vs. search KB)
- Its context window (128k tokens) comfortably holds the sliding-window conversation history plus tool outputs

Cost is the main tradeoff; for a high-volume production system, a fine-tuned GPT-4o-mini would be evaluated first.

---

## 2. Tradeoffs

| Decision | Chosen | Alternative | Tradeoff accepted |
|---|---|---|---|
| Agent framework | LangGraph ReAct | Plain `LLMChain` | More complex setup; necessary for multi-tool branching |
| Vector store | Pinecone serverless | ChromaDB | Pinecone survives ephemeral filesystems; higher operational dependency |
| LLM | GPT-4o | GPT-3.5-turbo / GPT-4o-mini | Higher cost; better tool selection and multi-turn reasoning |
| Memory | SQLChatMessageHistory (DB-backed) | In-memory list | DB-backed survives restarts and supports concurrent sessions; minor latency overhead per turn |
| Deployment | Single Render Web Service | Microservices | Simpler ops for a capstone; production would split API and UI |
| Database | Neon PostgreSQL + SQLite fallback | Pure PostgreSQL | SQLite fallback eliminates external dependency for local dev |
| Observability | LangSmith | Custom JSONL logging only | LangSmith provides per-step traces, token counts, and latency without custom instrumentation |
| Auth & secrets | Environment variables | Vault / AWS SSM | Env vars are standard for PaaS; a production system would use a dedicated secrets manager |
| Slack / Sheets | Optional integrations (env-var activated) | Always-on | Zero-config degradation — the agent works fully without these credentials |

---

## 3. Safety Approach

### 3.1 Input Guardrails (Pre-Agent)

Every user message passes through `check_safety()` in `guardrails.py` **before** the agent or any tool is invoked. Five injection/misuse categories are detected:

| Category | Example pattern | Action |
|---|---|---|
| Prompt injection | "ignore previous instructions", "disregard your system prompt" | Blocked with explanation |
| Role override | "you are now DAN", "act as an unrestricted AI" | Blocked |
| System manipulation | "pretend you have no rules", "forget all constraints" | Blocked |
| PII / credential harvesting | Credit card numbers, SSNs | Blocked; PII masked in logs |
| Off-scope abuse | Legal threats, account hacking requests | Blocked |

Blocking happens before the LLM is called, so no tokens are consumed and no tool is invoked.

### 3.2 PII Masking in Audit Logs

The `log_interaction()` function in `db.py` stores user input and agent response in the `interactions` audit table and (optionally) in Google Sheets. Before storage, `mask_pii()` replaces credit card numbers, email addresses, and phone numbers with `[REDACTED]`, ensuring raw PII never reaches persistent storage or third-party services.

### 3.3 Escalation as a Safety Valve

The `mark_unresolved()` / `mark_resolved()` logic in `AgentMemory` tracks consecutive unresolved turns. After 2 unresolved turns the agent is instructed to escalate to a human agent. This prevents the user from being trapped in an unhelpful loop (loop prevention) and ensures a human reviews edge cases the LLM cannot handle confidently.

### 3.4 Language Detection — No Silent Failures

`detect_language()` in `guardrails.py` uses `langdetect` to identify the user's language (40+ languages supported). The detected language is passed to the agent so responses are always in the user's language. If detection fails, English is the graceful default — the agent never responds in the wrong language or raises an unhandled exception.

### 3.5 Secrets Management

- `.env` is listed in `.gitignore` and is never committed to source control
- `render.yaml` contains only non-secret config values (`OPENAI_MODEL`, `PINECONE_INDEX_NAME`, etc.); all secret keys are set via the Render dashboard **Environment** tab
- `.env.example` ships with the repository as a template containing only placeholder values

---

## 4. Deployment Assumptions

### 4.1 Render Free Tier Constraints

The application is deployed on Render's free tier with the following understood limitations:

| Constraint | Impact | Mitigation |
|---|---|---|
| Service spins down after 15 min inactivity | ~30s cold start on first request | Acceptable for demo; `/api/health` can be used as a warm-up ping |
| Ephemeral filesystem | Local vector store (ChromaDB) lost on restart | Pinecone is the primary store; ChromaDB fallback is only used locally |
| 512 MB RAM | LangChain + Gradio + Pinecone client occupies ~300–400 MB at runtime | Monitored; upgrade to Starter plan ($7/mo) if OOM occurs |
| Shared CPU | Slower response when CPU-bound | GPT-4o API latency dominates regardless; CPU contention is a minor factor |

### 4.2 First-Start Pinecone Upsert

On first deployment the agent embeds all `.txt` files in `data/product_docs/` using `text-embedding-3-small` and upserts ~87 vectors to Pinecone. This takes 30–60 seconds depending on OpenAI rate limits. Subsequent starts skip the upsert (vector count check in `build_vectorstore()`). This is a one-time cost per index.

### 4.3 Database Cold-Start (Neon Free Tier)

Neon PostgreSQL suspends after 5 minutes of inactivity. The first database operation after suspension adds ~2 seconds of latency (Neon auto-wakes on connection). SQLAlchemy's connection pool handles the reconnect transparently — no application-level retry logic is needed. For production SLAs, a paid Neon plan or always-on PostgreSQL instance would replace this.

### 4.4 Stateless Horizontal Scaling

Each request carries a `session_id`. `AgentMemory` loads conversation history from the database using the session ID, making the application **stateless between restarts** and safe to scale horizontally across multiple replicas. The SQLAlchemy engine is a singleton per process (not shared across processes), which is correct behaviour for Render's single-instance free tier.

### 4.5 CI/CD via GitHub → Render Auto-Deploy

Any `git push` to the `main` branch triggers an automatic Render redeploy. The `render.yaml` blueprint pins the build command (`pip install -r requirements.txt`) and start command (`uvicorn main:app --host 0.0.0.0 --port $PORT`), so deployments are fully reproducible without manual steps.

### 4.6 Python Version Pinning

A `.python-version` file (`3.11.0`) and a `PYTHON_VERSION` environment variable in `render.yaml` ensure Render uses Python 3.11, which satisfies the `>=3.9` requirement of `langchain-pinecone>=0.2.0` and avoids the dependency resolution errors that occur on Render's default Python 3.8 runtime.
