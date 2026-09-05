"""Persisted history of finished games, for the admin drill-down view.

Two storage layers, on purpose:

1. A local tempfile (same as before) — this is what the Admin page reads
   from, so it always shows results immediately, with no setup required.
   Same caveat as game_engine/stats.py: it lives in the system temp
   directory, not the repo, so it resets whenever the app redeploys or
   reboots. It's "results since last deploy", not permanent history.

2. A Google Sheet mirror — every finished game is ALSO appended there,
   one row per player per question, so there's a copy that survives
   redeploys/reboots even though the in-app view doesn't. This requires
   two Streamlit secrets that aren't set up by default (Settings ->
   Secrets on Streamlit Community Cloud):
       history_sheet_id = "<the spreadsheet ID from its URL>"
       [gcp_service_account]
       type = "service_account"
       ... (the rest of the service-account JSON key, as a TOML table)
   The service account's client_email must be shared on the sheet as an
   Editor, or the sync will fail. Until those secrets are set, the sheet
   sync silently no-ops (never breaks the game or blocks the Admin page)
   and the failure reason is available via get_last_sheet_error().

Each finished game is stored locally as ONE session record:
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

Solo plays (see record_solo_result / get_all_solo_plays near the bottom)
are stored separately from all of the above, in their own tempfile - a
solo play has no join code or other players, so it doesn't fit the
session shape. Solo plays ARE also mirrored to the same Google Sheet,
but on their own "Solo Plays" tab (created automatically the first time
a solo play is recorded, if it doesn't exist yet) rather than the
multiplayer tab, since the row shape is different (a player name instead
of a join code, no other players). Uses the same two secrets as the
multiplayer mirror above; failures are available via
get_last_solo_sheet_error() and never block the Leaderboard page.
"""

import json
import os
import tempfile
import time
from typing import Dict, List, Optional

import streamlit as st

_HISTORY_PATH = os.path.join(tempfile.gettempdir(), "zevo_kc_game_history.json")
_SOLO_PATH = os.path.join(tempfile.gettempdir(), "zevo_kc_solo_history.json")

_SHEET_HEADER = [
    "code", "category", "played_at", "player_name", "player_score",
    "question", "your_answer", "correct_answer", "result", "points",
]

_SOLO_SHEET_HEADER = [
    "name", "category", "played_at", "score",
    "question", "your_answer", "correct_answer", "result", "points",
]

_last_error: Optional[str] = None
_last_sheet_error: Optional[str] = None
_last_solo_error: Optional[str] = None
_last_solo_sheet_error: Optional[str] = None


# ---------------------------------------------------------------------
# Local tempfile storage - the source of truth for the Admin page itself.
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# Google Sheet mirror - best-effort, never blocks the game or the page.
# ---------------------------------------------------------------------

def _sheet_configured() -> bool:
    try:
        return bool(st.secrets.get("history_sheet_id")) and "gcp_service_account" in st.secrets
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _worksheet():
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


def _sync_to_sheet(code: str, category_label: Optional[str], played_at: float, players: List[Dict]) -> None:
    """Best-effort mirror of a finished game to the Google Sheet. Never
    raises - any failure is recorded via get_last_sheet_error() and the
    local tempfile write (the one the Admin page actually depends on) has
    already happened by the time this runs."""
    global _last_sheet_error
    if not _sheet_configured():
        _last_sheet_error = "Google Sheet not configured (missing history_sheet_id / gcp_service_account secrets)"
        return

    played_at_display = time.strftime("%b %d, %Y %I:%M %p", time.localtime(played_at))
    rows = []
    for p in players:
        for a in p.get("answers", []):
            rows.append([
                code,
                category_label or "",
                played_at_display,
                p.get("name", ""),
                p.get("score", 0),
                a.get("question", ""),
                a.get("your_answer") or "(no answer)",
                a.get("correct_answer", ""),
                "Correct" if a.get("correct") else "Wrong",
                a.get("points", 0),
            ])

    if not rows:
        _last_sheet_error = None
        return

    try:
        _worksheet().append_rows(rows, value_input_option="RAW")
        _last_sheet_error = None
    except Exception as e:  # noqa: BLE001 - a sheet hiccup must never break the game
        _last_sheet_error = f"Google Sheet sync failed ({type(e).__name__}): {e}"


