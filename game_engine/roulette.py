"""Pure helper logic for the host-side category roulette animation.

Kept separate from the Streamlit page (and from the streamlit-autorefresh
component) so the spin/landing logic can be unit tested directly, without
needing a real browser round-trip.
"""

import random
from typing import List


def pick_target(category_keys: List[str]) -> str:
    """Decide the spin's outcome up front, so the animation can land on it."""
    return random.choice(category_keys)


def flash_category(category_keys: List[str], target_key: str, tick: int, total_ticks: int) -> str:
    """Which category to display on-screen for a given animation tick.

    Cycles through the categories tick by tick to look like a spin, then
    shows the actual target on the final tick so the wheel visually lands
    on the real outcome instead of a mismatched decoy.
    """
    if tick >= total_ticks - 1:
        return target_key
    return category_keys[tick % len(category_keys)]
