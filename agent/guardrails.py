"""
agent/guardrails.py
-------------------
Safety checks, prompt-injection / jailbreak detection,
PII masking, and language detection for the TaskFlow Pro Support Agent.
"""

import re
from typing import Tuple

# ---------------------------------------------------------------------------
# Content safety — policy-violating request patterns
# ---------------------------------------------------------------------------
UNSAFE_PATTERNS = [
    (r"\b(hack|exploit|bypass|crack|brute[\s-]?force)\b", "security bypass attempt"),
    (r"\b(sql\s*inject|xss|script\s*inject)\b", "injection attempt"),
    (r"\b(lawsuit|legal\s*action|sue\s+you|take\s+you\s+to\s+court)\b", "legal threat — requires human"),
    (r"\b(refund\s+me\s+now|charge\s*back|dispute\s+payment)\b", "payment dispute — requires billing team"),
    (r"\b(delete\s+my\s+account|close\s+my\s+account)\b", "account deletion — requires human confirmation"),
]

# ---------------------------------------------------------------------------
# Prompt injection / jailbreak detection patterns
# ---------------------------------------------------------------------------
INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Instruction override
    (
        r"ignore\s+(all\s+)?(previous|prior|above|your|the)\s+"
        r"(instructions?|rules?|guidelines?|directives?|constraints?|prompt)",
        "instruction override attempt",
    ),
    (
        r"forget\s+(everything|all(\s+previous)?\s+instructions?|your\s+(rules?|instructions?|guidelines?))",
        "instruction override attempt",
    ),
    (
        r"disregard\s+(all\s+)?(previous|prior|your|the)\s+(instructions?|rules?|guidelines?)",
        "instruction override attempt",
    ),
    (
        r"(do\s+not|don'?t)\s+follow\s+(your|the|any|all)\s+(instructions?|rules?|guidelines?|constraints?)",
        "instruction override attempt",
    ),
    (
        r"override\s+(your|the|all)\s+(instructions?|rules?|safety|guidelines?|constraints?)",
        "instruction override attempt",
    ),
    (
        r"(new|updated|revised)\s+(instructions?|rules?|guidelines?|directives?)\s*:\s*\S",
        "instruction injection attempt",
    ),

    # Persona / role hijacking
    (r"you\s+are\s+now\s+(a|an|no\s+longer|not)\b", "persona hijacking attempt"),
    (r"pretend\s+(you\s+are|to\s+be|that\s+you\s+(are|have\s+no))", "persona hijacking attempt"),
    (r"roleplay\s+as\s+(a|an|the)\b", "persona hijacking attempt"),
    (
        r"act\s+as\s+(if\s+you\s+(are|were|have)|a\s+different\b|an?\s+unrestricted\b|an?\s+uncensored\b)",
        "persona hijacking attempt",
    ),
    (
        r"(switch|change|transform)\s+(to|into)\s+(a|an|the)\s+"
        r"(mode|persona|character|role|version)\s+(that|where|which|without)",
        "persona hijacking attempt",
    ),
    (
        r"your\s+true\s+(self|capabilities|form|nature)\s+(has\s+no|without|ignore)",
        "persona hijacking attempt",
    ),

    # Named jailbreak variants
    (r"\bdan\b.{0,30}\b(mode|prompt|now)\b", "DAN jailbreak attempt"),
    (r"\bjailbreak\b", "jailbreak attempt"),
    (r"\bdeveloper\s+mode\b", "developer mode jailbreak"),
    (r"\bunrestricted\s+mode\b", "unrestricted mode jailbreak"),
    (
        r"(without|no)\s+(any\s+)?(restrictions?|limitations?|constraints?|safety\s+filters?)\b",
        "bypass attempt",
    ),
    (
        r"(bypass|disable|turn\s+off|remove)\s+(your\s+)?(safety|content\s+filter|restrictions?|guidelines?)",
        "safety bypass attempt",
    ),
    (r"unleash\s+your\s+(true|full|real|hidden)\b", "jailbreak attempt"),

    # System prompt / instruction extraction
    (
        r"(repeat|print|output|reveal|show|tell\s+me|display|write\s+out)\s+"
        r"(your|the|all|initial|original|full)\s+(system\s+)?prompt",
        "prompt extraction attempt",
    ),
    (
        r"(repeat|print|output|reveal|show|display)\s+(your|the|all|original)\s+instructions?",
        "prompt extraction attempt",
    ),
    (
        r"what\s+(are|were|is)\s+your\s+(original\s+)?(instructions?|rules?|system\s+prompt)\b",
        "prompt extraction attempt",
    ),

    # Template / separator injection (ChatML, XML, markdown tricks)
    (r"<\s*/?\s*(system|assistant|user)\s*>", "template injection attempt"),
    (r"###\s*(system|new\s+instructions?|override|assistant)\b", "template injection attempt"),
    (r"\[\s*(system|INST|SYS|OVERRIDE)\s*\]", "template injection attempt"),
    (r"<\|im_start\|>|<\|endoftext\|>|<\|im_end\|>", "model token injection attempt"),

    # Encoding-based bypass
    (
        r"base64\s+(encoded|decode\s+(and\s+)?(run|execute|follow)|instruction|command|prompt)",
        "encoded instruction attempt",
    ),
]

