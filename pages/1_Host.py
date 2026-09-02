import streamlit as st
from streamlit_autorefresh import st_autorefresh

from game_engine.state import get_store, LOBBY, QUESTION, REVEAL, FINISHED
from game_engine.questions import load_questions
from theme import page, banner, render_leaderboard, render_name_chips

page("Host", "🖥️")
banner("🖥️", "Host screen — create a game and run the room")

store = get_store()

# ---------------------------------------------------------------- no game yet
if "host_game_code" not in st.session_state:
    st.write("Start a new game to get a join code for the group.")
    try:
        questions = load_questions()
    except Exception as e:
        st.error(f"Couldn't load data/questions.json: {e}")
        st.stop()

    st.caption(f"{len(questions)} question(s) loaded from data/questions.json.")
    if st.button("Create new game", type="primary"):
        code = store.create_game(questions)
        st.session_state["host_game_code"] = code
        st.rerun()
    st.stop()

code = st.session_state["host_game_code"]
game = store.get(code)

if game is None:
    st.warning("That game no longer exists.")
    if st.button("Start a new one"):
        del st.session_state["host_game_code"]
        st.rerun()
    st.stop()

# ------------------------------------------------------------------- LOBBY
if game.phase == LOBBY:
    st_autorefresh(interval=1000, key="host_lobby_refresh")

    with st.container(border=True):
        st.header(f"Join code: `{code}`")
        st.write("Tell everyone to go to the Player screen and enter this code.")

        players = list(game.players.keys())
        st.subheader(f"Players joined ({len(players)})")
        if players:
            st.write(", ".join(players))
        else:
            st.caption("Waiting for players to join…")

    if st.button("Start game", type="primary", disabled=len(players) == 0):
        store.start_game(code)
        st.rerun()

# ---------------------------------------------------------------- QUESTION
elif game.phase == QUESTION:
    st_autorefresh(interval=1000, key="host_question_refresh")

    total = len(game.questions)
    q = game.current_question

    with st.container(border=True):
        st.caption(f"Question {game.current_index + 1} of {total}")
        st.header(q["question"])

        for i, opt in enumerate(q["options"]):
            st.write(f"{chr(65 + i)}. {opt}")

        remaining = int(game.seconds_remaining) + 1
        st.progress(min(1.0, game.seconds_elapsed / game.question_duration))
        st.metric("Time remaining", f"{max(0, remaining)}s")

        answered = sum(1 for p in game.players.values() if game.current_index in p.answers)
        st.write(f"**{answered} / {len(game.players)}** players have answered.")

    if game.is_time_up:
        store.reveal(code)
        st.rerun()

    if st.button("Reveal answer now"):
        store.reveal(code)
        st.rerun()

# ------------------------------------------------------------------ REVEAL
elif game.phase == REVEAL:
    st_autorefresh(interval=1000, key="host_reveal_refresh")

    total = len(game.questions)
    q = game.current_question

    with st.container(border=True):
        st.caption(f"Question {game.current_index + 1} of {total}")
        st.header(q["question"])

        correct_letter = chr(65 + q["correct_index"])
        for i, opt in enumerate(q["options"]):
            prefix = "✅" if i == q["correct_index"] else "◻️"
            st.write(f"{prefix} {chr(65 + i)}. {opt}")

        correct_names = [
            name for name, p in game.players.items()
            if game.current_index in p.answers and p.answers[game.current_index].correct
        ]
        missed_names = [name for name in game.players if name not in correct_names]

        st.write(f"**{len(correct_names)} / {len(game.players)}** players got it right (answer: {correct_letter}).")

        col_correct, col_missed = st.columns(2)
        with col_correct:
            st.markdown("**✅ Got it right**")
            render_name_chips(correct_names, tone="correct")
        with col_missed:
            st.markdown("**❌ Missed it**")
            render_name_chips(missed_names, tone="incorrect")

    st.subheader("Leaderboard so far")
    render_leaderboard(store.leaderboard(code), limit=10)

    is_last = game.current_index + 1 >= total
    label = "Show final results" if is_last else "Next question"
    if st.button(label, type="primary"):
        store.next_question(code)
        st.rerun()

# ---------------------------------------------------------------- FINISHED
elif game.phase == FINISHED:
    st.header("🏁 Final results")
    board = store.leaderboard(code)
    render_leaderboard(board)

    if not board:
        st.caption("No players joined this game.")

    st.divider()
    if st.button("Start a new game"):
        del st.session_state["host_game_code"]
        st.rerun()
