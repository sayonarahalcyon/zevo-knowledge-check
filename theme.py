"""Shared branding/styling helpers for every page of the app."""

import html

import streamlit as st

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
        </style>
        """,
        unsafe_allow_html=True,
    )


def page(title_suffix: str, icon: str) -> None:
    """Call first thing on every page: sets the tab title/icon and shared styling."""
    full_title = f"{APP_NAME} — {title_suffix}" if title_suffix else APP_NAME
    st.set_page_config(page_title=full_title, page_icon=icon, layout="centered")
    _inject_css()


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
