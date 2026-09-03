"""
Shared, in-memory game engine for the live quiz.

Design note: this relies on Streamlit running as a SINGLE server process
(the default on Streamlit Community Cloud for one app). Every visitor's
browser tab is a separate Streamlit "session", but they all share the same
Python process, so a plain Python object cached with st.cache_resource is
shared across every player and the host. That's what makes a live,
Kahoot-style shared game possible without a separate database.

If this app is ever deployed across multiple server instances (e.g. behind
a load balancer with more than one replica), this in-memory approach will
NOT work, because different players could land on different processes that
don't share state. For a single small-group session this is not a concern.
"""

import random
import string
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import streamlit as st

from game_engine import history, stats

LOBBY = "lobby"
QUESTION = "question"
REVEAL = "reveal"
FINISHED = "finished"

HOST_PICK = "host"
VOTE = "vote"
ROULETTE = "roulette"

MIN_POINTS = 500
MAX_POINTS = 1000
DEFAULT_DURATION = 20  # seconds, used if a question doesn't specify one


@dataclass
class Answer:
    choice_index: int
    correct: bool
    points: int
    seconds_taken: float


@dataclass
class Player:
    name: str
    joined_at: float = field(default_factory=time.time)
    answers: Dict[int, Answer] = field(default_factory=dict)

    @property
    def score(self) -> int:
        return sum(a.points for a in self.answers.values())


@dataclass
class Game:
    code: str
    questions: List[dict] = field(default_factory=list)
    phase: str = LOBBY
    current_index: int = -1
    question_started_at: Optional[float] = None
    players: Dict[str, Player] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    # ---- category selection ----
    selection_mode: str = HOST_PICK  # "host" | "vote" | "roulette"
    category: Optional[str] = None
    category_label: Optional[str] = None
    category_icon: Optional[str] = None
    pending_bank: Dict[str, dict] = field(default_factory=dict)  # only set while a vote is open
    category_votes: Dict[str, str] = field(default_factory=dict)  # player name -> category key

    @property
    def current_question(self) -> Optional[dict]:
        if 0 <= self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    @property
    def question_duration(self) -> int:
        q = self.current_question
        if not q:
            return DEFAULT_DURATION
        return int(q.get("duration", DEFAULT_DURATION))

    @property
    def seconds_elapsed(self) -> float:
        if self.question_started_at is None:
            return 0.0
        return time.time() - self.question_started_at

    @property
    def seconds_remaining(self) -> float:
        return max(0.0, self.question_duration - self.seconds_elapsed)

    @property
    def is_time_up(self) -> bool:
        return self.seconds_elapsed >= self.question_duration

    @property
    def category_pending(self) -> bool:
        return self.selection_mode == VOTE and self.category is None


