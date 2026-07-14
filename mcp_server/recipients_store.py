import os
import json
import uuid
import re
import logging
from typing import List, Dict, Any

log = logging.getLogger("recipients_store")

# Allow running from either mcp_server or root dir
_CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config'))
STORE_FILE = os.path.join(_CONFIG_DIR, 'recipients.json')

DEFAULT_DATA = {
    "recipients": [],
    "preferences": {
        "daily_report": True,
        "critical_alerts": True,
        "warning_alerts": False
    }
}

def _get_data() -> Dict[str, Any]:
    if not os.path.exists(STORE_FILE):
        return DEFAULT_DATA.copy()
    try:
        with open(STORE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure structure exists
            if "recipients" not in data:
                data["recipients"] = []
            if "preferences" not in data:
                data["preferences"] = DEFAULT_DATA["preferences"].copy()
            return data
    except Exception as e:
        log.error(f"Error reading recipients store: {e}")
        return DEFAULT_DATA.copy()

def _save_data(data: Dict[str, Any]):
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    try:
        with open(STORE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error(f"Error writing to recipients store: {e}")

def get_recipients() -> List[Dict[str, str]]:
    data = _get_data()
    return data.get("recipients", [])

def add_recipient(email: str, label: str = "") -> Dict[str, str]:
    email = email.strip().lower()
    
    # Basic email validation
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise ValueError("Invalid email format.")

    data = _get_data()
    recipients = data.get("recipients", [])
    
    # Check for duplicates
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
    
    return new_recipient

def remove_recipient(recipient_id: str) -> bool:
    data = _get_data()
    recipients = data.get("recipients", [])
    
    initial_len = len(recipients)
    data["recipients"] = [r for r in recipients if r.get("id") != recipient_id]
    
    if len(data["recipients"]) < initial_len:
        _save_data(data)
        return True
    return False

def get_preferences() -> Dict[str, bool]:
    data = _get_data()
    return data.get("preferences", DEFAULT_DATA["preferences"])

def update_preferences(prefs: Dict[str, bool]) -> Dict[str, bool]:
    data = _get_data()
    current_prefs = data.get("preferences", DEFAULT_DATA["preferences"])
    
    if "daily_report" in prefs:
        current_prefs["daily_report"] = bool(prefs["daily_report"])
    if "critical_alerts" in prefs:
        current_prefs["critical_alerts"] = bool(prefs["critical_alerts"])
    if "warning_alerts" in prefs:
        current_prefs["warning_alerts"] = bool(prefs["warning_alerts"])
        
    data["preferences"] = current_prefs
    _save_data(data)
    
    return current_prefs
