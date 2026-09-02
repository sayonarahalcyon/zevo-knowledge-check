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
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import streamlit as st

LOBBY = "lobby"
QUESTION = "question"
REVEAL = "reveal"
FINISHED = "finished"

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
    questions: List[dict]
    phase: str = LOBBY
    current_index: int = -1
    question_started_at: Optional[float] = None
    players: Dict[str, Player] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

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

    def create_game(self, questions: List[dict]) -> str:
        with self._lock:
            code = self._new_code()
            self._games[code] = Game(code=code, questions=questions)
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
