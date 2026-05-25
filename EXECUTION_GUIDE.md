# TaskFlow Pro Support Agent — Execution Guide

A complete, step-by-step guide for setting up and running the project locally,
running the Jupyter notebooks, and using the REST API and Gradio UI.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Pre-requisites](#2-pre-requisites)
3. [Environment Setup](#3-environment-setup)
4. [Configure the `.env` File](#4-configure-the-env-file)
5. [Install Dependencies](#5-install-dependencies)
6. [Pinecone Index Setup](#6-pinecone-index-setup)
7. [Database Setup (SQLite / Neon)](#7-database-setup-sqlite--neon)
8. [Running the Full Application](#8-running-the-full-application)
9. [Using the Gradio Chat UI](#9-using-the-gradio-chat-ui)
10. [Using the REST API](#10-using-the-rest-api)
11. [Running the Gradio UI Standalone](#11-running-the-gradio-ui-standalone)
12. [Running the Jupyter Notebooks](#12-running-the-jupyter-notebooks)
13. [Module Import Validation](#13-module-import-validation)
14. [Enabling LangSmith Tracing](#14-enabling-langsmith-tracing)
15. [Enabling Optional Integrations (Slack / Google Sheets)](#15-enabling-optional-integrations-slack--google-sheets)
16. [Updating the Knowledge Base](#16-updating-the-knowledge-base)
17. [Common Errors and Fixes](#17-common-errors-and-fixes)
18. [Environment Variable Reference](#18-environment-variable-reference)
19. [Deploying to Render (Production)](#19-deploying-to-render-production)

---

## 1. Project Structure

```
Capstone project/
│
├── main.py                  ← FastAPI + Gradio combined server (entry point)
├── requirements.txt         ← All pip dependencies
├── .env                     ← Your local secrets (never commit)
├── .env.example             ← Template — copy to .env
├── render.yaml              ← Render deployment blueprint
├── Procfile                 ← Start command for Render / Heroku
├── DEPLOY.md                ← Production deployment guide
├── taskflow.db              ← SQLite database (auto-created on first run, gitignored)
│
├── agent/                   ← Core agent package
│   ├── agent.py             ← Agent assembly (LangGraph ReAct)
│   ├── db.py                ← Database engine, schema, ticket + audit ops
│   ├── memory.py            ← DB-backed conversation memory (SQLChatMessageHistory)
│   ├── retriever.py         ← Pinecone vector store + retriever factory
│   ├── tools.py             ← Custom tools (ticket check/create/escalate)
│   ├── guardrails.py        ← Safety checks, injection detection, PII masking
│   ├── tracing.py           ← LangSmith observability configuration
│   ├── slack_notifier.py    ← Slack ticket + escalation notifications
│   ├── sheets_logger.py     ← Google Sheets audit log mirror
│   └── __init__.py
│
├── ui/                      ← Gradio frontend package
│   ├── gradio_app.py        ← Gradio Blocks app (multi-turn chat)
│   └── __init__.py
│
├── data/
│   ├── product_docs/        ← Knowledge base (.txt files — committed to Git)
│   │   ├── billing_policy.txt
│   │   ├── features.txt
│   │   ├── getting_started.txt
│   │   ├── integrations.txt
│   │   ├── known_issues.txt
│   │   └── troubleshooting.txt
│   └── vectorstore/         ← ChromaDB local fallback (gitignored)
│
├── notebooks/               ← Phase-by-phase Jupyter development notebooks
│   ├── Phase1_Problem_Framing.ipynb
│   ├── Phase2_Basic_Agent.ipynb
│   ├── Phase3_LLM_Integration.ipynb
│   ├── Phase4_RAG_Knowledge.ipynb       ← Pinecone ingestion demo
│   ├── Phase5_Tool_Usage.ipynb
│   ├── Phase6_Memory_Planning.ipynb
│   ├── Phase7_Adaptive_Behaviour.ipynb
│   ├── Phase8_Deployment.ipynb
│   └── Phase9_Evaluation.ipynb
│
└── logs/                    ← Legacy log directory (JSONL logging superseded by DB persistence)
```

---

## 2. Pre-requisites

| Requirement | Minimum version | Check command |
|---|---|---|
| Python | 3.10 | `python --version` |
| pip | 23+ | `pip --version` |
| Git | any | `git --version` |
| OpenAI API key | — | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| Pinecone API key | — | [app.pinecone.io](https://app.pinecone.io) |
| LangSmith API key *(optional)* | — | [smith.langchain.com](https://smith.langchain.com) |
| Neon PostgreSQL account *(optional, production DB)* | — | [neon.tech](https://neon.tech) |
| Slack Bot token *(optional, ticket notifications)* | — | [api.slack.com/apps](https://api.slack.com/apps) |
| Google service account *(optional, audit log)* | — | [console.cloud.google.com](https://console.cloud.google.com) |

Python 3.10 is strongly recommended. Python 3.11+ also works.

---

## 3. Environment Setup

### 3a. Clone or locate the project

```powershell
# If cloning from GitHub:
git clone https://github.com/<you>/<repo>.git
cd "Capstone project"

# If already on disk:
cd "C:\Users\admin\AgenticAI_Course\Capstone project"
```

### 3b. Create a virtual environment (recommended)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows PowerShell
# source .venv/bin/activate     # macOS / Linux
```

You should see `(.venv)` at the start of your prompt.

---

## 4. Configure the `.env` File

Copy the example file and fill in your secrets:

```powershell
Copy-Item .env.example .env
```

Then open `.env` and set every value:

```ini
# --- LLM Provider ---
OPENAI_API_KEY=sk-...your-key...
OPENAI_MODEL=gpt-4o

# --- Logging ---
LOG_LEVEL=INFO
LOG_FILE=logs/agent_interactions.jsonl

# --- Vector Store (Pinecone — primary) ---
PINECONE_API_KEY=pc-...your-key...
PINECONE_INDEX_NAME=taskflow-kb
PINECONE_ENVIRONMENT=us-east-1

# --- Vector Store paths ---
DOCS_PATH=data/product_docs
VECTOR_STORE_PATH=data/vectorstore

# --- LangSmith Observability (optional) ---
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=ls__...your-key...
LANGSMITH_PROJECT=taskflow-pro-agent
LANGSMITH_ENDPOINT=https://api.smith.langchain.com

# --- Database (conversation history + tickets + audit log) ---
# Production (Neon): postgresql://user:pass@host/db?sslmode=require
# Local dev: leave blank — SQLite taskflow.db is auto-created in project root
DATABASE_URL=

# --- Slack Notifications (optional) ---
SLACK_BOT_TOKEN=xoxb-...your-token...
SLACK_ESCALATION_CHANNEL=#support-escalations

# --- Google Sheets Audit Log (optional) ---
GOOGLE_SHEETS_ID=your-spreadsheet-id
GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/service_account_key.json
GOOGLE_SHEETS_TAB=Interactions
```

> **Security rule:** `.env` is listed in `.gitignore` — it will never be committed. Never paste
> your real API keys anywhere else in the project.

---

## 5. Install Dependencies

```powershell
pip install -r requirements.txt
```

This installs:

| Package group | Key packages |
|---|---|
| LangChain stack | `langchain`, `langchain-openai`, `langchain-community`, `langchain-core`, `langchain-text-splitters` |
| Agent orchestration | `langgraph` |
| Vector store | `pinecone`, `langchain-pinecone`, `tiktoken` |
| API server | `fastapi`, `uvicorn` |
| Frontend | `gradio` |
| Observability | `langsmith` |
| Data / eval | `pandas`, `numpy`, `pydantic` |
| Notebooks | `jupyter`, `ipykernel`, `ipywidgets` |
| Integrations | `slack-sdk`, `gspread`, `google-auth` |
| Database | `sqlalchemy`, `psycopg2-binary` |
| Language detection | `langdetect` |

Typical install time: 2–4 minutes on a fresh venv.

---

## 6. Pinecone Index Setup

The retriever creates the index automatically on first run. Nothing manual is required **unless** you
want to pre-create it:

1. Log in to [app.pinecone.io](https://app.pinecone.io).
2. Create a **Serverless** index with these settings:

   | Setting | Value |
   |---|---|
   | Name | `taskflow-kb` (must match `PINECONE_INDEX_NAME`) |
   | Dimensions | `1536` |
   | Metric | `cosine` |
   | Cloud | `AWS` |
   | Region | `us-east-1` (must match `PINECONE_ENVIRONMENT`) |

On first application start the retriever will:
- Detect the index exists (or create it)
- Load all `.txt` files from `data/product_docs/`
- Split them into 500-character chunks with 50-character overlap
- Embed each chunk with `text-embedding-3-small`
- Upsert all vectors into the index

On subsequent starts the upsert is **skipped** (vectors already exist).

---

## 7. Database Setup (SQLite / Neon PostgreSQL)

No manual setup is required for **local development** — the SQLite database (`taskflow.db`)
is created automatically in the project root when the server starts (`init_schema()` runs in
the FastAPI lifespan hook).

For **production**, provision a free [Neon serverless PostgreSQL](https://neon.tech) database:

1. Create a free account at [neon.tech](https://neon.tech) and create a project.
2. From the Dashboard, copy the **Connection String** (pooled, `?sslmode=require` included).
3. Add it to `.env` and your Render environment variables:

   ```ini
   DATABASE_URL=postgresql://user:password@ep-xxx.aws.neon.tech/dbname?sslmode=require
   ```

Tables created automatically on first start — no migrations required:

| Table | Contents |
|---|---|
| `tickets` | Support ticket records (survives server restarts) |
| `interactions` | Per-turn audit log — session ID, category, language, latency |
| `message_store` | Full per-session conversation history (LangChain-managed) |

> **Tip:** Leave `DATABASE_URL` unset for local dev. `taskflow.db` is auto-created in the
> project root and is already listed in `.gitignore`.

---

## 8. Running the Full Application

The `main.py` entry point starts **both** the FastAPI REST API and the Gradio UI in one process.

```powershell
# From the project root:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Flag explanations:

| Flag | Purpose |
|---|---|
| `--reload` | Auto-restart on code changes (development only) |
| `--host 0.0.0.0` | Accept connections from all network interfaces |
| `--port 8000` | Listen on port 8000 |

Expected startup output:

```
INFO     DB engine ready: taskflow.db  (or neon-host/dbname in production)
INFO     DB schema ready.
INFO     Building agent...
INFO     Loading documents from '...\data\product_docs' ...
INFO     Pinecone index 'taskflow-kb' already exists.
INFO     Index 'taskflow-kb' has 87 vectors — skipping upsert.
INFO     Agent ready.
INFO     Uvicorn running on http://0.0.0.0:8000
```

> First-ever run (empty index): the upsert step takes ~30–60 seconds depending on your
> internet connection and OpenAI embedding rate limits.

### Available endpoints after startup

| Endpoint | Method | Description |
|---|---|---|
| `http://localhost:8000/chat` | GET (browser) | Gradio multi-turn chat UI |
| `http://localhost:8000/api/chat` | POST | REST JSON chat API |
| `http://localhost:8000/api/health` | GET | Health check / status JSON |
| `http://localhost:8000/docs` | GET (browser) | Interactive Swagger UI |
| `http://localhost:8000/redoc` | GET (browser) | ReDoc API docs |

---

## 9. Using the Gradio Chat UI

1. Start the server (see Section 7).
2. Open `http://localhost:8000/chat` in your browser.
3. Type a question in the text box and press **Send** or hit Enter.

Example questions to try:

- `What is the refund policy?`
- `How do I connect Slack to TaskFlow Pro?`
- `My dashboard won't load — what should I do?`
- `Check ticket #12345`
- `I need to speak to a human agent`

The **Clear** button resets the session memory.

---

## 10. Using the REST API

### Health check

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/health" -Method GET
```

Expected response:

```json
{
  "status": "ok",
  "agent": "ready",
  "timestamp": 1716000000.0
}
```

### Send a chat message

```powershell
$body = @{
    message    = "What are the billing options?"
    session_id = "user-session-001"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/chat" `
                  -Method POST `
                  -ContentType "application/json" `
                  -Body $body
```

With `curl`:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the billing options?", "session_id": "user-session-001"}'
```

Response schema:

```json
{
  "response": "TaskFlow Pro offers three billing plans ...",
  "session_id": "user-session-001",
  "latency_ms": 1243.7
}
```

> `session_id` is optional. If omitted a new UUID is generated and returned. Re-use the same
> `session_id` across requests to maintain conversation context.

### Delete a session (clear memory)

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/session/user-session-001" -Method DELETE
```

---

## 11. Running the Gradio UI Standalone

If you want to run **only** the Gradio chat app without the FastAPI server:

```powershell
python -m ui.gradio_app
```

Opens on `http://localhost:7860`.
Useful for rapidly iterating on the UI without starting the full server stack.

---

## 12. Running the Jupyter Notebooks

The `notebooks/` folder contains 9 phase notebooks that walk through the project
from problem framing to evaluation. Each notebook is self-contained and imports from
the `agent/` package.

### Start Jupyter

```powershell
jupyter lab
# or
jupyter notebook
```

This opens the browser automatically. Navigate to `notebooks/`.

### Recommended run order

| Notebook | What it covers |
|---|---|
| `Phase1_Problem_Framing.ipynb` | Problem definition, user personas, success metrics |
| `Phase2_Basic_Agent.ipynb` | Minimal LangGraph ReAct agent skeleton |
| `Phase3_LLM_Integration.ipynb` | OpenAI GPT-4o integration and system prompt |
| `Phase4_RAG_Knowledge.ipynb` | Pinecone ingestion, similarity search demo |
| `Phase5_Tool_Usage.ipynb` | Custom tool creation and agent tool-calling |
| `Phase6_Memory_Planning.ipynb` | Sliding-window memory implementation |
| `Phase7_Adaptive_Behaviour.ipynb` | Guardrails, PII masking, escalation logic |
| `Phase8_Deployment.ipynb` | FastAPI + Gradio server walkthrough |
| `Phase9_Evaluation.ipynb` | Response quality metrics and evaluation harness |

### Kernel requirement

Each notebook needs the **same Python environment** as the project.
Register it as a Jupyter kernel if needed:

```powershell
python -m ipykernel install --user --name taskflow --display-name "TaskFlow (Python 3.10)"
```

Then select **TaskFlow (Python 3.10)** from the kernel picker in each notebook.

---

## 13. Module Import Validation

Run this to confirm all agent modules load without errors:

```powershell
Set-Location "C:\Users\admin\AgenticAI_Course\Capstone project"

python -c "
import sys; sys.path.insert(0, '.')
import importlib
for m in ['agent.db','agent.guardrails','agent.tools','agent.tracing',
          'agent.memory','agent.retriever','agent.agent',
          'agent.slack_notifier','agent.sheets_logger']:
    try:
        importlib.import_module(m)
        print('OK ', m)
    except Exception as e:
        print('ERR', m, ':', e)
"
```

All lines should read `OK`. Any `ERR` line indicates a missing package or misconfigured `.env`.

---

## 14. Enabling LangSmith Tracing

LangSmith tracing is **off by default**. To enable it:

1. Get your API key from [smith.langchain.com](https://smith.langchain.com).
2. Edit `.env`:

   ```ini
   LANGSMITH_TRACING=true
   LANGSMITH_API_KEY=ls__...your-key...
   LANGSMITH_PROJECT=taskflow-pro-agent
   ```

3. Restart the server.

Every agent invocation will now appear as a trace in LangSmith with:
- Tool calls and their inputs/outputs
- LLM prompts and completions
- Token usage and latency per step
- Custom tags: `category:billing`, `category:feature`, `category:general`
- Session ID metadata

---

## 15. Enabling Optional Integrations (Slack / Google Sheets)

Both integrations are **disabled by default** and activate automatically when their
environment variables are present — no code changes required.

### Slack Notifications

Ticket creation and escalation events are posted to a Slack channel when these variables
are set:

```ini
SLACK_BOT_TOKEN=xoxb-...your-token...
SLACK_ESCALATION_CHANNEL=#support-escalations
```

To create a Slack bot:
1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**.
2. Under **OAuth & Permissions**, add the `chat:write` bot scope.
3. Install the app to your workspace and copy the **Bot User OAuth Token**.
4. Invite the bot to the escalation channel: `/invite @your-bot-name`.

### Google Sheets Audit Log

Every conversation turn is appended to a Google Sheet when these variables are set:

```ini
GOOGLE_SHEETS_ID=your-spreadsheet-id
GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/service_account_key.json
GOOGLE_SHEETS_TAB=Interactions
```

To set up:
1. Go to [console.cloud.google.com](https://console.cloud.google.com) → **IAM & Admin** → **Service Accounts**.
2. Create a service account, add the **Editor** role, and generate a JSON key file.
3. Share your Google Sheet with the service account email (`...@....iam.gserviceaccount.com`).
4. Set `GOOGLE_SERVICE_ACCOUNT_JSON` to the path of the downloaded JSON key.

---

## 16. Updating the Knowledge Base

To add or update documentation:

1. Add or edit `.txt` files in `data/product_docs/`.
2. To force re-embedding on next start, call `build_vectorstore(force_rebuild=True)` or use the
   Python snippet below:

   ```powershell
   python -c "
   import sys; sys.path.insert(0, '.')
   from agent.retriever import build_vectorstore
   build_vectorstore(force_rebuild=True)
   print('Done.')
   "
   ```

3. Restart the server — the new chunks will be retrievable immediately.

---

## 17. Common Errors and Fixes

### `ModuleNotFoundError: No module named 'agent'`

You must run commands **from the project root** (`Capstone project/`), not from a subdirectory.

```powershell
Set-Location "C:\Users\admin\AgenticAI_Course\Capstone project"
```

---

### `FileNotFoundError: data/product_docs`

The `DOCS_PATH` in `.env` is a relative path but the process is running from a different
working directory. The retriever auto-resolves this, but confirm `.env` contains:

```ini
DOCS_PATH=data/product_docs
```

---

### `pinecone.exceptions.UnauthorizedException`

Your `PINECONE_API_KEY` in `.env` is missing or invalid. Check the key at
[app.pinecone.io](https://app.pinecone.io) → API Keys.

---

### `openai.AuthenticationError`

Your `OPENAI_API_KEY` is missing or expired. Regenerate at
[platform.openai.com/api-keys](https://platform.openai.com/api-keys).

---

### `TypeError: create_react_agent() got an unexpected keyword argument 'state_modifier'`

You have an older version of `langgraph`. Run:

```powershell
pip install --upgrade langgraph
```

---

### `gradio.Error: CUDA / port already in use`

Another process is using port 7860 or 8000.

```powershell
# Find and kill the process using port 8000:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

Or start on a different port:

```powershell
uvicorn main:app --reload --port 8001
```

---

### `sqlalchemy.exc.OperationalError` / Database connection failed

Check:

- **Neon free tier**: the database suspends after 5 minutes of inactivity. The first request
  wakes it up automatically — expect ~2 extra seconds on that call.
- **URL prefix**: both `postgres://` and `postgresql://` are accepted. `db.py` normalises
  them to `postgresql+psycopg2://` automatically.
- **Driver missing**: `pip install psycopg2-binary`
- **SQLite fallback**: leave `DATABASE_URL` unset. `taskflow.db` is created in the project
  root on first start with no extra configuration.

---

### Cold start is slow (30–60 seconds)

This is expected on the **first ever run** while documents are being embedded and upserted to
Pinecone. Subsequent starts take 3–5 seconds.

---

## 18. Environment Variable Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | Model name (e.g. `gpt-4o`, `gpt-4-turbo`) |
| `LOG_LEVEL` | No | `INFO` | Python logging level |
| `LOG_FILE` | No | `logs/agent_interactions.jsonl` | PII-safe interaction log path |
| `PINECONE_API_KEY` | Yes | — | Pinecone API key |
| `PINECONE_INDEX_NAME` | No | `taskflow-kb` | Pinecone index name |
| `PINECONE_ENVIRONMENT` | No | `us-east-1` | Pinecone serverless region |
| `DOCS_PATH` | No | `data/product_docs` | Path to knowledge base `.txt` files |
| `VECTOR_STORE_PATH` | No | `data/vectorstore` | ChromaDB local fallback path |
| `LANGSMITH_TRACING` | No | `false` | Set `true` to enable LangSmith tracing |
| `LANGSMITH_API_KEY` | If tracing | — | LangSmith API key |
| `LANGSMITH_PROJECT` | No | `taskflow-pro-agent` | LangSmith project name |
| `LANGSMITH_ENDPOINT` | No | `https://api.smith.langchain.com` | LangSmith API endpoint |
| `ENVIRONMENT` | No | `production` | Runtime environment label (`development`/`production`) |
| `DATABASE_URL` | No | SQLite auto | Neon PostgreSQL or SQLite connection string |
| `SLACK_BOT_TOKEN` | No | — | Slack bot OAuth token (enables ticket/escalation notifications) |
| `SLACK_ESCALATION_CHANNEL` | No | `#support-escalations` | Slack channel for escalation alerts |
| `GOOGLE_SHEETS_ID` | No | — | Google Sheets spreadsheet ID for the audit log |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | No | — | Path to (or inline) Google service account JSON key |
| `GOOGLE_SHEETS_TAB` | No | `Interactions` | Worksheet tab name for the audit log |

---

## 19. Deploying to Render (Production)

Full step-by-step instructions for deploying this application as a Render Web Service
(including GitHub setup, environment variable configuration, Neon PostgreSQL, and
LangSmith monitoring) are in **[DEPLOY.md](DEPLOY.md)**.

Quick reference:

| File | Purpose |
|---|---|
| `DEPLOY.md` | Complete Render deployment walkthrough |
| `render.yaml` | Render Blueprint — auto-configures the Web Service on connect |
| `Procfile` | Fallback start command (`uvicorn main:app --host 0.0.0.0 --port $PORT`) |

> **Tip:** Render detects `render.yaml` automatically when you connect your GitHub repo.
> All secret values (`OPENAI_API_KEY`, `PINECONE_API_KEY`, etc.) must be set in the
> Render dashboard **Environment** tab — never committed to Git.