@st.cache_resource(show_spinner=False)
def _solo_worksheet():
    """The "Solo Plays" tab of the same spreadsheet used for multiplayer
    history. Created automatically (with a header row) the first time a
    solo play is recorded, if it doesn't already exist."""
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ]
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(st.secrets["history_sheet_id"])
    try:
        return sheet.worksheet("Solo Plays")
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title="Solo Plays", rows=1000, cols=len(_SOLO_SHEET_HEADER))
        ws.append_row(_SOLO_SHEET_HEADER, value_input_option="RAW")
        return ws


def _sync_solo_to_sheet(name: str, category_label: Optional[str], played_at: float, score: int, answers: List[Dict]) -> None:
    """Best-effort mirror of one finished solo play to the "Solo Plays"
    tab. Never raises - any failure is recorded via
    get_last_solo_sheet_error() and the local tempfile write (the one the
    Leaderboard page actually depends on) has already happened by the
    time this runs."""
    global _last_solo_sheet_error
    if not _sheet_configured():
        _last_solo_sheet_error = "Google Sheet not configured (missing history_sheet_id / gcp_service_account secrets)"
        return

    played_at_display = time.strftime("%b %d, %Y %I:%M %p", time.localtime(played_at))
    rows = []
    for a in answers:
        rows.append([
            name,
            category_label or "",
            played_at_display,
            score,
            a.get("question", ""),
            a.get("your_answer") or "(no answer)",
            a.get("correct_answer", ""),
            "Correct" if a.get("correct") else "Wrong",
            a.get("points", 0),
        ])

    if not rows:
        _last_solo_sheet_error = None
        return

    try:
        _solo_worksheet().append_rows(rows, value_input_option="RAW")
        _last_solo_sheet_error = None
    except Exception as e:  # noqa: BLE001 - a sheet hiccup must never break the game
        _last_solo_sheet_error = f"Google Sheet sync failed ({type(e).__name__}): {e}"


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def record_game_result(code: str, category_label: Optional[str], players: List[Dict]) -> None:
    """Record one session for a game that just finished, both locally
    (for the Admin page) and, if configured, in the Google Sheet mirror.

    players: list of {"name": str, "score": int, "answers": [ {...}, ... ]},
    where each answer dict has "question", "your_answer" (None if unanswered),
    "correct_answer", "correct" (bool), and "points".
    """
    played_at = time.time()

    records = _read_all()
    records.append(
        {
            "code": code,
            "category": category_label,
            "played_at": played_at,
            "players": players,
        }
    )
    _write_all(records)

    _sync_to_sheet(code, category_label, played_at, players)


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
    """For diagnostics: the last LOCAL read/write problem hit, if any.
    This is what the Admin page depends on - a problem here means the
    page itself can't show results."""
    return _last_error


def get_last_sheet_error() -> Optional[str]:
    """For diagnostics: the last Google Sheet sync problem hit, if any
    (including simply not being configured yet). This never affects what
    the Admin page shows - it's purely about the durable mirror."""
    return _last_sheet_error


def check_sheet_connection() -> str:
    """On-demand LIVE check of the Google Sheet mirror - actually tries to
    open the spreadsheet and list its tabs right now, rather than reporting
    a possibly-stale get_last_*_error() value (those only update the next
    time a game/solo play finishes, so "no error yet" can just mean nothing
    has tried since the app last restarted). Never raises; always returns a
    plain-language result string."""
    if not _sheet_configured():
        return "Not configured: missing history_sheet_id / gcp_service_account secret(s)."
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]
        creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(st.secrets["history_sheet_id"])
        tabs = [ws.title for ws in sheet.worksheets()]
        return f'Connected OK to "{sheet.title}". Tabs: {", ".join(tabs) or "(none)"}.'
    except Exception as e:  # noqa: BLE001 - surfacing the real error is the whole point here
        return f"Connection failed ({type(e).__name__}): {e}"


def get_debug_info() -> dict:
    """For diagnostics: where the history file lives, what's on disk right
    now, and whether the Google Sheet mirror is configured."""
    info = {"path": _HISTORY_PATH, "exists": os.path.exists(_HISTORY_PATH)}
    try:
        info["writable_dir"] = os.access(os.path.dirname(_HISTORY_PATH), os.W_OK)
    except Exception as e:  # noqa: BLE001
        info["writable_dir"] = f"check failed: {e}"
    info["sheet_configured"] = _sheet_configured()
    return info


