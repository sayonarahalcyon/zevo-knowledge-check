import streamlit as st
from streamlit_autorefresh import st_autorefresh

from game_engine.state import (
    get_store,
    LOBBY,
    QUESTION,
    REVEAL,
    FINISHED,
    HOST_PICK,
    VOTE,
    ROULETTE,
)
from game_engine.questions import load_category_bank
from game_engine.roulette import pick_target, flash_category
from theme import (
    page,
    banner,
    render_leaderboard,
    render_name_chips,
    render_category_badge,
    render_roulette_box,
    render_vote_tally,
)

page("Host", "🖥️")
banner("🖥️", "Host screen — create a game and run the room")

store = get_store()

MODE_LABELS = {
    HOST_PICK: "Pick it myself",
    VOTE: "Let players vote",
    ROULETTE: "Spin the roulette",
}
ROULETTE_TICKS = 16  # ~2s of spinning at 130ms/tick before it lands

# ---------------------------------------------------------------- no game yet
if "host_game_code" not in st.session_state:
    st.write("Start a new game to get a join code for the group.")
    try:
        bank = load_category_bank()
    except Exception as e:
        st.error(f"Couldn't load data/questions.json: {e}")
        st.stop()

    category_keys = list(bank.keys())

    st.subheader("How should the category get picked?")
    mode = st.radio(
        "Selection mode",
        options=[HOST_PICK, VOTE, ROULETTE],
        format_func=lambda m: MODE_LABELS[m],
        horizontal=True,
        label_visibility="collapsed",
        key="setup_mode",
    )

    st.divider()

    # ---- pick it myself ----
    if mode == HOST_PICK:
        choice_key = st.selectbox(
            "Category",
            options=category_keys,
            format_func=lambda k: f'{bank[k]["icon"]} {bank[k]["label"]} ({len(bank[k]["questions"])} questions)',
        )
        if st.button("Create new game", type="primary"):
            code = store.create_game(HOST_PICK, bank, category_key=choice_key)
            st.session_state["host_game_code"] = code
            st.rerun()

    # ---- let players vote ----
    elif mode == VOTE:
        st.caption(
            "Players each pick a category after they join. You lock it in once "
            "everyone's voted, then start the game."
        )
        cols = st.columns(len(category_keys))
        for col, key in zip(cols, category_keys):
            meta = bank[key]
            with col:
                st.write(f'{meta["icon"]} **{meta["label"]}**')
                st.caption(f'{len(meta["questions"])} questions')
        if st.button("Create new game", type="primary"):
            code = store.create_game(VOTE, bank)
            st.session_state["host_game_code"] = code
            st.rerun()

    # ---- roulette ----
    else:
        st.caption("Spin to land on a random category, then start the game with it.")
        spinning = st.session_state.get("roulette_spinning", False)
        result_key = st.session_state.get("roulette_result")

        if not spinning and not result_key:
            if st.button("🎰 Spin the wheel", type="primary"):
                st.session_state["roulette_spinning"] = True
                st.session_state["roulette_spin_id"] = st.session_state.get("roulette_spin_id", 0) + 1
                # Decide the outcome up front so the animation actually lands on it.
                st.session_state["roulette_target"] = pick_target(category_keys)
                st.rerun()

        if spinning:
            spin_id = st.session_state.get("roulette_spin_id", 0)
            target_key = st.session_state.get("roulette_target", category_keys[0])
            tick = st_autorefresh(interval=130, limit=ROULETTE_TICKS, key=f"roulette_ticker_{spin_id}")
            on_final_tick = tick >= ROULETTE_TICKS - 1
            flash_key = flash_category(category_keys, target_key, tick, ROULETTE_TICKS)
            flash_meta = bank[flash_key]
            render_roulette_box(flash_meta["icon"], flash_meta["label"])
            if on_final_tick:
                st.session_state["roulette_spinning"] = False
                st.session_state["roulette_result"] = target_key
                st.rerun()

        if result_key and not spinning:
            meta = bank[result_key]
            render_roulette_box(meta["icon"], meta["label"])
            st.success(f'Landed on: {meta["icon"]} {meta["label"]}')
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Create new game", type="primary", use_container_width=True):
                    code = store.create_game(ROULETTE, bank, category_key=result_key)
                    st.session_state["host_game_code"] = code
                    del st.session_state["roulette_result"]
                    st.rerun()
            with col_b:
                if st.button("Spin again", use_container_width=True):
                    del st.session_state["roulette_result"]
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

    if game.category_pending:
        st.subheader("🗳️ Category vote")
        st.caption("Players are voting on their Play screen. Lock it in once you're ready to start.")
        render_vote_tally(store.category_vote_counts(code))
        if st.button("Lock in category", type="primary"):
            store.lock_in_category(code)
            st.rerun()
    elif game.category:
        render_category_badge(game.category_icon, game.category_label)

    if st.button("Start game", type="primary", disabled=len(players) == 0 or not game.questions):
        store.start_game(code)
        st.rerun()

# ---------------------------------------------------------------- QUESTION
elif game.phase == QUESTION:
    st_autorefresh(interval=1000, key="host_question_refresh")

    total = len(game.questions)
    q = game.current_question

    with st.container(border=True):
        st.caption(f"Question {game.current_index + 1} of {total}")
        if game.category_label:
            render_category_badge(game.category_icon, game.category_label)
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
        if game.category_label:
            render_category_badge(game.category_icon, game.category_label)
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
    if game.category_label:
        render_category_badge(game.category_icon, game.category_label)
    board = store.leaderboard(code)
    render_leaderboard(board)

    if not board:
        st.caption("No players joined this game.")

    st.divider()
    if st.button("Start a new game"):
        del st.session_state["host_game_code"]
        st.rerun()
