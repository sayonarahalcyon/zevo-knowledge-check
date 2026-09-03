import datetime

import streamlit as st

from game_engine import history
from theme import page, banner

page("Admin", "🛠️")
banner("🛠️", "Admin — every agent who's played, their score, and when")

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

results = history.get_all_results()

if not results:
    st.caption("No finished games yet since the app's last deploy/reboot.")
else:
    rows = [
        {
            "Agent": r["name"],
            "Score": r["score"],
            "Category": r.get("category") or "—",
            "Game code": r.get("code", "—"),
            "Played": datetime.datetime.fromtimestamp(r["played_at"]).strftime("%b %d, %Y %I:%M %p"),
        }
        for r in sorted(results, key=lambda r: r["played_at"], reverse=True)
    ]
    st.subheader(f"{len(rows)} result(s)")
    st.dataframe(rows, use_container_width=True, hide_index=True)

st.caption(
    "Resets on every redeploy/reboot, same as the games-hosted counter — this is "
    "results since the app last restarted, not a permanent historical record."
)

error = history.get_last_error()
if error:
    st.caption(f"⚠️ {error}")