# ---------------------------------------------------------------------------
# PII patterns — strip before logging
# ---------------------------------------------------------------------------
PII_PATTERNS = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL]"),
    (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE]"),
    (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "[CARD_NUMBER]"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),
    (r"\bpassword\s*[=:]\s*\S+", "[PASSWORD]"),
]

# ---------------------------------------------------------------------------
# Language code → full name map (ISO 639-1 + common variants)
# ---------------------------------------------------------------------------
_LANG_NAMES: dict[str, str] = {
    "af": "Afrikaans", "ar": "Arabic",   "bg": "Bulgarian", "bn": "Bengali",
    "ca": "Catalan",   "cs": "Czech",    "cy": "Welsh",     "da": "Danish",
    "de": "German",    "el": "Greek",    "en": "English",   "es": "Spanish",
    "et": "Estonian",  "fa": "Persian",  "fi": "Finnish",   "fr": "French",
    "gu": "Gujarati",  "he": "Hebrew",   "hi": "Hindi",     "hr": "Croatian",
    "hu": "Hungarian", "id": "Indonesian","it": "Italian",  "ja": "Japanese",
    "kn": "Kannada",   "ko": "Korean",   "lt": "Lithuanian","lv": "Latvian",
    "mk": "Macedonian","ml": "Malayalam","mr": "Marathi",   "ms": "Malay",
    "mt": "Maltese",   "nl": "Dutch",    "no": "Norwegian", "pl": "Polish",
    "pt": "Portuguese","ro": "Romanian", "ru": "Russian",   "sk": "Slovak",
    "sl": "Slovenian", "so": "Somali",   "sq": "Albanian",  "sv": "Swedish",
    "sw": "Swahili",   "ta": "Tamil",    "te": "Telugu",    "th": "Thai",
    "tl": "Filipino",  "tr": "Turkish",  "uk": "Ukrainian", "ur": "Urdu",
    "vi": "Vietnamese","zh-cn": "Chinese","zh-tw": "Chinese (Traditional)",
}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def check_safety(user_input: str) -> Tuple[bool, str]:
    """
    Returns (is_safe, refusal_message).
    If is_safe is False, refusal_message contains an appropriate response.
    """
    lower = user_input.lower()
    for pattern, reason in UNSAFE_PATTERNS:
        if re.search(pattern, lower):
            return False, (
                f"I'm not able to assist with that request ({reason}). "
                "If you need further help, I can escalate this to a human agent."
            )
    return True, ""


def check_injection(user_input: str) -> Tuple[bool, str]:
    """
    Detect prompt injection and jailbreak attempts.
    Returns (is_clean, refusal_message).
    is_clean=True means no injection detected (safe to process).
    """
    lower = user_input.lower()
    for pattern, _reason in INJECTION_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return False, (
                "I'm only able to assist with TaskFlow Pro support questions. "
                "If you have a product question, I'm happy to help!"
            )
    return True, ""


def mask_pii(text: str) -> str:
    """Remove PII from text before it is written to logs."""
    for pattern, replacement in PII_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def detect_language(text: str) -> str:
    """
    Detect the natural language of *text*.
    Returns a full language name (e.g. 'Spanish', 'French').
    Falls back to 'English' if detection fails or the text is too short.
    """
    if len(text.strip()) < 8:          # too short to detect reliably
        return "English"
    try:
        from langdetect import detect  # lazy import — graceful if not installed
        code = detect(text)
        return _LANG_NAMES.get(code, "English")
    except Exception:
        return "English"
