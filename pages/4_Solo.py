"""Solo practice mode: one player, no host, no join code.

Reuses the same question bank as the group game, but untimed: no countdown,
no auto-reveal, flat points (game_engine.state's POINTS_PER_CORRECT) for
every correct answer. All state lives in this browser tab's
st.session_state instead of the shared GameStore, since there's no one else
to sync with. Each finished play is recorded via history.record_solo_result()
so it shows up on the Leaderboard page.
"""

import time

import streamlit as st

from game_engine import history
from game_engine.questions import load_category_bank
from game_engine.state import POINTS_PER_CORRECT
from theme import page, banner, render_category_badge

page("Solo", "🧑‍🎓")
banner("🧑‍🎓", "Solo practice — play a category on your own, at your own pace")

stage = st.session_state.get("solo_stage", "setup")

# ------------------------------------------------------------------- SETUP
if stage == "setup":
    st.write(
        "Same questions as the group game, minus the host and the clock — "
        "just you and a category, at your own pace."
    )
    try:
        bank = load_category_bank()
    except Exception as e:
        st.error(f"Couldn't load data/questions.json: {e}")
        st.stop()

    category_keys = list(bank.keys())

    name = st.text_input("Your name", value=st.session_state.get("solo_name", ""))
    choice_key = st.selectbox(
        "Category",
        options=category_keys,
        format_func=lambda k: f'{bank[k]["icon"]} {bank[k]["label"]} ({len(bank[k]["questions"])} questions)',
    )

    if st.button("Start", type="primary", disabled=not name.strip()):
        st.session_state["solo_name"] = name.strip()
        st.session_state["solo_category_label"] = bank[choice_key]["label"]
        st.session_state["solo_category_icon"] = bank[choice_key]["icon"]
        st.session_state["solo_questions"] = bank[choice_key]["questions"]
        st.session_state["solo_index"] = 0
        st.session_state["solo_answers"] = []
        st.session_state["solo_started_at"] = time.time()
        st.session_state["solo_stage"] = "question"
        st.session_state.pop("solo_recorded", None)
        st.rerun()

    st.divider()
    st.page_link("pages/5_Leaderboard.py", label="See everyone's solo scores", icon="🏆")
    st.stop()

questions = st.session_state["solo_questions"]
index = st.session_state["solo_index"]
total = len(questions)
q = questions[index]
icon = st.session_state["solo_category_icon"]
label = st.session_state["solo_category_label"]

# ----------------------------------------------------------------- QUESTION
if stage == "question":
    with st.container(border=True):
        st.caption(f"Question {index + 1} of {total}")
        render_category_badge(icon, label)
        st.header(q["question"])

        st.caption("Take your time — no clock here.")
        shapes = ["▲", "◆", "●", "■"]
        cols = st.columns(2)
        for i, opt in enumerate(q["options"]):
            col = cols[i % 2]
            btn_label = f"{shapes[i]} {chr(65 + i)}. {opt}"
            if col.button(btn_label, key=f"opt_{i}", use_container_width=True, wrap=True):
                correct = i == q["correct_index"]
                points = POINTS_PER_CORRECT if correct else 0
                st.session_state["solo_answers"].append(
                    {
                        "choice_index": i,
                        "correct": correct,
                        "points": points,
                        "seconds_taken": round(time.time() - st.session_state["solo_started_at"], 1),
                    }
                )
                st.session_state["solo_stage"] = "reveal"
                st.rerun()

# ------------------------------------------------------------------- REVEAL
elif stage == "reveal":
    result = st.session_state["solo_answers"][index]
    correct_letter = chr(65 + q["correct_index"])
    correct_text = q["options"][q["correct_index"]]

    with st.container(border=True):
        st.caption(f"Question {index + 1} of {total}")
        render_category_badge(icon, label)
        st.header(q["question"])

        if result["correct"]:
            st.success(f"✅ Correct! +{result['points']} points")
        else:
            st.error(f"❌ Not quite. Correct answer: {correct_letter}. {correct_text}")

        running_score = sum(a["points"] for a in st.session_state["solo_answers"])
        st.metric("Your score so far", running_score)

    is_last = index + 1 >= total
    if st.button("See final score" if is_last else "Next question", type="primary"):
        if is_last:
            st.session_state["solo_stage"] = "finished"
        else:
            st.session_state["solo_index"] += 1
            st.session_state["solo_started_at"] = time.time()
            st.session_state["solo_stage"] = "question"
        st.rerun()

# ----------------------------------------------------------------- FINISHED
elif stage == "finished":
    answers = st.session_state["solo_answers"]
    score = sum(a["points"] for a in answers)
    correct_count = sum(1 for a in answers if a["correct"])

    st.header("🏁 Nice work!")
    render_category_badge(icon, label)
    st.subheader(f"Final score: {score} points ({correct_count}/{total} correct)")

    rows = [
        {
            "Question": qq["question"],
            "Your answer": (qq["options"][a["choice_index"]] if a["choice_index"] is not None else "(no answer)"),
            "Correct answer": qq["options"][qq["correct_index"]],
            "Result": "✅ Correct" if a["correct"] else "❌ Wrong",
            "Points": a["points"],
        }
        for qq, a in zip(questions, answers)
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if not st.session_state.get("solo_recorded"):
        history.record_solo_result(
            st.session_state["solo_name"],
            label,
            score,
            [
                {
                    "question": qq["question"],
                    "your_answer": (qq["options"][a["choice_index"]] if a["choice_index"] is not None else None),
                    "correct_answer": qq["options"][qq["correct_index"]],
                    "correct": a["correct"],
                    "points": a["points"],
                }
                for qq, a in zip(questions, answers)
            ],
        )
        st.session_state["solo_recorded"] = True

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Play again", use_container_width=True):
            for k in (
                "solo_stage",
                "solo_category_label",
                "solo_category_icon",
                "solo_questions",
                "solo_index",
                "solo_answers",
                "solo_started_at",
                "solo_recorded",
            ):
                st.session_state.pop(k, None)
            st.rerun()
    with col2:
        st.page_link("pages/5_Leaderboard.py", label="See the leaderboard", icon="🏆", use_container_width=True)