class GameStore:
    """Thread-safe holder for all active games (keyed by join code)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._games: Dict[str, Game] = {}

    def _new_code(self) -> str:
        alphabet = string.ascii_uppercase.replace("O", "").replace("I", "")
        while True:
            code = "".join(random.choices(alphabet, k=4))
            if code not in self._games:
                return code

    def create_game(
        self,
        mode: str,
        bank: Dict[str, dict],
        category_key: Optional[str] = None,
    ) -> str:
        """Start a new game.

        mode "host" or "roulette": category_key must already be chosen (by the
        host directly, or by a roulette spin resolved on the host's screen) —
        the game starts with that category's questions loaded immediately.

        mode "vote": category_key is ignored; the game starts with no
        questions yet. Players vote for a category while joining/in the
        lobby, and the host calls lock_in_category() once voting closes.
        """
        with self._lock:
            code = self._new_code()
            game = Game(code=code, selection_mode=mode)

            if mode == VOTE:
                game.pending_bank = bank
            else:
                if category_key not in bank:
                    raise ValueError(f"Unknown category '{category_key}'.")
                meta = bank[category_key]
                game.questions = meta["questions"]
                game.category = category_key
                game.category_label = meta["label"]
                game.category_icon = meta["icon"]

            self._games[code] = game
            stats.increment_games_created()
            return code

    def get(self, code: str) -> Optional[Game]:
        with self._lock:
            return self._games.get((code or "").strip().upper())

    def join(self, code: str, name: str) -> tuple[bool, str]:
        name = (name or "").strip()
        if not name:
            return False, "Enter a name."
        with self._lock:
            game = self._games.get((code or "").strip().upper())
            if not game:
                return False, "That game code doesn't exist."
            if game.phase != LOBBY:
                return False, "This game has already started."
            existing = {n.lower() for n in game.players}
            if name.lower() in existing:
                return False, "That name is already taken in this game."
            game.players[name] = Player(name=name)
            return True, "Joined!"

    def pending_categories(self, code: str) -> List[Tuple[str, str, str]]:
        """(key, label, icon) for each category still open for voting."""
        game = self._games.get(code)
        if not game or not game.pending_bank:
            return []
        return [(k, meta["label"], meta["icon"]) for k, meta in game.pending_bank.items()]

    def vote_category(self, code: str, name: str, category_key: str) -> None:
        with self._lock:
            game = self._games.get(code)
            if not game or game.selection_mode != VOTE or game.category is not None:
                return
            if name not in game.players or category_key not in game.pending_bank:
                return
            game.category_votes[name] = category_key

    def category_vote_counts(self, code: str) -> List[Tuple[str, str, str, int]]:
        """(key, label, icon, vote_count) sorted by vote_count desc."""
        game = self._games.get(code)
        if not game or not game.pending_bank:
            return []
        tally = Counter(game.category_votes.values())
        rows = [
            (k, meta["label"], meta["icon"], tally.get(k, 0))
            for k, meta in game.pending_bank.items()
        ]
        return sorted(rows, key=lambda r: r[3], reverse=True)

    def lock_in_category(self, code: str) -> None:
        """End voting: pick the category with the most votes (ties broken randomly)."""
        with self._lock:
            game = self._games.get(code)
            if not game or game.selection_mode != VOTE or game.category is not None:
                return
            if not game.pending_bank:
                return

            if game.category_votes:
                tally = Counter(game.category_votes.values())
                top_count = max(tally.values())
                winners = [k for k, c in tally.items() if c == top_count]
            else:
                winners = list(game.pending_bank.keys())

            chosen = random.choice(winners)
            meta = game.pending_bank[chosen]
            game.category = chosen
            game.category_label = meta["label"]
            game.category_icon = meta["icon"]
            game.questions = meta["questions"]
            game.pending_bank = {}

    def start_game(self, code: str) -> None:
        with self._lock:
            game = self._games.get(code)
            if not game or not game.questions:
                return
            game.phase = QUESTION
            game.current_index = 0
            game.question_started_at = time.time()

    def submit_answer(self, code: str, name: str, choice_index: int) -> None:
        with self._lock:
            game = self._games.get(code)
            if not game or game.phase != QUESTION:
                return
            player = game.players.get(name)
            if not player:
                return
            if game.current_index in player.answers:
                return  # already answered this question
            if game.is_time_up:
                return  # too late

            q = game.current_question
            elapsed = game.seconds_elapsed
            duration = game.question_duration
            correct = choice_index == q["correct_index"]
            if correct:
                fraction_left = max(0.0, (duration - elapsed) / duration)
                points = int(MIN_POINTS + (MAX_POINTS - MIN_POINTS) * fraction_left)
            else:
                points = 0
            player.answers[game.current_index] = Answer(
                choice_index=choice_index,
                correct=correct,
                points=points,
                seconds_taken=round(elapsed, 1),
            )

    def reveal(self, code: str) -> None:
        with self._lock:
            game = self._games.get(code)
            if game and game.phase == QUESTION:
                game.phase = REVEAL

    def next_question(self, code: str) -> None:
        with self._lock:
            game = self._games.get(code)
            if not game or game.phase != REVEAL:
                return
            if game.current_index + 1 >= len(game.questions):
                game.phase = FINISHED
                history.record_game_result(
                    code,
                    game.category_label,
                    [{"name": p.name, "score": p.score} for p in game.players.values()],
                )
            else:
                game.current_index += 1
                game.phase = QUESTION
                game.question_started_at = time.time()

    def leaderboard(self, code: str) -> List[tuple[str, int]]:
        game = self._games.get(code)
        if not game:
            return []
        rows = [(p.name, p.score) for p in game.players.values()]
        return sorted(rows, key=lambda r: r[1], reverse=True)


@st.cache_resource
def get_store() -> GameStore:
    """One GameStore instance, shared by every session on this server."""
    return GameStore()
