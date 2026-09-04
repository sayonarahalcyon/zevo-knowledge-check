"""Shared branding/styling helpers for every page of the app."""

import html

import streamlit as st

from game_engine.stats import get_games_created, get_last_error, get_debug_info

APP_NAME = "ZEVO Knowledge Check"
TAGLINE = "Live, group knowledge checks for ZEVO coworking sessions"

PRIMARY = "#00B37E"
PRIMARY_DARK = "#0B3D2E"


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
        }

        .zevo-banner {
            background: linear-gradient(135deg, #0B3D2E 0%, #00B37E 100%);
            color: #ffffff;
            padding: 1.6rem 2rem;
            border-radius: 16px;
            margin-bottom: 1.6rem;
            box-shadow: 0 8px 24px rgba(11, 61, 46, 0.25);
        }
        .zevo-banner h1 {
            color: #ffffff !important;
            margin: 0;
            font-size: 1.85rem;
            font-weight: 700;
            line-height: 1.2;
        }
        .zevo-banner p {
            margin: 0.35rem 0 0 0;
            opacity: 0.92;
            font-size: 0.95rem;
        }

        div.stButton > button {
            border-radius: 10px;
            font-weight: 600;
            transition: transform 0.05s ease-in-out;
        }
        div.stButton > button:hover {
            transform: translateY(-1px);
        }
        div.stButton > button[kind="primary"] {
            background-color: #00B37E;
            border-color: #00B37E;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #009c6b;
            border-color: #009c6b;
        }

        [data-testid="stMetricValue"] {
            color: #0B3D2E;
        }

        div[data-testid="stForm"] {
            border-radius: 14px;
        }

        .leaderboard-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.55rem 0.9rem;
            border-radius: 10px;
            margin-bottom: 0.4rem;
            background: #F4F7F6;
        }
        .leaderboard-row.leaderboard-top {
            background: linear-gradient(135deg, #FFF6E0, #FFEBB8);
            font-weight: 700;
        }
        .leaderboard-rank {
            width: 2.4rem;
            font-size: 1.1rem;
        }
        .leaderboard-name {
            flex: 1;
            padding: 0 0.75rem;
            word-break: break-word;
        }
        .leaderboard-score {
            font-weight: 700;
            color: #0B3D2E;
        }

        .name-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin: 0.3rem 0 0.9rem 0;
        }
        .name-chip {
            padding: 0.25rem 0.7rem;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
            word-break: break-word;
        }

        .category-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.3rem 0.9rem;
            border-radius: 999px;
            background: linear-gradient(135deg, #E4F7EE, #D2F0E3);
            color: #0B3D2E;
            font-weight: 700;
            font-size: 0.95rem;
            margin-bottom: 0.7rem;
        }

        .roulette-box {
            text-align: center;
            padding: 1.5rem;
            border-radius: 16px;
            background: linear-gradient(135deg, #0B3D2E 0%, #00B37E 100%);
            color: #ffffff;
            font-size: 1.7rem;
            font-weight: 700;
            margin: 0.6rem 0 1.1rem 0;
            box-shadow: 0 8px 24px rgba(11, 61, 46, 0.25);
        }

        .vote-tally-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.45rem 0.85rem;
            border-radius: 10px;
            margin-bottom: 0.35rem;
            background: #F4F7F6;
        }

        /* Kahoot-style colored answer tiles on the Play page. Buttons get a
           stable st-key-opt_<i> class (from key="opt_<i>") based on their
           on-screen position (A/B/C/D), independent of the question. */
        .st-key-opt_0 button,
        .st-key-opt_1 button,
        .st-key-opt_2 button,
        .st-key-opt_3 button {
            min-height: 3.4rem;
            padding: 0.75rem 1rem;
            text-align: left;
            line-height: 1.35;
            border-width: 0;
            font-size: 1.02rem;
        }
        .st-key-opt_0 button { background-color: #E21B3C; color: #ffffff; }
        .st-key-opt_0 button:hover { background-color: #c81733; color: #ffffff; }
        .st-key-opt_1 button { background-color: #1368CE; color: #ffffff; }
        .st-key-opt_1 button:hover { background-color: #0f57ab; color: #ffffff; }
        .st-key-opt_2 button { background-color: #D89E00; color: #17130a; }
        .st-key-opt_2 button:hover { background-color: #bb8900; color: #17130a; }
        .st-key-opt_3 button { background-color: #26890C; color: #ffffff; }
        .st-key-opt_3 button:hover { background-color: #1f6f0a; color: #ffffff; }

        /* Belt-and-suspenders: even without wrap=True, never hide answer text. */
        .st-key-opt_0 button p,
        .st-key-opt_1 button p,
        .st-key-opt_2 button p,
        .st-key-opt_3 button p {
            white-space: normal;
            overflow: visible;
            text-overflow: unset;
            word-break: break-word;
        }

        /* Games-hosted counter in the sidebar, styled to look like a big
           st.metric value even though it's really a link to the Admin page. */
        .st-key-games_hosted_link a {
            font-size: 2.2rem;
            font-weight: 700;
            color: #0B3D2E;
            text-decoration: none;
            line-height: 1.2;
        }
        .st-key-games_hosted_link a:hover {
            color: #00B37E;
            text-decoration: none;
        }
        .st-key-games_hosted_link [data-testid="stPageLink-Icon"] {
            display: none;
        }

        /* A little warmth behind the otherwise all-white page background. */
        [data-testid="stAppViewContainer"] > .main {
            background: radial-gradient(circle at 15% 0%, #EAF8F1 0%, #FFFFFF 45%);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page(title_suffix: str, icon: str) -> None:
    """Call first thing on every page: sets the tab title/icon and shared styling."""
    full_title = f"{APP_NAME} — {title_suffix}" if title_suffix else APP_NAME
    st.set_page_config(page_title=full_title, page_icon=icon, layout="centered")
    _inject_css()
    _render_sidebar_stats()


def _render_sidebar_stats() -> None:
    """Games-hosted counter under the page nav in the left sidebar.

    The count itself is a link (styled to look like a big metric value) to
    the Admin page, so clicking it jumps straight into the session/player/
    answer drill-down there.
    """
    with st.sidebar:
        st.divider()
        st.caption("🎮 Games hosted")
        with st.container(key="games_hosted_link"):
            st.page_link(
                "pages/3_Admin.py",
                label=str(get_games_created()),
            )
        st.caption("Since last deploy — click the number to view sessions")
        error = get_last_error()
        if error:
            st.caption(f"⚠️ {error}")
        with st.expander("Debug", expanded=False):
            st.json(get_debug_info())


def banner(icon: str, subtitle: str | None = None) -> None:
    st.markdown(
        f"""
        <div class="zevo-banner">
            <h1>{icon} {APP_NAME}</h1>
            <p>{html.escape(subtitle or TAGLINE)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_name_chips(names, tone: str = "neutral") -> None:
    """Render a wrapped row of small pill chips for a list of player names."""
    if not names:
        st.caption("No one.")
        return

    palette = {
        "correct": ("#E4F7EE", "#0B3D2E"),
        "incorrect": ("#FDEBEC", "#7A1F27"),
        "neutral": ("#F4F7F6", "#263a34"),
    }
    bg, fg = palette.get(tone, palette["neutral"])
    chips = "".join(
        f'<span class="name-chip" style="background:{bg};color:{fg};">{html.escape(str(n))}</span>'
        for n in names
    )
    st.markdown(f'<div class="name-chip-row">{chips}</div>', unsafe_allow_html=True)


def render_category_badge(icon: str, label: str) -> None:
    """Small pill showing the active category, e.g. on the game header."""
    st.markdown(
        f'<div class="category-badge">{icon} {html.escape(str(label))}</div>',
        unsafe_allow_html=True,
    )


def render_roulette_box(icon: str, label: str) -> None:
    """Big banner-style box used for the roulette spin/result."""
    st.markdown(
        f'<div class="roulette-box">🎰 {icon} {html.escape(str(label))}</div>',
        unsafe_allow_html=True,
    )


def render_vote_tally(rows) -> None:
    """rows: iterable of (key, label, icon, count), already sorted."""
    if not rows:
        st.caption("No votes yet.")
        return
    html_rows = []
    for _key, label, icon, count in rows:
        safe_label = html.escape(str(label))
        vote_word = "vote" if count == 1 else "votes"
        html_rows.append(
            '<div class="vote-tally-row">'
            f'<span>{icon} {safe_label}</span>'
            f'<span><strong>{count}</strong> {vote_word}</span>'
            "</div>"
        )
    st.markdown("".join(html_rows), unsafe_allow_html=True)


def render_leaderboard(board, limit: int | None = None) -> None:
    """Render a list of (name, score) tuples as a styled leaderboard."""
    rows = board[:limit] if limit else board
    if not rows:
        st.caption("No players yet.")
        return

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    html_rows = []
    for rank, (name, score) in enumerate(rows, start=1):
        badge = medals.get(rank, f"#{rank}")
        top_class = " leaderboard-top" if rank <= 3 else ""
        safe_name = html.escape(str(name))
        html_rows.append(
            f'<div class="leaderboard-row{top_class}">'
            f'<span class="leaderboard-rank">{badge}</span>'
            f'<span class="leaderboard-name">{safe_name}</span>'
            f'<span class="leaderboard-score">{score}</span>'
            f"</div>"
        )
    st.markdown(f'<div class="leaderboard">{"".join(html_rows)}</div>', unsafe_allow_html=True)
