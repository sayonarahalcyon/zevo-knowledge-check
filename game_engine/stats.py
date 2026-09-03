"""A tiny on-disk counter for how many games have been hosted.

This is intentionally separate from GameStore's in-memory game state: it's
stored as a local JSON file so it survives things like the app going to
sleep/waking up, but it is NOT a permanent historical total. Streamlit
Community Cloud rebuilds the app's container from the GitHub repo on every
push, which wipes any local file that isn't checked into the repo (this app
has no external database wired up) — so this counter resets on redeploy,
same as the in-memory game state does. Good enough for "how many games has
the room run recently", not for all-time analytics.
"""

import json
import os

_STATS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "_runtime_stats.json",
)


def _read() -> dict:
    try:
        with open(_STATS_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"games_created": 0}


def _write(data: dict) -> None:
    tmp_path = _STATS_PATH + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f)
        os.replace(tmp_path, _STATS_PATH)
    except OSError:
        pass  # best-effort; never let stats tracking break the app


def increment_games_created() -> int:
    """Bump the persisted games-created counter and return the new total."""
    data = _read()
    data["games_created"] = data.get("games_created", 0) + 1
    _write(data)
    return data["games_created"]


def get_games_created() -> int:
    return _read().get("games_created", 0)
