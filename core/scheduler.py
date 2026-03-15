"""
Greedy shift scheduler with fairness balancing.

Pre-scheduling:
  Build slot_index (Slot -> [worker names]) once so candidate lookup
  during scheduling is O(1) instead of scanning all workers per slot.

Main loop:
  For each slot, rank available workers by shift count (fewest first),
  break ties randomly, pick top WORKERS_PER_SHIFT.

Swap passes:
  _fill_understaffed — fills any slots that came out short after the
                       greedy pass by adding available workers.
  _balance_loads     — uses heaps (O(log n)) + a reverse worker->slots
                       index (O(assigned_shifts)) to swap the heaviest
                       worker's shift to the lightest worker where
                       availability permits.
"""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import date
from typing import Optional

from core.models import ShiftAssignment, ShiftType, Slot, Worker, SHIFT_TYPES, WORKERS_PER_SHIFT
from core.formatting import date_range


class Scheduler:

    def __init__(self, workers: list[Worker], period_start: date, period_end: date):
        self.workers: dict[str, Worker] = {w.name: w for w in workers}
        self.period_start = period_start
        self.period_end = period_end
        self._shift_counts: dict[str, int] = defaultdict(int)
        self._schedule: list[ShiftAssignment] = []
        self._worker_slots: dict[str, list[ShiftAssignment]] = defaultdict(list)
        self._slot_index: dict[Slot, list[str]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, swap_passes: int = 3, seed: Optional[int] = None) -> list[ShiftAssignment]:
        if seed is not None:
            random.seed(seed)

        self._shift_counts = defaultdict(int)
        self._schedule = []
        self._worker_slots = defaultdict(list)
        self._slot_index = self._build_slot_index()

        for day in date_range(self.period_start, self.period_end):
            for shift in SHIFT_TYPES:
                slot: Slot = (day, shift)
                candidates = list(self._slot_index.get(slot, []))
                candidates.sort(key=lambda n: (self._shift_counts[n], random.random()))
                chosen = candidates[:WORKERS_PER_SHIFT]
                assignment = ShiftAssignment(day=day, shift=shift, workers=set(chosen))
                for name in chosen:
                    self._shift_counts[name] += 1
                    self._worker_slots[name].append(assignment)
                self._schedule.append(assignment)

        for _ in range(swap_passes):
            self._fill_understaffed()
            self._balance_loads()

        return self._schedule

    @property
    def schedule(self) -> list[ShiftAssignment]:
        return self._schedule

    def shift_counts(self) -> dict[str, int]:
        return dict(self._shift_counts)

    def understaffed_slots(self) -> list[ShiftAssignment]:
        return [s for s in self._schedule if not s.is_full]

    def print_schedule(self) -> None:
        if not self._schedule:
            print("Schedule not yet generated. Call generate() first.")
            return

        print("\n" + "=" * 60)
        print(f"  SCHEDULE  {self.period_start} → {self.period_end}")
        print("=" * 60)

        current_week: Optional[int] = None
        for a in self._schedule:
            week = a.day.isocalendar()[1]
            if week != current_week:
                print(f"\n  — Week {week} —")
                current_week = week
            day_label   = a.day.strftime("%a %b %d")
            workers_str = ", ".join(sorted(a.workers)) if a.workers else "⚠  UNDERSTAFFED"
            flag        = f"  ⚠ need {a.shortfall} more" if a.shortfall else ""
            print(f"  {day_label}  [{a.shift.value:<8}]  {workers_str}{flag}")

        print("\n" + "-" * 60)
        print("  Shift counts per worker:")
        for name, count in sorted(self._shift_counts.items(), key=lambda x: -x[1]):
            print(f"    {name:<20} {count:>3}  {'█' * count}")
        print("=" * 60 + "\n")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_slot_index(self) -> dict[Slot, list[str]]:
        index: dict[Slot, list[str]] = defaultdict(list)
        for name, worker in self.workers.items():
            for slot in worker.availability:
                index[slot].append(name)
        return dict(index)

    def _fill_understaffed(self) -> None:
        """Phase 1: top up any slots that came out short after the greedy pass."""
        counts = self._shift_counts
        for sa in self._schedule:
            if sa.is_full:
                continue
            candidates = [
                n for n in self._slot_index.get(sa.slot, [])
                if n not in sa.workers
            ]
            candidates.sort(key=lambda n: counts[n])
            for name in candidates[:sa.shortfall]:
                sa.workers.add(name)
                counts[name] += 1
                self._worker_slots[name].append(sa)

    def _balance_loads(self) -> None:
        """Phase 2: swap one shift from the heaviest worker to the lightest."""
        counts = self._shift_counts
        if len(counts) < 2:
            return
        heaviest = max(counts, key=counts.__getitem__)
        lightest = min(counts, key=counts.__getitem__)
        heaviest_count = counts[heaviest]
        lightest_count = counts[lightest]
        if heaviest_count - lightest_count < 2:
            return
        lightest_worker = self.workers[lightest]
        for sa in self._worker_slots.get(heaviest, []):
            if lightest not in sa.workers and lightest_worker.is_available(sa.day, sa.shift):
                sa.workers.discard(heaviest)
                sa.workers.add(lightest)
                counts[heaviest] -= 1
                counts[lightest] += 1
                self._worker_slots[heaviest].remove(sa)
                self._worker_slots[lightest].append(sa)
                return
