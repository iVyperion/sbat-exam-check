"""
Persist the exam slots that were already seen, so a restart doesn't
re-send notifications for slots you were already told about.

Stored as JSON in `seen_slots.json` next to the script / frozen executable.
Keys look like "<center> YYYY-MM-DDTHH:MM"; slots in the past are pruned.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


SEEN_FILE = _app_dir() / "seen_slots.json"


def _is_future(key: str, today: str) -> bool:
    # key = "<center> YYYY-MM-DDTHH:MM" -> compare the date part
    date_part = key.rsplit(" ", 1)[-1][:10]
    return date_part >= today


def load_seen() -> set[str]:
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            data = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        return {k for k in data if isinstance(k, str) and _is_future(k, today)}
    except FileNotFoundError:
        return set()
    except Exception as e:
        print(f"Could not read {SEEN_FILE}: {e}")
        return set()


def save_seen(seen: set[str]) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    keep = sorted(k for k in seen if _is_future(k, today))
    tmp = SEEN_FILE.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(keep, f, indent=2)
        os.replace(tmp, SEEN_FILE)  # atomic, so a crash never leaves a half-written file
    except Exception as e:
        print(f"Could not write {SEEN_FILE}: {e}")
