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
code, since some managed hosts mount the deployed app source read-only.
"""

import json
import os
import tempfile

_STATS_PATH = os.path.join(tempfile.gettempdir(), "zevo_kc_runtime_stats.json")

_last_error: str | None = None


def _read() -> dict:
    global _last_error
    try:
        with open(_STATS_PATH, "r") as f:
            data = json.load(f)
        _last_error = None
        return data
    except FileNotFoundError:
        _last_error = None  # normal on first run, not a real error
        return {"games_created": 0}
    except Exception as e:  # noqa: BLE001 - deliberately broad for diagnostics
        _last_error = f"read failed ({type(e).__name__}): {e}"
        return {"games_created": 0}


def _write(data: dict) -> None:
    global _last_error
    tmp_path = _STATS_PATH + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f)
        os.replace(tmp_path, _STATS_PATH)
        _last_error = None
    except Exception as e:  # noqa: BLE001 - deliberately broad; never break the app
        _last_error = f"write failed ({type(e).__name__}): {e}"


def increment_games_created() -> int:
    """Bump the persisted games-created counter and return the new total."""
    data = _read()
    data["games_created"] = data.get("games_created", 0) + 1
    _write(data)
    return data["games_created"]


def get_games_created() -> int:
    return _read().get("games_created", 0)


def get_last_error() -> str | None:
    """For diagnostics: the last read/write problem hit, if any."""
    return _last_error


def get_debug_info() -> dict:
    """For diagnostics: where the counter lives and what's on disk right now."""
    info = {"path": _STATS_PATH, "exists": os.path.exists(_STATS_PATH)}
    try:
        info["writable_dir"] = os.access(os.path.dirname(_STATS_PATH), os.W_OK)
    except Exception as e:  # noqa: BLE001
        info["writable_dir"] = f"check failed: {e}"
    if info["exists"]:
        try:
            with open(_STATS_PATH, "r") as f:
                info["raw_contents"] = f.read()
        except Exception as e:  # noqa: BLE001
            info["raw_contents"] = f"read failed: {e}"
    return info
