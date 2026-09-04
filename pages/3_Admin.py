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

sessions = history.get_all_sessions()

if not sessions:
    error = history.get_last_error()
    if error:
        st.error(f"Session history isn't loading: {error}")
    else:
        st.caption("No finished games recorded yet.")
    st.stop()


def _session_label(s: dict) -> str:
    return (
        f'{s["code"]} · {s.get("category") or "—"} · {s["played_at"]} '
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
st.caption(f'{session.get("category") or "—"} · played {session["played_at"]}')

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
    "Stored in a Google Sheet, so this list survives redeploys and reboots "
    "(unlike the games-hosted counter above, which still resets)."
)

error = history.get_last_error()
if error:
    st.caption(f"⚠️ {error}")
