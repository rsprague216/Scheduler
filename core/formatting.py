"""
Shared formatting utilities used by the scheduler, exporters, and GUI.

Centralises date iteration, period calculation, and display helpers
so they are never duplicated across modules.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from core.models import ShiftAssignment


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def date_range(start: date, end: date) -> list[date]:
    """Return every date from *start* to *end* inclusive."""
    days, d = [], start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


def build_period(start: date, length: str = "week") -> tuple[date, date]:
    """
    Return (start, end) for 'week', '2week', or 'month'.
    Uses calendar.monthrange to handle variable month lengths correctly.
    """
    length = length.lower().replace("-", "").replace(" ", "")
    if length == "week":
        return start, start + timedelta(days=6)
    elif length in ("2week", "twoweek", "biweek"):
        return start, start + timedelta(days=13)
    elif length == "month":
        days_in_month = calendar.monthrange(start.year, start.month)[1]
        return start, start + timedelta(days=days_in_month - 1)
    else:
        raise ValueError(f"Unknown period '{length}'. Use 'week', '2week', or 'month'.")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def sorted_workers(assignment: ShiftAssignment) -> list[str]:
    """Return the workers assigned to a shift, sorted alphabetically."""
    return sorted(assignment.workers)


def understaffed_text(assignment: ShiftAssignment) -> str:
    """Human-readable status string for a shift assignment."""
    return f"Need {assignment.shortfall} more" if assignment.shortfall else "✓ OK"
