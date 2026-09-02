import streamlit as st
from streamlit_autorefresh import st_autorefresh

from game_engine.state import get_store, LOBBY, QUESTION, REVEAL, FINISHED

st.set_page_config(page_title="Play — Live Knowledge Check", page_icon="🎮", layout="centered")

store = get_store()

st.title("🎮 Play")

# ------------------------------------------------------------------ JOIN FORM
if "player_name" not in st.session_state or "player_code" not in st.session_state:
    with st.form("join_form"):
        name = st.text_input("Your name")
        code = st.text_input("Game code", max_chars=4).upper()
        submitted = st.form_submit_button("Join game", type="primary")

    if submitted:
        ok, message = store.join(code, name)
        if ok:
            st.session_state["player_name"] = name.strip()
            st.session_state["player_code"] = code.strip().upper()
            st.rerun()
        else:
            st.error(message)
    st.stop()

name = st.session_state["player_name"]
code = st.session_state["player_code"]
game = store.get(code)

if game is None:
    st.warning("That game is no longer available.")
    if st.button("Leave"):
        del st.session_state["player_name"]
        del st.session_state["player_code"]
        st.rerun()
    st.stop()

st.caption(f"Playing as **{name}** in game `{code}`")

# ------------------------------------------------------------------- LOBBY
if game.phase == LOBBY:
    st_autorefresh(interval=1000, key="player_lobby_refresh")
    st.info("Waiting for the host to start the game…")
    st.write(f"{len(game.players)} player(s) have joined so far.")

# ---------------------------------------------------------------- QUESTION
elif game.phase == QUESTION:
    st_autorefresh(interval=1000, key="player_question_refresh")

    player = game.players.get(name)
    already_answered = player is not None and game.current_index in player.answers

    total = len(game.questions)
    q = game.current_question
    st.caption(f"Question {game.current_index + 1} of {total}")
    st.header(q["question"])

    remaining = max(0, int(game.seconds_remaining) + 1)

    if already_answered or game.is_time_up:
        if already_answered:
            picked = player.answers[game.current_index].choice_index
            st.success(f"Answer locked in: {chr(65 + picked)}. {q['options'][picked]}")
        else:
            st.warning("Time's up — no answer submitted.")
        st.caption("Waiting for the host to reveal the answer…")
    else:
        st.metric("Time remaining", f"{remaining}s")
        cols = st.columns(2)
        for i, opt in enumerate(q["options"]):
            col = cols[i % 2]
            if col.button(f"{chr(65 + i)}. {opt}", key=f"opt_{game.current_index}_{i}", use_container_width=True):
                store.submit_answer(code, name, i)
                st.rerun()

# ------------------------------------------------------------------ REVEAL
elif game.phase == REVEAL:
    st_autorefresh(interval=1000, key="player_reveal_refresh")

    player = game.players.get(name)
    q = game.current_question
    correct_letter = chr(65 + q["correct_index"])
    correct_text = q["options"][q["correct_index"]]

    result = player.answers.get(game.current_index) if player else None
    if result and result.correct:
        st.success(f"✅ Correct! +{result.points} points")
    elif result:
        st.error(f"❌ Not quite. Correct answer: {correct_letter}. {correct_text}")
    else:
        st.warning(f"No answer submitted. Correct answer: {correct_letter}. {correct_text}")

    board = store.leaderboard(code)
    names_in_order = [n for n, _ in board]
    rank = names_in_order.index(name) + 1 if name in names_in_order else None
    my_score = player.score if player else 0
    st.metric("Your score", my_score, delta=f"Rank #{rank}" if rank else None)

    st.caption("Waiting for the host to move to the next question…")

# ---------------------------------------------------------------- FINISHED
elif game.phase == FINISHED:
    board = store.leaderboard(code)
    names_in_order = [n for n, _ in board]
    rank = names_in_order.index(name) + 1 if name in names_in_order else None
    player = game.players.get(name)

    st.header("🏁 Game over!")
    if rank:
        st.subheader(f"You finished #{rank} with {player.score} points")

    st.divider()
    st.subheader("Final leaderboard")
    medals = ["🥇", "🥈", "🥉"]
    for r, (n, score) in enumerate(board, start=1):
        medal = medals[r - 1] if r <= 3 else f"{r}."
        st.write(f"{medal} **{n}** — {score}")

    st.divider()
    if st.button("Leave"):
        del st.session_state["player_name"]
        del st.session_state["player_code"]
        st.rerun()
