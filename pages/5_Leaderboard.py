import datetime
from collections import defaultdict

import streamlit as st

from game_engine import history
from theme import page, banner

page("Leaderboard", "🏆")
banner("🏆", "Leaderboard — every solo play, by player")

plays = history.get_all_solo_plays()

if not plays:
    error = history.get_last_solo_error()
    if error:
        st.error(f"Solo history isn't loading: {error}")
    else:
        st.caption("No solo games played yet since the app's last deploy/reboot.")
    st.stop()


def _played_str(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%b %d, %Y %I:%M %p")


by_player = defaultdict(list)
for p in plays:
    by_player[p["name"]].append(p)

summary_rows = [
    {
        "Player": name,
        "Plays": len(rows),
        "Best score": max(r["score"] for r in rows),
        "Last played": _played_str(max(r["played_at"] for r in rows)),
    }
    for name, rows in by_player.items()
]
summary_rows.sort(key=lambda r: r["Best score"], reverse=True)

st.subheader(f"{len(by_player)} player(s) · {len(plays)} play(s) total")
st.dataframe(summary_rows, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Play-by-play history")

names = ["All players"] + sorted(by_player.keys(), key=str.lower)
choice = st.selectbox("Filter by player", options=names)
filtered = plays if choice == "All players" else by_player[choice]

for p in filtered:
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

st.divider()
st.caption(
    "This list resets on every redeploy/reboot, same as the multiplayer "
    "session history on the Admin page — it's solo plays since the app "
    "last restarted, not a permanent historical record."
)

error = history.get_last_solo_error()
if error:
    st.caption(f"⚠️ {error}")
