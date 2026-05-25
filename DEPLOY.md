# Deploying TaskFlow Pro Support Agent on Render

This guide covers deploying the combined **FastAPI + Gradio** application to
[Render](https://render.com) as a single Web Service.

---

## Architecture Overview

```
Render Web Service  (single process)
│
├── GET  /chat          →  Gradio multi-turn chat UI
├── POST /api/chat      →  REST JSON API
└── GET  /api/health    →  Health check (used by Render)
│
├── LangGraph agent  →  GPT-4o (OpenAI)
├── Pinecone         →  Vector store (knowledge base)
└── LangSmith        →  Run tracing & observability
```

---

## Pre-requisites

Before deploying, ensure you have:

| Item | Where to get it |
|---|---|
| GitHub repo with this project | [github.com](https://github.com) |
| Render account | [render.com/register](https://render.com/register) |
| OpenAI API key | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| Pinecone API key + index | [app.pinecone.io](https://app.pinecone.io) |
| LangSmith API key | [smith.langchain.com](https://smith.langchain.com) |

### Pinecone index setup (one-time)

1. Log in to [app.pinecone.io](https://app.pinecone.io).
2. Create a **Serverless** index named `taskflow-kb`:
   - Dimensions: **1536**
   - Metric: **cosine**
   - Cloud: **AWS**, Region: **us-east-1** (or your preferred region)
3. Copy your API key.

> The agent will upsert document vectors into this index on first start automatically.

---

## Step-by-Step Deployment

### 1. Push your code to GitHub

```bash
git init                          # if not already a repo
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

Make sure `.gitignore` excludes `.env`, `data/vectorstore/`, and `logs/`.

---

### 2. Create a new Web Service on Render

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Web Service**.
2. Connect your GitHub account and select your repository.
3. Render will detect the `render.yaml` blueprint automatically. Click **Apply**.

If the blueprint is not detected, configure manually:

| Setting | Value |
|---|---|
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Health Check Path** | `/api/health` |

---

### 3. Set Environment Variables

Go to your service → **Environment** tab → **Add Environment Variable** for each key below.

> **Never paste secrets into `render.yaml`** — set them only in the Render dashboard.

| Variable | Value | Secret? |
|---|---|---|
| `OPENAI_API_KEY` | `sk-...` | Yes |
| `OPENAI_MODEL` | `gpt-4o` | No |
| `PINECONE_API_KEY` | `pc-...` | Yes |
| `PINECONE_INDEX_NAME` | `taskflow-kb` | No |
| `PINECONE_ENVIRONMENT` | `us-east-1` | No |
| `LANGSMITH_TRACING` | `true` | No |
| `LANGSMITH_API_KEY` | `ls__...` | Yes |
| `LANGSMITH_PROJECT` | `taskflow-pro-agent` | No |
| `LANGSMITH_ENDPOINT` | `https://api.smith.langchain.com` | No |
| `ENVIRONMENT` | `production` | No |
| `LOG_LEVEL` | `INFO` | No |
| `DOCS_PATH` | `data/product_docs` | No |

---

### 4. Deploy

Click **Save Changes** → Render will trigger an automatic deploy.

Watch the **Logs** tab. A successful first deploy will show:

```
Building agent...
Loading documents from '.../data/product_docs' ...
Pinecone index 'taskflow-kb' already exists.
Index 'taskflow-kb' has 0 vectors — upserting ...
Upserted 87 chunks to index 'taskflow-kb'.
Agent ready.
```

On subsequent deploys the upsert is skipped (index already has vectors).

---

### 5. Verify

| Check | URL |
|---|---|
| Health check | `https://<your-service>.onrender.com/api/health` |
| Gradio UI | `https://<your-service>.onrender.com/chat` |
| REST API | `POST https://<your-service>.onrender.com/api/chat` |

REST API test with `curl`:

```bash
curl -X POST https://<your-service>.onrender.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the refund policy?", "session_id": "test-123"}'
```

---

### 6. Updating the knowledge base

When you add or edit files in `data/product_docs/`:

1. Commit and push to GitHub — Render redeploys automatically.
2. On first start with new docs, call `build_vectorstore(force_rebuild=True)` or set
   a temporary env var `FORCE_REBUILD=true` and add handling in `retriever.py`.

---

## Monitoring with LangSmith

Once deployed with `LANGSMITH_TRACING=true`:

1. Go to [smith.langchain.com](https://smith.langchain.com) → project **taskflow-pro-agent**.
2. Every agent run appears as a trace with:
   - Tool calls (search_knowledge_base, create_support_ticket, etc.)
   - LLM inputs/outputs and token counts
   - Latency per step
   - Custom tags: `category:billing`, `category:feature`, `category:general`
   - Session ID metadata for per-user filtering

---

## Render Free Tier Limitations

| Limitation | Impact | Resolution |
|---|---|---|
| Service spins down after 15 min inactivity | Cold start ~30s on first request | Upgrade to **Starter** plan ($7/mo) for always-on |
| Ephemeral filesystem | ChromaDB local store is lost on restart | Already handled — Pinecone is the primary store |
| 512 MB RAM | May be tight with Gradio + LangChain loaded | Upgrade plan or reduce `chunk_size` in retriever |
| Shared CPU | Slower inference | Acceptable for demo; upgrade for production |

---

## Re-deploying

Any `git push` to the connected branch triggers an automatic redeploy.

To trigger a manual redeploy: Render dashboard → **Manual Deploy** → **Deploy latest commit**.
