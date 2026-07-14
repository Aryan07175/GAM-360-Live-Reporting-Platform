"""
Recipients Store
================
Stores email recipients and notification preferences.

STORAGE STRATEGY — Render Ephemeral Disk Warning
-------------------------------------------------
Render's free/starter plan uses an EPHEMERAL filesystem. Any file written
to disk (including config/recipients.json) is WIPED on every deploy or
restart. This silently loses all added recipients.

To avoid this:
  1. PRIMARY:   Read/write from RECIPIENTS_DATA env var (a JSON string).
                Set this in Render → Environment Variables.
                Format: {"recipients":[{"id":"...","email":"...","label":"..."}],
                         "preferences":{"daily_report":true,...}}
  2. FALLBACK:  Local config/recipients.json (works locally, NOT on Render
                unless a Persistent Disk is attached).
  3. MEMORY:    In-memory store used when both above are unavailable.

HOW TO PERSIST RECIPIENTS ON RENDER (without a Persistent Disk):
  - After adding a recipient via the UI, copy the JSON from
    GET /api/recipients and paste it as the RECIPIENTS_DATA env var in
    Render's dashboard. Future deploys will reload from this variable.

  Alternatively, attach a Render Persistent Disk mounted at /data and set
  the RECIPIENTS_FILE env var to /data/recipients.json.
"""

import os
import json
import uuid
import re
import logging
from typing import List, Dict, Any

log = logging.getLogger("recipients_store")

# ── Storage path ──────────────────────────────────────────────────────────────
# Allow override via env var (useful for Render persistent disk at /data/...)
_CUSTOM_FILE = os.getenv("RECIPIENTS_FILE")
_CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config'))
STORE_FILE = _CUSTOM_FILE or os.path.join(_CONFIG_DIR, 'recipients.json')

DEFAULT_DATA: Dict[str, Any] = {
    "recipients": [],
    "preferences": {
        "daily_report": True,
        "critical_alerts": True,
        "warning_alerts": False
    }
}

# In-memory cache — the single source of truth at runtime
_memory_store: Dict[str, Any] = {}


def _load_initial_data() -> Dict[str, Any]:
    """
    Load data at startup in priority order:
    1. RECIPIENTS_DATA env var (survives Render redeploys — set manually)
    2. Local file (works locally or with Render Persistent Disk)
    3. Default empty state
    """
    # 1. Try env var first
    raw_env = os.getenv("RECIPIENTS_DATA")
    if raw_env:
        try:
            data = json.loads(raw_env)
            log.info("[RECIPIENTS] Loaded from RECIPIENTS_DATA env var (%d recipients)",
                     len(data.get("recipients", [])))
            return _ensure_structure(data)
        except Exception as e:
            log.error("[RECIPIENTS] Failed to parse RECIPIENTS_DATA env var: %s", e)

    # 2. Try local file
    if os.path.exists(STORE_FILE):
        try:
            with open(STORE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            log.info("[RECIPIENTS] Loaded from file %s (%d recipients)",
                     STORE_FILE, len(data.get("recipients", [])))
            return _ensure_structure(data)
        except Exception as e:
            log.error("[RECIPIENTS] Error reading %s: %s", STORE_FILE, e)

    log.warning(
        "[RECIPIENTS] No persisted recipients found. "
        "On Render, set RECIPIENTS_DATA env var to persist recipients across deploys."
    )
    return DEFAULT_DATA.copy()


def _ensure_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    if "recipients" not in data:
        data["recipients"] = []
    if "preferences" not in data:
        data["preferences"] = DEFAULT_DATA["preferences"].copy()
    return data


def _save_data(data: Dict[str, Any]):
    """Save to local file (works locally). On Render ephemeral disk this is
    temporary — log a hint to update the RECIPIENTS_DATA env var."""
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    try:
        with open(STORE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        log.info("[RECIPIENTS] Saved to %s", STORE_FILE)

        # Hint for Render users
        if not os.getenv("RECIPIENTS_DATA"):
            log.info(
                "[RECIPIENTS] Render tip: to persist across redeploys, copy the "
                "following JSON and set it as RECIPIENTS_DATA in Render env vars:\n%s",
                json.dumps(data)
            )
    except Exception as e:
        log.error("[RECIPIENTS] Error writing to %s: %s", STORE_FILE, e)


def _get_data() -> Dict[str, Any]:
    """Return current in-memory store (already loaded at startup)."""
    return _memory_store


# ── Bootstrap: load on import ─────────────────────────────────────────────────
_memory_store.update(_load_initial_data())


# ── Public API ────────────────────────────────────────────────────────────────

def get_recipients() -> List[Dict[str, str]]:
    data = _get_data()
    recipients = data.get("recipients", [])
    log.debug("[RECIPIENTS] get_recipients() → %d recipient(s)", len(recipients))
    return recipients


def add_recipient(email: str, label: str = "") -> Dict[str, str]:
    email = email.strip().lower()

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise ValueError("Invalid email format.")

    data = _get_data()
    recipients = data.get("recipients", [])

    for r in recipients:
        if r.get("email") == email:
            raise ValueError(f"Email {email} is already in the recipients list.")

    new_recipient = {
        "id": str(uuid.uuid4()),
        "email": email,
        "label": label.strip()
    }

    recipients.append(new_recipient)
    data["recipients"] = recipients
    _save_data(data)

    log.info("[RECIPIENTS] Added recipient: %s (label=%r). Total: %d",
             email, label, len(recipients))
    return new_recipient


def remove_recipient(recipient_id: str) -> bool:
    data = _get_data()
    recipients = data.get("recipients", [])

    initial_len = len(recipients)
    data["recipients"] = [r for r in recipients if r.get("id") != recipient_id]

    if len(data["recipients"]) < initial_len:
        _save_data(data)
        log.info("[RECIPIENTS] Removed recipient id=%s. Remaining: %d",
                 recipient_id, len(data["recipients"]))
        return True

    log.warning("[RECIPIENTS] remove_recipient: id=%s not found", recipient_id)
    return False


def get_preferences() -> Dict[str, bool]:
    data = _get_data()
    return data.get("preferences", DEFAULT_DATA["preferences"])


def update_preferences(prefs: Dict[str, bool]) -> Dict[str, bool]:
    data = _get_data()
    current_prefs = data.get("preferences", DEFAULT_DATA["preferences"].copy())

    for key in ("daily_report", "critical_alerts", "warning_alerts"):
        if key in prefs:
            current_prefs[key] = bool(prefs[key])

    data["preferences"] = current_prefs
    _save_data(data)

    log.info("[RECIPIENTS] Preferences updated: %s", current_prefs)
    return current_prefs
