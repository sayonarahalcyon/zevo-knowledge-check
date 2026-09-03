"""Persisted history of finished games, for the admin results view.

Same storage caveat as game_engine/stats.py: this lives in the system temp
directory, not the repo, so it resets whenever the app redeploys or reboots.
It's "results since last deploy", not permanent historical analytics.

One record per player per finished game: who played, what they scored, what
category, which game code, and when.
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
    """Append one row per player for a game that just finished.

    players: iterable of {"name": str, "score": int}.
    """
    records = _read_all()
    played_at = time.time()
    for p in players:
        records.append(
            {
                "name": p["name"],
                "score": p["score"],
                "code": code,
                "category": category_label,
                "played_at": played_at,
            }
        )
    _write_all(records)


def get_all_results() -> List[dict]:
    return _read_all()


def get_last_error() -> Optional[str]:
    """For diagnostics: the last read/write problem hit, if any."""
    return _last_error
