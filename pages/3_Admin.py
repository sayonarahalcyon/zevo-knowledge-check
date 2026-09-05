import datetime
import json
import re
from collections import defaultdict

import streamlit as st

from game_engine import history
from theme import page, banner

page("Admin", "🛠️")
banner("🛠️", "Admin — every session, its agents, scores, and answers")

# Locked behind a password set in the app's Streamlit secrets (Manage app ->
# Settings -> Secrets: admin_password = "..."). If no secret is set yet, the
# page stays open (with a visible warning) so this isn't a hard blocker.
try:
    ADMIN_PASSWORD = st.secrets.get("admin_password")
except Exception:
    ADMIN_PASSWORD = None

if "admin_authed" not in st.session_state:
    st.session_state["admin_authed"] = False

if ADMIN_PASSWORD and not st.session_state["admin_authed"]:
    st.write("This page is restricted. Enter the admin password to continue.")
    entered = st.text_input("Admin password", type="password")
    if st.button("Unlock", type="primary"):
        if entered == ADMIN_PASSWORD:
            st.session_state["admin_authed"] = True
            st.rerun()
        else:
            st.error("That's not the admin password.")
    st.stop()

if not ADMIN_PASSWORD:
    st.warning(
        "No admin password is set, so this page is open to anyone with the link. "
        "Set `admin_password` in the app's Settings → Secrets panel on Streamlit "
        "Community Cloud to lock it down."
    )


# ---------------------------------------------------------------------
# Restore sessions from a backup file - for when a redeploy/reboot wiped
# the local tempfile before those sessions made it into the Google Sheet
# mirror (or before the Sheet was even set up). Only touches the local
# list below; never re-syncs to the Sheet, since a backup like this was
# usually taken FROM a Sheet-seeded snapshot in the first place and
# re-syncing would just duplicate rows there.
# ---------------------------------------------------------------------

def _restore_from_backup(uploaded_file) -> tuple[int, int]:
    try:
        data = json.load(uploaded_file)
    except Exception:
        st.error("That file isn't valid JSON.")
        return 0, 0

    backup_sessions = data.get("sessions", []) if isinstance(data, dict) else []
    if not backup_sessions:
        st.warning("That file doesn't look like a session backup (no \"sessions\" list found).")
        return 0, 0

    existing = history._read_all()
    existing_keys = {(r.get("code"), r.get("played_at")) for r in existing if "players" in r}

    restored = 0
    skipped = 0
    for sess in backup_sessions:
        clean_players = []
        for p in sess.get("players", []):
            answers = p.get("answers")
            if not isinstance(answers, list):
                continue  # e.g. a test session's answers stored as a plain string - not restorable
            # Strip a "(N pts)" tally that may have been appended to the name
            # for readability in a downloaded copy of this file.
            name = re.sub(r"\s*\(\d+ pts\)\s*$", "", str(p.get("name", ""))).strip()
            clean_players.append({"name": name, "score": p.get("score", 0), "answers": answers})

        if not clean_players:
            continue  # nothing restorable in this session

        try:
            played_at = datetime.datetime.strptime(
                sess.get("played_at_display", ""), "%b %d, %Y %I:%M %p"
            ).timestamp()
        except (TypeError, ValueError):
            played_at = None

        key = (sess.get("code"), played_at)
        if played_at is not None and key in existing_keys:
            skipped += 1
            continue

        existing.append(
            {
                "code": sess.get("code"),
                "category": sess.get("category"),
                "played_at": played_at if played_at is not None else 0,
                "players": clean_players,
            }
        )
        existing_keys.add(key)
        restored += 1

    if restored:
        history._write_all(existing)
    return restored, skipped


with st.expander("🩹 Restore sessions from a backup file", expanded=not history.get_all_sessions()):
    st.caption(
        "If a game finished but got wiped from the list below by a later "
        "redeploy/reboot (before it reached the Google Sheet mirror, or before "
        "the Sheet was set up), upload a backup JSON here to add it back. This "
        "only affects the list on this page - it never re-syncs to the Sheet."
    )
    backup_file = st.file_uploader("Backup JSON", type="json", key="restore_backup_upload")
    if st.button("Restore from this file", disabled=backup_file is None):
        restored, skipped = _restore_from_backup(backup_file)
        if restored:
            st.success(f"Restored {restored} session(s). Refreshing…")
            st.rerun()
        elif skipped:
            st.info("Nothing new to restore - those sessions are already in the list below.")
        else:
            st.warning("No valid sessions found in that file.")

