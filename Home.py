import streamlit as st

from theme import page, banner

page("", "⚡")
banner("⚡")

st.write(
    "A live, group quiz for coworking sessions — everyone joins with a code and "
    "answers in real time, like Kahoot."
)

st.divider()

col1, col2, col3 = st.columns(3)
with col1:
    with st.container(border=True):
        st.subheader("🖥️ Hosting?")
        st.write("Start a game, get a join code, and control the pace for the group.")
        st.page_link("pages/1_Host.py", label="Go to Host screen", icon="🖥️")

with col2:
    with st.container(border=True):
        st.subheader("🎮 Playing?")
        st.write("Enter the code from the host's screen and join in.")
        st.page_link("pages/2_Play.py", label="Go to Player screen", icon="🎮")

with col3:
    with st.container(border=True):
        st.subheader("🧑‍🎓 Practicing solo?")
        st.write("No host or code needed — play a category on your own, against the clock.")
        st.page_link("pages/4_Solo.py", label="Go to Solo practice", icon="🧑‍🎓")

st.divider()
st.caption(
    "Everyone (host and all players) needs to open the same deployed app URL "
    "for scores to sync — this only works while it's all one running app."
)
st.page_link("pages/5_Leaderboard.py", label="See everyone's solo scores", icon="🏆")
