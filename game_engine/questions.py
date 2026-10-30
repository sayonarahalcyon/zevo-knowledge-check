"""Loads the categorized quiz question bank from data/questions.json."""

import json
import random
import re
from pathlib import Path
from typing import Dict, List

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.json"

MIXED_CATEGORY_KEY = "everything"
MIXED_CATEGORY_COUNT = 20

# Optional grouping: a category in data/questions.json may carry a "group"
# name (and optionally a "group_icon"), e.g. every category added in one
# training update can share "group": "October 2026 Update". Grouped
# categories are shown under one parent choice in the pickers instead of
# each cluttering the top-level list, and the group also gets a "random
# mix of the whole group" entry (same idea as the Everything mix).
GROUP_KEY_PREFIX = "group:"
GROUP_DEFAULT_ICON = "📁"


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
            "group": cat.get("group") or None,
            "group_icon": cat.get("group_icon") or None,
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
    pool = [q for meta in bank.values() if not meta.get("group_mix") and not meta.get("group_all") for q in meta["questions"]]
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


def group_mix_key(group: str) -> str:
    return GROUP_KEY_PREFIX + re.sub(r"[^a-z0-9]+", "_", group.lower()).strip("_")


def group_all_key(group: str) -> str:
    return group_mix_key(group) + ":all"


def add_group_mixes(bank: Dict[str, dict], count: int = MIXED_CATEGORY_COUNT) -> Dict[str, dict]:
    """Returns a new bank with, for every group in `bank`, two extra
    entries: a "random mix of the whole group" (`count` questions sampled
    from all of that group's categories) and an "all questions" entry
    (every question in the group, shuffled). The group's own categories stay
    in the bank under their original keys. The extra entries are flagged
    "group_mix" / "group_all" so callers can tell them apart from real
    categories.

    Like add_mixed_category(), call this fresh on each page run so the
    sample is re-shuffled whenever the picker is shown.
    """
    members: Dict[str, List[str]] = {}
    for key, meta in bank.items():
        group = meta.get("group")
        if group and not meta.get("group_mix") and not meta.get("group_all"):
            members.setdefault(group, []).append(key)

    new_bank = dict(bank)
    for group, keys in members.items():
        pool = [q for k in keys for q in bank[k]["questions"]]
        icon = next((bank[k]["group_icon"] for k in keys if bank[k].get("group_icon")), GROUP_DEFAULT_ICON)
        new_bank[group_mix_key(group)] = {
            "label": f"{group} (random mix)",
            "icon": icon,
            "questions": random.sample(pool, min(count, len(pool))),
            "group": group,
            "group_mix": True,
        }
        # Every question in the group, shuffled (not just a sample).
        new_bank[group_all_key(group)] = {
            "label": f"{group} (all questions)",
            "icon": icon,
            "questions": random.sample(pool, len(pool)),
            "group": group,
            "group_all": True,
        }
    return new_bank


def top_level_bank(bank: Dict[str, dict], count: int = MIXED_CATEGORY_COUNT) -> Dict[str, dict]:
    """The categories a group-unaware chooser (player vote, roulette)
    should offer: every ungrouped category, plus ONE entry per group that
    plays a random mix of that whole group. A group's individual
    categories are left out so they don't crowd the vote / the wheel; the
    host's "pick it myself" list and Solo are where those are chosen.
    """
    with_mixes = add_group_mixes(bank, count)
    return {k: m for k, m in with_mixes.items() if not m.get("group") or m.get("group_mix")}
