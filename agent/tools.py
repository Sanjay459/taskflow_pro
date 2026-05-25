"""
agent/tools.py
--------------
LangChain-compatible tool definitions for the TaskFlow Pro Support Agent.
All tools are READ or CREATE only — no destructive operations permitted.
"""

import json
import uuid
from datetime import datetime
from langchain.tools import tool
from agent.db import get_ticket, save_ticket
from agent.slack_notifier import notify_ticket_created, notify_escalation


@tool
def check_ticket_status(ticket_id: str) -> str:
    """
    Check the current status of an existing TaskFlow Pro support ticket.
    Provide the ticket ID (e.g., TF-A1B2C3). Returns ticket details or a not-found message.
    """
    ticket = get_ticket(ticket_id.strip().upper())
    if ticket:
        return json.dumps(ticket, indent=2)
    return (
        f"No ticket found with ID '{ticket_id}'. "
        "Please double-check the ticket ID from your confirmation email."
    )


@tool
def create_support_ticket(subject: str, description: str, priority: str = "medium") -> str:
    """
    Create a new support ticket when the issue cannot be resolved through self-service.
    Use this after at least one resolution attempt has failed.
    priority must be one of: low, medium, high, critical.
    Do NOT include personally identifiable information (names, emails, card numbers) in the description.
    """
    allowed_priorities = {"low", "medium", "high", "critical"}
    safe_priority = priority.lower() if priority.lower() in allowed_priorities else "medium"

    ticket_id = f"TF-{uuid.uuid4().hex[:6].upper()}"
    ticket = {
        "ticket_id": ticket_id,
        "subject": subject[:200],          # cap length
        "description": description[:1000],  # cap length, no PII stored
        "priority": safe_priority,
        "status": "open",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    save_ticket(ticket)
    notify_ticket_created(ticket_id, subject[:100], safe_priority)
    return json.dumps(
        {
            "message": "Support ticket created successfully.",
            "ticket_id": ticket_id,
            "status": "open",
            "next_steps": (
                "You will receive an email confirmation shortly. "
                "A support agent will respond within 1 business day."
            ),
        },
        indent=2,
    )


@tool
def escalate_to_human(reason: str, context_summary: str) -> str:
    """
    Escalate the current conversation to a human support agent.
    Use this when:
    - The issue is sensitive, complex, or involves account/billing decisions.
    - Two or more self-service resolution attempts have failed.
    - The user explicitly requests a human agent.
    Provide a brief reason and a context_summary (no PII) so the human agent can assist immediately.
    """
    escalation_id = f"ESC-{uuid.uuid4().hex[:6].upper()}"
    notify_escalation(escalation_id, reason[:200], context_summary[:300])
    return json.dumps(
        {
            "escalation_id": escalation_id,
            "status": "escalated",
            "message": (
                "Your case has been escalated to a human support agent. "
                "You will receive an email within 2 business hours (Mon–Fri, 9am–6pm EST)."
            ),
            "reason": reason[:300],
        },
        indent=2,
    )
