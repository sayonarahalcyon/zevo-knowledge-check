"""Persisted history of finished games, for the admin drill-down view.

Unlike game_engine/stats.py's games-hosted counter, this is backed by a
Google Sheet rather than a local tempfile, specifically so it SURVIVES
redeploys and reboots — a plain code push used to silently wipe every
recorded session, which is the problem this file exists to fix.

Sheet layout (one row per player, per question, per finished game):
    code | category | played_at | player_name | player_score | question |
    your_answer | correct_answer | result | points

"result" is the literal string "Correct" or "Wrong" (kept human-readable
for anyone opening the sheet directly). "played_at" is a display string
("Sep 04, 2026 02:13 AM"), not a timestamp — rows are always appended in
chronological order, so grouping preserves that order and we simply
reverse it for "newest first".

Requires two Streamlit secrets (Settings -> Secrets on Streamlit Community
Cloud):
    history_sheet_id = "<the spreadsheet ID from its URL>"
    [gcp_service_account]
    type = "service_account"
    ... (the rest of the service-account JSON key, as a TOML table)

The service account's client_email must be shared on the sheet as an
Editor, or writes will fail with a permission error.

If those secrets aren't set (e.g. local dev), every function below fails
soft: writes are silently dropped and reads return an empty list, with the
problem surfaced via get_last_error()/get_debug_info() same as before.
"""

import time
from typing import Dict, List, Optional

import streamlit as st

_SHEET_HEADER = [
    "code", "category", "played_at", "player_name", "player_score",
    "question", "your_answer", "correct_answer", "result", "points",
]

_last_error: Optional[str] = None


def _configured() -> bool:
    try:
        return bool(st.secrets.get("history_sheet_id")) and "gcp_service_account" in st.secrets
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _worksheet():
    """The single worksheet (tab) we read/write, authorized once per process."""
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ]
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(st.secrets["history_sheet_id"])
    return sheet.sheet1


def record_game_result(code: str, category_label: Optional[str], players: List[Dict]) -> None:
    """Append rows for a game that just finished: one row per player per question.

    players: list of {"name": str, "score": int, "answers": [ {...}, ... ]},
    where each answer dict has "question", "your_answer" (None if unanswered),
    "correct_answer", "correct" (bool), and "points".
    """
    global _last_error
    if not _configured():
        _last_error = "Google Sheet not configured (missing history_sheet_id / gcp_service_account secrets)"
        return

    played_at = time.strftime("%b %d, %Y %I:%M %p")
    rows = []
    for p in players:
        for a in p.get("answers", []):
            rows.append([
                code,
                category_label or "",
                played_at,
                p.get("name", ""),
                p.get("score", 0),
                a.get("question", ""),
                a.get("your_answer") or "(no answer)",
                a.get("correct_answer", ""),
                "Correct" if a.get("correct") else "Wrong",
                a.get("points", 0),
            ])

    if not rows:
        return

    try:
        _worksheet().append_rows(rows, value_input_option="RAW")
        _last_error = None
    except Exception as e:  # noqa: BLE001 - never let a sheet hiccup break the game
        _last_error = f"write failed ({type(e).__name__}): {e}"


def get_all_sessions() -> List[dict]:
    """Every finished game, newest first, grouped session -> player -> answers."""
    global _last_error
    if not _configured():
        _last_error = "Google Sheet not configured (missing history_sheet_id / gcp_service_account secrets)"
        return []

    try:
        records = _read_records()
        _last_error = None
    except Exception as e:  # noqa: BLE001
        _last_error = f"read failed ({type(e).__name__}): {e}"
        return []

    sessions_by_key: Dict[tuple, dict] = {}
    order: List[tuple] = []

    for row in records:
        code = row.get("code")
        played_at = row.get("played_at")
        session_key = (code, played_at)
        if session_key not in sessions_by_key:
            sessions_by_key[session_key] = {
                "code": code,
                "category": row.get("category"),
                "played_at": played_at,
                "players": {},
                "player_order": [],
            }
            order.append(session_key)
        session = sessions_by_key[session_key]

        player_name = row.get("player_name")
        if player_name not in session["players"]:
            session["players"][player_name] = {
                "name": player_name,
                "score": _to_int(row.get("player_score")),
                "answers": [],
            }
            session["player_order"].append(player_name)
        session["players"][player_name]["answers"].append({
            "question": row.get("question"),
            "your_answer": row.get("your_answer"),
            "correct_answer": row.get("correct_answer"),
            "correct": row.get("result") == "Correct",
            "points": _to_int(row.get("points")),
        })

    sessions = []
    for key in reversed(order):  # newest first (rows are appended chronologically)
        s = sessions_by_key[key]
        sessions.append({
            "code": s["code"],
            "category": s["category"],
            "played_at": s["played_at"],
            "players": [s["players"][name] for name in s["player_order"]],
        })
    return sessions


@st.cache_data(ttl=15, show_spinner=False)
def _read_records() -> List[dict]:
    """Raw sheet rows as dicts, cached briefly so a busy Admin page doesn't
    hammer the Sheets API on every rerun."""
    return _worksheet().get_all_records(expected_headers=_SHEET_HEADER)


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def get_last_error() -> Optional[str]:
    """For diagnostics: the last read/write problem hit, if any."""
    return _last_error


def get_debug_info() -> dict:
    """For diagnostics: whether the sheet is configured and reachable."""
    info = {"configured": _configured()}
    if info["configured"]:
        try:
            info["sheet_title"] = _worksheet().spreadsheet.title
            info["row_count"] = _worksheet().row_count
        except Exception as e:  # noqa: BLE001
            info["connection_error"] = f"{type(e).__name__}: {e}"
    return info
