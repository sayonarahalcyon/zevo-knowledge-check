"""Loads the categorized quiz question bank from data/questions.json."""

import json
from pathlib import Path
from typing import Dict, List

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.json"


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
