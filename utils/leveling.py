"""
XP / level math, using a standard increasing-curve formula (similar to
what bots like Mee6 use): each level requires progressively more XP
than the last, so leveling up gets slower as you go.
"""


def xp_for_next_level(level: int) -> int:
    """XP required to go from `level` to `level + 1`."""
    return 5 * (level ** 2) + 50 * level + 100


def total_xp_for_level(level: int) -> int:
    """Cumulative XP required to REACH `level` from 0."""
    return sum(xp_for_next_level(l) for l in range(level))


def level_from_total_xp(total_xp: int):
    """Returns (level, xp_into_current_level)."""
    level = 0
    remaining = total_xp
    while remaining >= xp_for_next_level(level):
        remaining -= xp_for_next_level(level)
        level += 1
    return level, remaining


def progress_bar(current: int, needed: int, length: int = 12) -> str:
    filled = int(length * current / needed) if needed else length
    filled = max(0, min(length, filled))
    return "█" * filled + "░" * (length - filled)
