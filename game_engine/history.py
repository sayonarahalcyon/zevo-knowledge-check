"""Persisted history of finished games, for the admin drill-down view.

Same storage caveat as game_engine/stats.py: this lives in the system temp
directory, not the repo, so it resets whenever the app redeploys or reboots.
It's "results since last deploy", not permanent historical analytics.

Each finished game is stored as ONE session record:
    {
        "code": "YPAK",
        "category": "Vehicle",
        "played_at": 1730598900.123,
        "players": [
            {
                "name": "Faith",
                "score": 3994,
                "answers": [
                    {"question": "...", "your_answer": "...", "correct_answer": "...",
                     "correct": True, "points": 800},
                    ...
                ],
            },
            ...
        ],
    }

so the Admin page can drill from a session, to a player, to that player's
question-by-question right/wrong breakdown.

An earlier version of this file stored one FLAT record per player (no
"players" key, no per-question "answers") instead of one record per game.
get_all_sessions() understands both shapes and groups old flat rows that
share the same (code, played_at) back into a single legacy session, so
results recorded before this change aren't lost - they just show up
without a per-question breakdown.
"""

import json
import os
import tempfile
import time
from typing import Dict, List, Optional

_HISTORY_PATH = os.path.join(tempfile.gettempdir(), "zevo_kc_game_history.json")

_last_error: Optional[str] = None


def _read_all() -> List[dict]:
    global _last_error
    try:
        with open(_HISTORY_PATH, "r") as f:
            data = json.load(f)
        _last_error = None
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        _last_error = None  # normal before the first game finishes
        return []
    except Exception as e:  # noqa: BLE001 - deliberately broad for diagnostics
        _last_error = f"read failed ({type(e).__name__}): {e}"
        return []


def _write_all(records: List[dict]) -> None:
    global _last_error
    tmp_path = _HISTORY_PATH + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(records, f)
        os.replace(tmp_path, _HISTORY_PATH)
        _last_error = None
    except Exception as e:  # noqa: BLE001 - deliberately broad; never break the app
        _last_error = f"write failed ({type(e).__name__}): {e}"


def record_game_result(code: str, category_label: Optional[str], players: List[Dict]) -> None:
    """Append one session record for a game that just finished.

    players: list of {"name": str, "score": int, "answers": [ {...}, ... ]},
    where each answer dict has "question", "your_answer" (None if unanswered),
    "correct_answer", "correct" (bool), and "points".
    """
    records = _read_all()
    records.append(
        {
            "code": code,
            "category": category_label,
            "played_at": time.time(),
            "players": players,
        }
    )
    _write_all(records)


def get_all_sessions() -> List[dict]:
    """Every finished game, newest first, normalized to the session shape.

    Handles both current session-shaped records and legacy flat per-player
    records (grouped back into a pseudo-session by matching code+played_at;
    those players simply have an empty "answers" list since the old format
    never recorded per-question detail).
    """
    sessions_by_key: Dict[tuple, dict] = {}
    order: List[tuple] = []

    for rec in _read_all():
        key = (rec.get("code"), rec.get("played_at"))
        if "players" in rec:
            sessions_by_key[key] = rec
            if key not in order:
                order.append(key)
            continue

        # Legacy flat per-player record - group by (code, played_at).
        session = sessions_by_key.get(key)
        if session is None:
            session = {
                "code": rec.get("code"),
                "category": rec.get("category"),
                "played_at": rec.get("played_at"),
                "players": [],
                "legacy": True,
            }
            sessions_by_key[key] = session
            order.append(key)
        session["players"].append(
            {"name": rec.get("name"), "score": rec.get("score", 0), "answers": []}
        )

    sessions = [sessions_by_key[k] for k in order]
    return sorted(sessions, key=lambda s: s.get("played_at", 0), reverse=True)


def get_last_error() -> Optional[str]:
    """For diagnostics: the last read/write problem hit, if any."""
    return _last_error


def get_debug_info() -> dict:
    """For diagnostics: where the history file lives and what's on disk right now."""
    info = {"path": _HISTORY_PATH, "exists": os.path.exists(_HISTORY_PATH)}
    try:
        info["writable_dir"] = os.access(os.path.dirname(_HISTORY_PATH), os.W_OK)
    except Exception as e:  # noqa: BLE001
        info["writable_dir"] = f"check failed: {e}"
    return info
