import threading
import time
from typing import Any, Dict

latest_data_lock = threading.Lock()
latest_data: Dict[str, Any] = {
    "raw": None,
    "parsed": None,
    "device_id": None,
    "topic": None,
    "last_updated": None,
}

def update_latest(raw: str, parsed_rows, device_id: str, topic: str):
    """Update the globally shared latest data."""
    with latest_data_lock:
        latest_data["raw"] = raw
        latest_data["parsed"] = parsed_rows  # list[dict]
        latest_data["device_id"] = device_id
        latest_data["topic"] = topic
        latest_data["last_updated"] = time.time()

def get_latest_data() -> Dict[str, Any]:
    """Return a copy of the latest data so callers can't mutate it."""
    with latest_data_lock:
        return dict(latest_data)