def _played_str(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%b %d, %Y %I:%M %p")


# ---------------------------------------------------------------------
# Solo plays - same content as the standalone Leaderboard page, folded in
# here too so admins don't have to leave this page to check it. Placed
# before the multiplayer section below (which can st.stop() the rest of
# the page when there are no multiplayer sessions yet), so this always
# shows regardless of multiplayer history.
# ---------------------------------------------------------------------

st.divider()
st.subheader("🧑‍🎓 Solo plays")

solo_plays = history.get_all_solo_plays()

if not solo_plays:
    solo_error = history.get_last_solo_error()
    if solo_error:
        st.error(f"Solo history isn't loading: {solo_error}")
    else:
        st.caption("No solo games played yet since the app's last deploy/reboot.")
else:
    solo_by_player = defaultdict(list)
    for p in solo_plays:
        solo_by_player[p["name"]].append(p)

    solo_summary_rows = [
        {
            "Player": name,
            "Plays": len(rows),
            "Best score": max(r["score"] for r in rows),
            "Last played": _played_str(max(r["played_at"] for r in rows)),
        }
        for name, rows in solo_by_player.items()
    ]
    solo_summary_rows.sort(key=lambda r: r["Best score"], reverse=True)

    st.caption(f"{len(solo_by_player)} player(s) · {len(solo_plays)} play(s) total")
    st.dataframe(solo_summary_rows, use_container_width=True, hide_index=True)

    solo_names = ["All players"] + sorted(solo_by_player.keys(), key=str.lower)
    solo_choice = st.selectbox("Filter by player", options=solo_names, key="admin_solo_filter")
    solo_filtered = solo_plays if solo_choice == "All players" else solo_by_player[solo_choice]

    for p in solo_filtered:
        header = f'{p["name"]} — {p["score"]} pts · {p.get("category") or "—"} · {_played_str(p["played_at"])}'
        with st.expander(header):
            rows = [
                {
                    "Question": a["question"],
                    "Your answer": a["your_answer"] or "(no answer)",
                    "Correct answer": a["correct_answer"],
                    "Result": "✅ Correct" if a["correct"] else "❌ Wrong",
                    "Points": a["points"],
                }
                for a in p["answers"]
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("🗑️ Remove test / mistaken plays"):
        if st.session_state.get("admin_solo_delete_result"):
            st.success(st.session_state.pop("admin_solo_delete_result"))
        names_to_remove = st.multiselect(
            "Select player(s) to remove from the list above",
            options=sorted(solo_by_player.keys(), key=str.lower),
            key="admin_solo_delete_select",
        )
        also_sheet = st.checkbox(
            "Also remove their rows from the Google Sheet's Solo Plays tab",
            value=True,
            key="admin_solo_delete_sheet",
        )
        if st.button("Delete selected", disabled=not names_to_remove):
            removed = history.delete_solo_plays(names_to_remove)
            msg = f"Removed {removed} play(s) locally."
            if also_sheet:
                msg += " " + history.delete_solo_sheet_rows(names_to_remove)
            st.session_state["admin_solo_delete_result"] = msg
            st.rerun()

    solo_sheet_error = history.get_last_solo_sheet_error()
    if solo_sheet_error:
        st.caption(f"📄 Solo Sheet mirror: ⚠️ {solo_sheet_error}")
    else:
        st.caption('📄 Every solo play above is also mirrored to a Google Sheet ("Solo Plays" tab).')

    solo_error = history.get_last_solo_error()
    if solo_error:
        st.caption(f"⚠️ {solo_error}")

st.divider()

sessions = history.get_all_sessions()

if not sessions:
    error = history.get_last_error()
    if error:
        st.error(f"Session history isn't loading: {error}")
    else:
        st.caption("No finished games yet since the app's last deploy/reboot.")
    st.stop()


def _session_label(s: dict) -> str:
    return (
        f'{s["code"]} · {s.get("category") or "—"} · {_played_str(s["played_at"])} '
        f'· {len(s["players"])} player(s)'
    )


st.subheader(f"{len(sessions)} session(s)")

choice = st.selectbox(
    "Choose a session to drill into",
    options=range(len(sessions)),
    format_func=lambda i: _session_label(sessions[i]),
)
session = sessions[choice]

st.divider()
st.markdown(f"### Join code `{session['code']}`")
st.caption(f'{session.get("category") or "—"} · played {_played_str(session["played_at"])}')

if session.get("legacy"):
    st.caption(
        "⚠️ This session was recorded before per-question answers were tracked, "
        "so only final scores are available below."
    )

players_sorted = sorted(session["players"], key=lambda p: p["score"], reverse=True)
medals = {0: "🥇", 1: "🥈", 2: "🥉"}

for rank, p in enumerate(players_sorted):
    badge = medals.get(rank, f"#{rank + 1}")
    with st.expander(f'{badge} **{p["name"]}** — {p["score"]} pts'):
        if not p["answers"]:
            st.caption("No per-question detail was recorded for this session.")
            continue
        rows = [
            {
                "Question": a["question"],
                "Your answer": a["your_answer"] or "(no answer)",
                "Correct answer": a["correct_answer"],
                "Result": "✅ Correct" if a["correct"] else "❌ Wrong",
                "Points": a["points"],
            }
            for a in p["answers"]
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "This list resets on every redeploy/reboot, same as the games-hosted "
    "counter — it's results since the app last restarted, not a permanent "
    "historical record."
)

sheet_error = history.get_last_sheet_error()
if sheet_error:
    st.caption(f"📄 Google Sheet mirror: ⚠️ {sheet_error}")
else:
    st.caption("📄 Every game above is also mirrored to a Google Sheet, so it survives redeploys too.")

if st.button("🔄 Test Google Sheet connection now"):
    st.caption(history.check_sheet_connection())

error = history.get_last_error()
if error:
    st.caption(f"⚠️ {error}")
