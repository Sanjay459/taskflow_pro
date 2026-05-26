# Submission Guide — TaskFlow Pro Support Agent

## Github details:
https://github.com/Sanjay459/taskflow_pro

## Render url:
https://taskflow-pro-0fgi.onrender.com/api/health

https://taskflow-pro-0fgi.onrender.com/chat/

### Evaluator File Location Map

This document maps every submission requirement to the exact file(s) in this project.

---

## 1. Agent Source Code — with Run Instructions

| What | Where |
|---|---|
| **Agent source root** | [`agent/`](agent/) |
| Core agent (LangGraph ReAct loop) | [`agent/agent.py`](agent/agent.py) |
| Tool definitions (4 tools) | [`agent/tools.py`](agent/tools.py) |
| Conversational memory | [`agent/memory.py`](agent/memory.py) |
| Safety guardrails + PII masking | [`agent/guardrails.py`](agent/guardrails.py) |
| RAG retriever (Pinecone) | [`agent/retriever.py`](agent/retriever.py) |
| Database schema + ticket CRUD | [`agent/db.py`](agent/db.py) |
| Slack notifier | [`agent/slack_notifier.py`](agent/slack_notifier.py) |
| Google Sheets audit logger | [`agent/sheets_logger.py`](agent/sheets_logger.py) |
| LangSmith tracing config | [`agent/tracing.py`](agent/tracing.py) |
| FastAPI + Gradio entry point | [`main.py`](main.py) |
| Gradio chat UI | [`ui/gradio_app.py`](ui/gradio_app.py) |
| Knowledge base documents (RAG) | [`data/product_docs/`](data/product_docs/) |
| Python dependencies | [`requirements.txt`](requirements.txt) |
| Environment variable template | [`.env.example`](.env.example) |

> **Run instructions → [`EXECUTION_GUIDE.md`](EXECUTION_GUIDE.md)**  
> Covers local setup, environment variables, Pinecone ingestion, database init, and launching the app.  
> Section 19 covers cloud deployment to Render.

---

## 2. Problem Framing Document (1–2 pages)

| What | Where |
|---|---|
| **Primary problem framing notebook** | [`notebooks/Phase1_Problem_Framing.ipynb`](notebooks/Phase1_Problem_Framing.ipynb) |
| User persona, quantified problem statement (500 tickets/day, 65 % repeat, 14 h response) | Phase 1 — Section 2 |
| Inputs / Outputs / Constraints / Assumptions | Phase 1 — Section 3 |
| Success criteria & metrics table (6 KPIs) | Phase 1 — Section 5 |
| Known failure cases & edge scenarios (8 rows) | Phase 1 — Section 6 |
| Workflow map (ASCII flowchart) | Phase 1 — Section 7 |
| High-level architecture document | [`HIGH_LEVEL_DESIGN.md`](HIGH_LEVEL_DESIGN.md) |

---

## 3. Demo Script — Forced Interactions + Evidence

### 3a. Forced Interaction Demos (Notebooks)

| Scenario | Notebook | Section |
|---|---|---|
| Feature question (sub-task, views, shortcuts) | [`Phase5_Tool_Usage.ipynb`](notebooks/Phase5_Tool_Usage.ipynb) | 5.1 |
| Billing query + ticket creation | Phase 5 | 5.2 |
| Troubleshooting + escalation trigger | Phase 5 | 5.3 |
| Safety refusal (hack/bypass/legal) | Phase 5 | 5.4 |
| Loop prevention → auto-escalation | Phase 5 | 5.5 |
| Multi-turn memory (context carried forward) | [`Phase7_Adaptive_Behaviour.ipynb`](notebooks/Phase7_Adaptive_Behaviour.ipynb) | 7.7 |
| Adaptive billing prompt after feedback | Phase 7 | 7.4 |

### 3b. Evidence — Logs

| Artefact | Location |
|---|---|
| Agent interaction log (JSONL) | [`logs/agent_interactions.jsonl`](logs/agent_interactions.jsonl) |
| User feedback log (JSONL) | [`logs/feedback.jsonl`](logs/feedback.jsonl) |
| Phase 9 evaluation results (JSON) | [`logs/phase9_evaluation_results.json`](logs/phase9_evaluation_results.json) |
| Phase 3 prompt comparison results | [`logs/phase3_prompt_comparison.json`](logs/phase3_prompt_comparison.json) |

### 3c. Evidence — Screenshots

