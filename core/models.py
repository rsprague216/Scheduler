"""
Core data models for the shift scheduler.

Defines the primitive types shared across the scheduling engine,
exporters, and GUI: ShiftType, Worker, and ShiftAssignment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


# ---------------------------------------------------------------------------
# Constants / types
# ---------------------------------------------------------------------------

class ShiftType(Enum):
    MORNING = "Morning"
    CLOSING = "Closing"


SHIFT_TYPES: list[ShiftType] = [ShiftType.MORNING, ShiftType.CLOSING]
WORKERS_PER_SHIFT: int = 2
Slot = tuple[date, ShiftType]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Worker:
    name: str
    # Flat set of (date, ShiftType) pairs — O(1) membership, no False entries.
    availability: set[Slot] = field(default_factory=set)

    def is_available(self, day: date, shift: ShiftType) -> bool:
        return (day, shift) in self.availability

    def add_availability(self, day: date, shifts: list[ShiftType]) -> None:
        for s in shifts:
            self.availability.add((day, s))

    def remove_availability(self, day: date, shift: ShiftType) -> None:
        self.availability.discard((day, shift))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "availability": [
                [slot[0].isoformat(), slot[1].name]
                for slot in sorted(self.availability, key=lambda s: (s[0], s[1].name))
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Worker":
        worker = cls(name=data["name"])
        for date_str, shift_name in data.get("availability", []):
            worker.availability.add((date.fromisoformat(date_str), ShiftType[shift_name]))
        return worker


@dataclass
class ShiftAssignment:
    day: date
    shift: ShiftType
    workers: set[str] = field(default_factory=set)

    @property
    def is_full(self) -> bool:
        return len(self.workers) >= WORKERS_PER_SHIFT

    @property
    def shortfall(self) -> int:
        return max(0, WORKERS_PER_SHIFT - len(self.workers))

    @property
    def slot(self) -> Slot:
        return (self.day, self.shift)
