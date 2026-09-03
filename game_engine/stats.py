"""A tiny on-disk counter for how many games have been hosted.

This is intentionally separate from GameStore's in-memory game state: it's
stored as a local JSON file so it survives things like the app going to
sleep/waking up, but it is NOT a permanent historical total. Streamlit
Community Cloud rebuilds the app's container from the GitHub repo on every
push, which wipes any local file that isn't checked into the repo (this app
has no external database wired up) — so this counter resets on redeploy,
same as the in-memory game state does. Good enough for "how many games has
the room run recently", not for all-time analytics.

The file lives in the system temp directory rather than next to the repo
code: some managed hosts (including, it turns out, Streamlit Community
Cloud) mount the deployed app source read-only, so writing beside the code
can silently fail. The OS temp dir is writable in effectively every
sandboxed/managed Python environment.
"""

import json
import os
import tempfile

_STATS_PATH = os.path.join(tempfile.gettempdir(), "zevo_kc_runtime_stats.json")

_last_write_error: str | None = None


def _read() -> dict:
    try:
        with open(_STATS_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"games_created": 0}


def _write(data: dict) -> None:
    global _last_write_error
    tmp_path = _STATS_PATH + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f)
        os.replace(tmp_path, _STATS_PATH)
        _last_write_error = None
    except OSError as e:
        _last_write_error = str(e)  # best-effort; never let stats tracking break the app


def increment_games_created() -> int:
    """Bump the persisted games-created counter and return the new total."""
    data = _read()
    data["games_created"] = data.get("games_created", 0) + 1
    _write(data)
    return data["games_created"]


def get_games_created() -> int:
    return _read().get("games_created", 0)


def get_last_write_error() -> str | None:
    """For diagnostics: the last OSError message hit while writing, if any."""
    return _last_write_error
