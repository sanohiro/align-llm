"""Billable duration helpers."""

import math


def round_to_minutes(seconds: int) -> int:
    """Round a whole-second duration to whole minutes.

    An exact half minute rounds away from zero, so ``30`` becomes ``1``
    and ``-30`` becomes ``-1``.
    """
    return round(seconds / 60)
