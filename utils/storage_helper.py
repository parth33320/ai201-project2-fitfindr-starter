import json
import os
from datetime import datetime

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_PROFILE_PATH = os.path.join(_DATA_DIR, "style_profile.json")

def _load_all_profiles() -> dict:
    if not os.path.exists(_PROFILE_PATH):
        return {}
    try:
        with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def _save_all_profiles(profiles: dict):
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)

def load_style_profile(user_id: str) -> list[str]:
    """Load historical style tags for a specific user."""
    profiles = _load_all_profiles()
    user_data = profiles.get(user_id, {})
    return user_data.get("tags", [])

def save_style_profile(user_id: str, new_tags: list[str]):
    """Append new tags to user's history, deduplicate, and cap at 10 (FIFO)."""
    if not new_tags:
        return

    profiles = _load_all_profiles()
    user_data = profiles.get(user_id, {"tags": [], "last_updated": ""})

    current_tags = user_data.get("tags", [])

    # Update logic: Append new tags, maintaining order, then deduplicate
    # To keep it FIFO-ish and capped at 10:
    # We want to add new tags to the end.
    for tag in new_tags:
        tag = tag.strip().lower()
        if not tag:
            continue
        if tag in current_tags:
            current_tags.remove(tag)
        current_tags.append(tag)

    # Cap at 10
    if len(current_tags) > 10:
        current_tags = current_tags[-10:]

    user_data["tags"] = current_tags
    user_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    profiles[user_id] = user_data
    _save_all_profiles(profiles)
