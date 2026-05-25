"""
agent/sheets_logger.py
----------------------
Appends one row per agent turn to a Google Sheet, providing a live audit log
that the entire support team can view without server access.

Disabled gracefully when GOOGLE_SHEETS_ID / GOOGLE_SERVICE_ACCOUNT_JSON are
not set — the rest of the application continues to work unchanged.

Sheet columns (auto-created on first run):
  timestamp | session_id | category | language | user_query |
  resolution | ticket_id | latency_ms

Setup:
  1. Create a Google Cloud project and enable the Google Sheets API.
  2. Create a Service Account and download the JSON key file.
  3. Share your Google Sheet with the service account email (Editor access).
  4. Set in .env:
       GOOGLE_SHEETS_ID=<the long ID from the sheet URL>
       GOOGLE_SERVICE_ACCOUNT_JSON=path/to/service_account.json
         -- OR --
       GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account", ...}  (inline JSON)
       GOOGLE_SHEETS_TAB=Interactions   (optional; default: Interactions)
"""

import json
import logging
import os
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_HEADER = [
    "timestamp", "session_id", "category", "language",
    "user_query", "resolution", "ticket_id", "latency_ms",
]

# Module-level singletons — initialised once on first use
_worksheet = None
_ready: bool | None = None   # None = not yet attempted


def _init():
    """Connect to the Google Sheet. Returns the gspread Worksheet or None."""
    global _worksheet, _ready
    if _ready is not None:
        return _worksheet

    sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "").strip()
    sa_json  = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    tab_name = os.environ.get("GOOGLE_SHEETS_TAB", "Interactions").strip()

    if not sheet_id or not sa_json:
        logger.info(
            "Google Sheets logging disabled "
            "(GOOGLE_SHEETS_ID / GOOGLE_SERVICE_ACCOUNT_JSON not set)."
        )
        _ready = False
        return None

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]

        # Accept either a file path or an inline JSON string
        if os.path.isfile(sa_json):
            creds = Credentials.from_service_account_file(sa_json, scopes=scopes)
        else:
            info = json.loads(sa_json)
            creds = Credentials.from_service_account_info(info, scopes=scopes)

        gc = gspread.authorize(creds)
        workbook = gc.open_by_key(sheet_id)

        # Get or create the worksheet tab
        try:
            ws = workbook.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            ws = workbook.add_worksheet(title=tab_name, rows=5000, cols=len(_HEADER))
            ws.append_row(_HEADER, value_input_option="USER_ENTERED")
            logger.info("Google Sheets: created worksheet '%s'", tab_name)

        _worksheet = ws
        _ready = True
        logger.info("Google Sheets logging enabled → sheet %s / tab '%s'", sheet_id[:8] + "...", tab_name)
        return _worksheet

    except ImportError:
        logger.warning("gspread / google-auth not installed — Google Sheets logging disabled.")
        _ready = False
        return None
    except Exception as exc:
        logger.warning("Google Sheets init failed: %s", exc)
        _ready = False
        return None


# ---------------------------------------------------------------------------
# Resolution inference helpers
# ---------------------------------------------------------------------------

_TICKET_RE    = re.compile(r"\bTF-[A-Z0-9]{6}\b")
_ESCALATION_RE = re.compile(r"\bESC-[A-Z0-9]{6}\b")


def _infer_resolution(response: str) -> tuple[str, str]:
    """Return (resolution_label, ticket_or_escalation_id) from the response text."""
    m = _TICKET_RE.search(response)
    if m:
        return "ticket_created", m.group(0)
    m = _ESCALATION_RE.search(response)
    if m:
        return "escalated", m.group(0)
    return "responded", ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def log_turn(
    session_id: str,
    category: str,
    language: str,
    user_query: str,      # should already be PII-masked before calling
    response: str,
    latency_ms: float,
) -> None:
    """
    Append one interaction row to the configured Google Sheet.
    Fire-and-forget: any failure is logged as a warning and never propagates.
    """
    ws = _init()
    if ws is None:
        return

    resolution, ref_id = _infer_resolution(response)

    row = [
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        session_id or "anonymous",
        category,
        language,
        user_query[:200],
        resolution,
        ref_id,
        round(latency_ms, 1),
    ]

    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.debug("Sheets: row appended (session=%s, resolution=%s)", session_id, resolution)
    except Exception as exc:
        logger.warning("Google Sheets append failed: %s", exc)
