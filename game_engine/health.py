"""
Lightweight server-side health monitoring: a background heartbeat, plus a
log of any operation that took unusually long, so a reported freeze can be
checked against real evidence instead of only what a player says happened.

What this CAN prove: whether the shared server process itself stalled -
e.g. the game lock in state.py getting held for a long time by a slow
network call. The heartbeat thread runs independently of that lock (it's
a separate background thread doing nothing but sleep + a local file
write), so if it keeps ticking on schedule, the server was not hung, full
stop. A gap in it is real evidence of a server-side stall.

What this CANNOT prove: anything on a player's own device or network. A
dropped wifi connection, a laptop going to sleep, or a browser tab that
froze locally all look identical to "nothing happened" from here - there
is no way to instrument someone else's phone from this app. A clean
heartbeat log means the SERVER was fine; it doesn't mean the player's
report was wrong.

One more wrinkle: Streamlit Community Cloud puts an idle app to sleep
after a stretch with no visitors at all, and going to sleep is normal,
not a bug. A heartbeat gap that lines up with a quiet overnight stretch
with nobody around isn't suspicious by itself - what actually matters is
a gap that overlaps a session's played_at time on the Admin page (i.e.
a game was actually being played right then).

Stored locally only (same tradeoff as the old games-hosted counter in
stats.py) - this resets on every redeploy/reboot. That's fine here: it's
for diagnosing what happened on the CURRENTLY running process, not a
permanent record like the Google Sheet-backed game history is.
"""

import json
import os
import tempfile
import threading
import time
from typing import List, Optional

_HEALTH_PATH = os.path.join(tempfile.gettempdir(), "zevo_kc_health_log.json")

_HEARTBEAT_INTERVAL = 10   # seconds between heartbeats
_GAP_THRESHOLD = 30        # a gap bigger than this (3x the interval) gets flagged
_SLOW_OP_THRESHOLD = 3.0   # seconds - an operation slower than this gets logged
_MAX_ENTRIES = 1000        # ring buffer size, per log, so the file can't grow forever

_state_lock = threading.Lock()
_watchdog_started = False


def _read() -> dict:
    try:
        with open(_HEALTH_PATH, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"heartbeats": [], "slow_ops": []}
        data.setdefault("heartbeats", [])
        data.setdefault("slow_ops", [])
        return data
    except Exception:  # noqa: BLE001 - diagnostics only, never worth breaking the app
        return {"heartbeats": [], "slow_ops": []}


def _write(data: dict) -> None:
    tmp_path = _HEALTH_PATH + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f)
        os.replace(tmp_path, _HEALTH_PATH)
    except Exception:  # noqa: BLE001 - diagnostics only, never worth breaking the app
        pass


def _append_heartbeat() -> None:
    with _state_lock:
        data = _read()
        data["heartbeats"].append(time.time())
        data["heartbeats"] = data["heartbeats"][-_MAX_ENTRIES:]
        _write(data)


def record_slow_operation(name: str, seconds: float) -> None:
    """Log any operation that could stall the whole app if it hangs (e.g. a
    Google Sheets network call) once it's taken longer than
    _SLOW_OP_THRESHOLD seconds. Cheap no-op for the normal, fast case."""
    if seconds < _SLOW_OP_THRESHOLD:
        return
    with _state_lock:
        data = _read()
        data["slow_ops"].append({"name": name, "seconds": round(seconds, 1), "at": time.time()})
        data["slow_ops"] = data["slow_ops"][-_MAX_ENTRIES:]
        _write(data)


def _watchdog_loop() -> None:
    while True:
        _append_heartbeat()
        time.sleep(_HEARTBEAT_INTERVAL)


def start_watchdog() -> None:
    """Start the background heartbeat thread, once per running process.
    Safe to call on every page load - only the very first call actually
    starts anything, everything after that is a no-op."""
    global _watchdog_started
    with _state_lock:
        if _watchdog_started:
            return
        _watchdog_started = True
    threading.Thread(target=_watchdog_loop, daemon=True).start()


def get_last_heartbeat() -> Optional[float]:
    beats = _read().get("heartbeats", [])
    return max(beats) if beats else None


def get_heartbeat_gaps(threshold: float = _GAP_THRESHOLD) -> List[dict]:
    """Every gap between consecutive heartbeats bigger than `threshold`
    seconds, oldest first. Each is either a genuine server stall or just
    the app sleeping / nobody around - cross-check against session times
    on the Admin page to tell which."""
    beats = sorted(_read().get("heartbeats", []))
    gaps = []
    for a, b in zip(beats, beats[1:]):
        gap = b - a
        if gap > threshold:
            gaps.append({"from": a, "to": b, "seconds": round(gap, 1)})
    return gaps


def get_slow_operations() -> List[dict]:
    """Every logged slow operation, newest first."""
    return sorted(_read().get("slow_ops", []), key=lambda r: r.get("at", 0), reverse=True)
