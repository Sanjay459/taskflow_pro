"""
agent/slack_notifier.py
-----------------------
Sends Slack notifications for ticket creation and human escalations.

Disabled gracefully when SLACK_BOT_TOKEN / SLACK_ESCALATION_CHANNEL are not
set — the rest of the application continues to work without Slack configured.

Setup:
  1. Create a Slack app at https://api.slack.com/apps
  2. Add the OAuth scope: chat:write
  3. Install the app to your workspace and copy the Bot User OAuth Token
  4. Invite the bot to your channel:  /invite @YourBotName
  5. Set in .env:
       SLACK_BOT_TOKEN=xoxb-...
       SLACK_ESCALATION_CHANNEL=#support-escalations   (name or channel ID)
"""

import logging
import os

logger = logging.getLogger(__name__)

# Module-level singletons — initialised once on first use
_client = None
_channel: str = ""
_ready: bool | None = None   # None = not yet attempted


def _init() -> bool:
    """Initialise the Slack WebClient. Returns True if Slack is configured."""
    global _client, _channel, _ready
    if _ready is not None:
        return _ready

    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    _channel = os.environ.get("SLACK_ESCALATION_CHANNEL", "").strip()

    if not token or not _channel:
        logger.info("Slack notifications disabled (SLACK_BOT_TOKEN / SLACK_ESCALATION_CHANNEL not set).")
        _ready = False
        return False

    try:
        from slack_sdk import WebClient  # lazy import
        _client = WebClient(token=token)
        _ready = True
        logger.info("Slack notifications enabled → channel %s", _channel)
        return True
    except ImportError:
        logger.warning("slack-sdk not installed — Slack notifications disabled.")
        _ready = False
        return False


# ---------------------------------------------------------------------------
# Public notification functions
# ---------------------------------------------------------------------------

def notify_ticket_created(ticket_id: str, subject: str, priority: str) -> None:
    """Post a notification to the Slack channel when a support ticket is opened."""
    if not _init():
        return

    priority_emoji = {"low": ":white_circle:", "medium": ":large_yellow_circle:",
                      "high": ":large_orange_circle:", "critical": ":red_circle:"}.get(priority.lower(), ":white_circle:")

    try:
        _client.chat_postMessage(
            channel=_channel,
            text=f":ticket: New ticket {ticket_id} — {subject}",
            blocks=[
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": ":ticket:  New Support Ticket Created"},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Ticket ID:*\n`{ticket_id}`"},
                        {"type": "mrkdwn", "text": f"*Priority:*\n{priority_emoji} {priority.upper()}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Subject:*\n{subject[:200]}"},
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn",
                         "text": ":clock1: A support agent should review within 1 business day."},
                    ],
                },
            ],
        )
        logger.info("Slack: ticket notification sent — %s", ticket_id)
    except Exception as exc:
        logger.warning("Slack ticket notification failed: %s", exc)


def notify_escalation(escalation_id: str, reason: str, context_summary: str) -> None:
    """Post an urgent notification to the Slack channel when a conversation is escalated."""
    if not _init():
        return

    try:
        _client.chat_postMessage(
            channel=_channel,
            text=f":rotating_light: Escalation {escalation_id} — {reason}",
            blocks=[
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": ":rotating_light:  Human Escalation Required"},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Escalation ID:*\n`{escalation_id}`"},
                        {"type": "mrkdwn", "text": f"*Reason:*\n{reason[:150]}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Context:*\n{context_summary[:300]}",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn",
                         "text": ":alarm_clock: Requires *immediate* attention — respond within 2 business hours."},
                    ],
                },
            ],
        )
        logger.info("Slack: escalation notification sent — %s", escalation_id)
    except Exception as exc:
        logger.warning("Slack escalation notification failed: %s", exc)
