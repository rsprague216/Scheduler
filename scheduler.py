"""
Backwards-compatibility shim.

This module re-exports the public API that external code and the old
scheduler_app.py expected from a single 'scheduler' module.  New code
should import directly from the core/ and cli modules.
"""

from core.models import Worker, ShiftType, ShiftAssignment, SHIFT_TYPES, WORKERS_PER_SHIFT, Slot
from core.scheduler import Scheduler
from core.formatting import build_period, date_range
from core.export import export_schedule_csv, export_schedule_pdf
from cli import load_workers_from_csv, write_sample_csv, build_demo_workers

__all__ = [
    "Worker", "ShiftType", "ShiftAssignment", "SHIFT_TYPES", "WORKERS_PER_SHIFT", "Slot",
    "Scheduler",
    "build_period", "date_range",
    "export_schedule_csv", "export_schedule_pdf",
    "load_workers_from_csv", "write_sample_csv", "build_demo_workers",
]