| Screenshot | File |
|---|---|
| Gradio chat UI (session 1) | [`screenshots/chat_screenshot_1.png`](screenshots/chat_screenshot_1.png) |
| Gradio chat UI (session 2) | [`screenshots/chat_screenshot_2.png`](screenshots/chat_screenshot_2.png) |
| Render cloud deployment (live) | [`screenshots/render_deploy.png`](screenshots/render_deploy.png) |
| Slack integration (#support-escalations) | [`screenshots/slack_integration.png`](screenshots/slack_integration.png) |
| LangSmith tracing dashboard | [`screenshots/langsmith_tracing.png`](screenshots/langsmith_tracing.png) |
| LangSmith monitoring overview | [`screenshots/langsmith_monitoring.png`](screenshots/langsmith_monitoring.png) |
| Neon PostgreSQL database | [`screenshots/neon_db_screenshot.png`](screenshots/neon_db_screenshot.png) |
| Pinecone vector index | [`screenshots/pinecone_db_screenshot.png`](screenshots/pinecone_db_screenshot.png) |
| REST API health check | [`screenshots/api_health.png`](screenshots/api_health.png) |

---

## 4. Prompt Comparison Table (2–3 variants, same test set, insights)

| What | Where |
|---|---|
| **Primary notebook** | [`notebooks/Phase3_LLM_Integration.ipynb`](notebooks/Phase3_LLM_Integration.ipynb) |
| Three prompt variants defined (v1 minimal / v2 structured / v3 chain-of-thought) | Phase 3 — Section 3.1 |
| 6-query test set (feature, billing, troubleshoot, integration, safety, off-topic) | Phase 3 — Section 3.2 |
| All prompts × all queries executed (18 API calls, results in `df`) | Phase 3 — Section 3.3 |
| Full side-by-side comparison table (DataFrame display) | Phase 3 — Section 3.4 |
| **Critical-case side-by-side (Q5 safety + Q6 off-topic) + quantitative scoring** | Phase 3 — Section 3.4b |
| Analysis table: v1 / v2 / v3 per query category | Phase 3 — Section 3.5 |
| Default prompt selection with justification | Phase 3 — Section 3.6 |
| **Tradeoffs table: 7 design decisions mapped to quality dimensions** | Phase 3 — Section 3.7 |
| Saved comparison JSON | [`logs/phase3_prompt_comparison.json`](logs/phase3_prompt_comparison.json) |

---

## 5. Evaluation Report — Including Debugged Failure Cases

| What | Where |
|---|---|
| **Primary notebook** | [`notebooks/Phase9_Evaluation.ipynb`](notebooks/Phase9_Evaluation.ipynb) |
| 20-query automated test harness (feature, billing, troubleshoot, integration, safety, out-of-scope, edge) | Phase 9 — Section 9.1 |
| Evaluation runner with per-query pass/fail + latency | Phase 9 — Section 9.2 |
| Per-category pass rates, P50/P95 latency | Phase 9 — Section 9.3 |
| Failed-case listing from live eval run | Phase 9 — Section 9.4 |
| Root cause analysis table (3 failures: E02, O02, B01) | Phase 9 — Section 9.5 |
| **Debugged Failure 1: Gradio 6.0 API breaking change** | Phase 9 — Section 9.5.1 |
| &emsp;→ Symptom: `AttributeError: 'list' object has no attribute 'get'` | |
| &emsp;→ Root cause: Gradio 6.14 changed history format from tuple to dict | |
| &emsp;→ Fix: `ui/gradio_app.py` respond() updated to dict format | |
| &emsp;→ Before/after output: reproduced and verified in notebook cell | |
| **Debugged Failure 2: Gibberish input passes guardrails (E02)** | Phase 9 — Section 9.5.2 |
| &emsp;→ Symptom: `"aaaaaaaaaa"` passed `check_safety()` unblocked | |
| &emsp;→ Root cause: no coherence / minimum-content check in guardrails | |
| &emsp;→ Fix: `is_gibberish()` pre-guard + `check_safety_v2()` | |
| &emsp;→ Before/after output: 5-input test confirms fix, no regressions | |
| O02 fix (off-topic → prompt scope rule): before/after output demo | Phase 9 — Section 9.5 |
| Safety & ethics review table (7 dimensions) | Phase 9 — Section 9.6 |
| Improvement roadmap (7 items, prioritised) | Phase 9 — Section 9.7 |
| Saved evaluation JSON | [`logs/phase9_evaluation_results.json`](logs/phase9_evaluation_results.json) |

---

## 6. Engineering & Product Justification

| What | Where |
|---|---|
| **Primary document** | [`ENGINEERING_JUSTIFICATION.md`](ENGINEERING_JUSTIFICATION.md) |
| Design decisions & tradeoffs (LLM, RAG, memory, DB, deployment) | ENGINEERING_JUSTIFICATION — Section 1 |
| Safety approach (guardrails, PII, refusals, escalation) | ENGINEERING_JUSTIFICATION — Section 2 |
| Deployment assumptions & production readiness | ENGINEERING_JUSTIFICATION — Section 3 |
| Known limitations & proposed mitigations | ENGINEERING_JUSTIFICATION — Section 4 |
| High-level architecture (component diagram, data-flow map) | [`HIGH_LEVEL_DESIGN.md`](HIGH_LEVEL_DESIGN.md) |
| Deployment playbook (Render, env vars, health check) | [`DEPLOY.md`](DEPLOY.md) |

---

## Quick Reference — Notebook → Rubric Criterion Map

| Notebook | Primary Rubric Criterion |
|---|---|
| `Phase1_Problem_Framing.ipynb` | Problem Framing & Domain Understanding |
| `Phase2_Basic_Agent.ipynb` | Python Foundations & Baseline Prototype |
| `Phase3_LLM_Integration.ipynb` | LLM Integration & Prompt Design |
| `Phase4_RAG_Knowledge.ipynb` | Embeddings & Semantic Retrieval (RAG) |
| `Phase5_Tool_Usage.ipynb` | Tool-Using Agent Implementation |
| `Phase6_Memory_Planning.ipynb` | Agent Architecture, Planning & Memory |
| `Phase7_Adaptive_Behaviour.ipynb` | Adaptive Behaviour & Feedback |
| `Phase8_Deployment.ipynb` | Deployment & Monitoring |
| `Phase9_Evaluation.ipynb` | Safety, Evaluation & Governance |

---

*Last updated: May 2026*
