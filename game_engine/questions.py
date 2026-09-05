"""Loads the categorized quiz question bank from data/questions.json."""

import json
import random
from pathlib import Path
from typing import Dict, List

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.json"

MIXED_CATEGORY_KEY = "everything"
MIXED_CATEGORY_COUNT = 20


def _validate_questions(category_key: str, questions: List[dict]) -> None:
    if not questions:
        raise ValueError(f"Category '{category_key}' has no questions.")
    for i, q in enumerate(questions):
        if "question" not in q or "options" not in q or "correct_index" not in q:
            raise ValueError(f"Category '{category_key}' question {i} is missing a required field.")
        if not (0 <= q["correct_index"] < len(q["options"])):
            raise ValueError(f"Category '{category_key}' question {i} has a correct_index out of range.")


def load_category_bank() -> Dict[str, dict]:
    """Returns {category_key: {"label": str, "icon": str, "questions": [...]}}."""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    categories = raw.get("categories") if isinstance(raw, dict) else None
    if not categories:
        raise ValueError("data/questions.json must have a top-level \"categories\" list.")

    bank: Dict[str, dict] = {}
    for cat in categories:
        key = cat.get("key")
        if not key:
            raise ValueError("Every category needs a \"key\".")
        questions = cat.get("questions", [])
        _validate_questions(key, questions)
        bank[key] = {
            "label": cat.get("label", key.title()),
            "icon": cat.get("icon", "❓"),
            "questions": questions,
        }
    return bank


def add_mixed_category(bank: Dict[str, dict], count: int = MIXED_CATEGORY_COUNT) -> Dict[str, dict]:
    """Returns a new bank with an extra "everything" entry inserted first:
    a random, shuffled sample of `count` questions pooled from every real
    category in `bank` (fewer than `count` only if the bank itself has
    fewer questions total). A mixed play doesn't track which original
    category each question came from - that's fine, since answers are
    already scored/recorded per-question rather than per-category.

    Call this fresh on each page run (after load_category_bank()) so the
    mix is re-shuffled every time the category picker is shown; whatever
    got sampled during the run where "Start"/"Create new game" is clicked
    is what that play actually uses.
    """
    pool = [q for meta in bank.values() for q in meta["questions"]]
    sample_size = min(count, len(pool))
    mixed_questions = random.sample(pool, sample_size) if pool else []

    new_bank = {
        MIXED_CATEGORY_KEY: {
            "label": "Everything (random mix)",
            "icon": "🎲",
            "questions": mixed_questions,
        }
    }
    new_bank.update(bank)
    return new_bank