# ---------------------------------------------------------------------
# Solo play history - separate from the multiplayer store above, since a
# solo play has no join code or other players. Local tempfile only for
# now (same "resets on redeploy/reboot" caveat as everything else here) -
# not mirrored to the Google Sheet.
# ---------------------------------------------------------------------

def _read_solo() -> List[dict]:
    global _last_solo_error
    try:
        with open(_SOLO_PATH, "r") as f:
            data = json.load(f)
        _last_solo_error = None
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        _last_solo_error = None  # normal before the first solo game finishes
        return []
    except Exception as e:  # noqa: BLE001 - deliberately broad for diagnostics
        _last_solo_error = f"read failed ({type(e).__name__}): {e}"
        return []


def _write_solo(records: List[dict]) -> None:
    global _last_solo_error
    tmp_path = _SOLO_PATH + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(records, f)
        os.replace(tmp_path, _SOLO_PATH)
        _last_solo_error = None
    except Exception as e:  # noqa: BLE001 - deliberately broad; never break the app
        _last_solo_error = f"write failed ({type(e).__name__}): {e}"


def record_solo_result(name: str, category_label: Optional[str], score: int, answers: List[Dict]) -> None:
    """Record one finished solo play.

    answers: list of {"question", "your_answer" (None if unanswered),
    "correct_answer", "correct" (bool), "points"}, one per question.
    """
    played_at = time.time()
    records = _read_solo()
    records.append(
        {
            "name": name,
            "category": category_label,
            "played_at": played_at,
            "score": score,
            "answers": answers,
        }
    )
    _write_solo(records)

    _sync_solo_to_sheet(name, category_label, played_at, score, answers)


def get_all_solo_plays() -> List[dict]:
    """Every finished solo play, newest first."""
    return sorted(_read_solo(), key=lambda r: r.get("played_at", 0), reverse=True)


def get_last_solo_error() -> Optional[str]:
    """For diagnostics: the last read/write problem hit for solo history."""
    return _last_solo_error


def get_last_solo_sheet_error() -> Optional[str]:
    """For diagnostics: the last Google Sheet sync problem hit for solo
    plays, if any (including simply not being configured yet). This never
    affects what the Leaderboard page shows - it's purely about the
    durable "Solo Plays" tab mirror."""
    return _last_solo_sheet_error


def delete_solo_plays(names: List[str]) -> int:
    """Remove every solo play for the given player name(s) from local
    history (exact, case-sensitive match on name) - e.g. to clean up test
    plays. Returns how many plays were removed. Does not touch the Google
    Sheet mirror; see delete_solo_sheet_rows() for that."""
    if not names:
        return 0
    name_set = set(names)
    records = _read_solo()
    kept = [r for r in records if r.get("name") not in name_set]
    removed = len(records) - len(kept)
    if removed:
        _write_solo(kept)
    return removed


def delete_solo_sheet_rows(names: List[str]) -> str:
    """Best-effort removal of every row on the "Solo Plays" tab whose name
    column matches one of the given player name(s). Never raises; always
    returns a plain-language result string."""
    if not names:
        return "No names given."
    if not _sheet_configured():
        return "Not configured: missing history_sheet_id / gcp_service_account secret(s)."
    try:
        ws = _solo_worksheet()
        values = ws.get_all_values()
        if not values:
            return "Sheet is empty, nothing to remove."
        name_set = set(names)
        # Row 1 is the header; sheet rows are 1-indexed and line up with
        # this full read, so row number = list index + 1.
        rows_to_delete = [
            i + 1 for i, row in enumerate(values)
            if i > 0 and row and row[0] in name_set
        ]
        for row_num in sorted(rows_to_delete, reverse=True):
            ws.delete_rows(row_num)
        if rows_to_delete:
            return f"Removed {len(rows_to_delete)} row(s) from the Solo Plays tab."
        return "No matching rows found on the Solo Plays tab."
    except Exception as e:  # noqa: BLE001 - surfacing the real error is the whole point here
        return f"Sheet cleanup failed ({type(e).__name__}): {e}"
