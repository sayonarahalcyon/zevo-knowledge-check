import streamlit as st

from theme import page, banner

page("", "⚡")
banner("⚡")

st.write(
    "A live, group quiz for coworking sessions — everyone joins with a code and "
    "answers in real time, like Kahoot."
)

st.divider()

col1, col2 = st.columns(2)
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

st.divider()
st.caption(
    "Everyone (host and all players) needs to open the same deployed app URL "
    "for scores to sync — this only works while it's all one running app."
)
