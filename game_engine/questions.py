"""Loads the quiz question bank from data/questions.json."""

import json
from pathlib import Path
from typing import List

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.json"


def load_questions() -> List[dict]:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        questions = json.load(f)

    for i, q in enumerate(questions):
        if "question" not in q or "options" not in q or "correct_index" not in q:
            raise ValueError(f"Question {i} in questions.json is missing a required field.")
        if not (0 <= q["correct_index"] < len(q["options"])):
            raise ValueError(f"Question {i} has a correct_index out of range.")
    return questions
