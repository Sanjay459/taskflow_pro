"""
ui/gradio_app.py
----------------
Gradio multi-turn chat UI for the TaskFlow Pro Support Agent.

Can be run standalone:
    python -m ui.gradio_app

Or mounted inside FastAPI via main.py at the /chat path.
"""

import os
import warnings
import gradio as gr
from dotenv import load_dotenv

# Suppress Gradio 6.0 deprecation warning for theme/css in Blocks constructor.
# These params are kept in Blocks (not launch()) because the app is mounted via
# gr.mount_gradio_app() in FastAPI, where launch() is never called.
warnings.filterwarnings(
    "ignore",
    message="The parameters have been moved from the Blocks constructor",
    category=UserWarning,
)

load_dotenv()

from agent.agent import build_agent, run_agent_turn
from agent.memory import AgentMemory
from agent.tracing import configure_tracing

# ── LangSmith tracing ─────────────────────────────────────────────
configure_tracing(environment=os.environ.get("ENVIRONMENT", "development"))

# ---------------------------------------------------------------------------
# Build the shared agent executor once at import time
# (FastAPI lifespan also calls build_agent — they share the same Pinecone index)
# ---------------------------------------------------------------------------
_executor = None


def _get_executor():
    global _executor
    if _executor is None:
        _executor = build_agent(verbose=False)
    return _executor


# ---------------------------------------------------------------------------
# Chat handler — called by Gradio on every message submission
# ---------------------------------------------------------------------------

def respond(
    user_message: str,
    history: list[dict],  # [{"role": "user"|"assistant", "content": str}, ...]
    session_memory: AgentMemory,
) -> tuple[str, list[dict], AgentMemory]:
    """
    Process one conversation turn.

    Returns:
        - empty string  (clears the input box)
        - updated history
        - updated session_memory state
    """
    if not user_message.strip():
        return "", history, session_memory

    executor = _get_executor()
    response = run_agent_turn(executor, session_memory, user_message, session_id=session_memory.session_id)

    history = history + [
        {"role": "user",      "content": user_message},
        {"role": "assistant", "content": response},
    ]
    return "", history, session_memory


def clear_session(session_memory: AgentMemory) -> tuple[list, AgentMemory]:
    """Reset conversation history and agent memory."""
    session_memory.reset()
    return [], session_memory


# ---------------------------------------------------------------------------
# UI definition
# ---------------------------------------------------------------------------

HEADER_HTML = """
<div style="
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    border-radius: 12px;
    padding: 24px 32px;
    margin-bottom: 8px;
    color: white;
">
    <h1 style="margin:0; font-size:1.8rem; font-weight:700; letter-spacing:-0.5px;">
        &#128203; TaskFlow Pro — AI Support
    </h1>
    <p style="margin:6px 0 0; opacity:0.9; font-size:0.95rem;">
        Instant answers about features, billing, integrations, and troubleshooting.
        Powered by GPT-4o + Pinecone RAG.
    </p>
</div>
"""

EXAMPLE_QUESTIONS = [
    "How do I set up the Slack integration?",
    "What is the refund policy for annual plans?",
    "Why is my Gantt chart loading slowly?",
    "How do I create a support ticket?",
    "What keyboard shortcuts does TaskFlow Pro support?",
]

CSS = """
.gradio-container { max-width: 860px !important; margin: 0 auto; }
.chat-window { border-radius: 12px !important; }
footer { display: none !important; }
"""


def build_gradio_app() -> gr.Blocks:
    with gr.Blocks(
        theme=gr.themes.Soft(
            primary_hue="violet",
            secondary_hue="indigo",
            neutral_hue="slate",
            font=gr.themes.GoogleFont("Inter"),
        ),
        css=CSS,
        title="TaskFlow Pro AI Support",
    ) as demo:

        # ── Header ──────────────────────────────────────────────
        gr.HTML(HEADER_HTML)

        # ── Per-session state ────────────────────────────────────
        session_memory = gr.State(AgentMemory)

        # ── Chat window ──────────────────────────────────────────
        chatbot = gr.Chatbot(
            label="Conversation",
            height=480,
            show_label=False,
            avatar_images=(
                None,                          # user — default avatar
                "https://api.dicebear.com/9.x/bottts/svg?seed=taskflow&backgroundColor=4f46e5",
            ),
            elem_classes="chat-window",
        )

        # ── Input row ────────────────────────────────────────────
        with gr.Row():
            msg_box = gr.Textbox(
                placeholder="Ask me anything about TaskFlow Pro…",
                show_label=False,
                scale=9,
                container=False,
                autofocus=True,
            )
            send_btn = gr.Button("Send", variant="primary", scale=1, min_width=80)

        # ── Action row ───────────────────────────────────────────
        with gr.Row():
            clear_btn = gr.Button("🗑  New conversation", size="sm", variant="secondary")

        # ── Example questions ────────────────────────────────────
        gr.Examples(
            examples=EXAMPLE_QUESTIONS,
            inputs=msg_box,
            label="Try an example",
        )

        # ── Footer note ──────────────────────────────────────────
        gr.Markdown(
            "<center><small>Answers are grounded in the TaskFlow Pro knowledge base. "
            "For urgent issues, contact <b>support@taskflowpro.com</b>.</small></center>"
        )

        # ── Event wiring ─────────────────────────────────────────
        submit_kwargs = dict(
            fn=respond,
            inputs=[msg_box, chatbot, session_memory],
            outputs=[msg_box, chatbot, session_memory],
        )
        msg_box.submit(**submit_kwargs)
        send_btn.click(**submit_kwargs)

        clear_btn.click(
            fn=clear_session,
            inputs=[session_memory],
            outputs=[chatbot, session_memory],
        )

    return demo


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = build_gradio_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("GRADIO_PORT", 7860)),
        share=False,
    )
