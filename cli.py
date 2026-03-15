"""
Command-line interface for the shift scheduler.

Usage examples:

  # Run with demo data, print to console
  python cli.py

  # Generate a blank availability template
  python cli.py --sample template.csv --start 2026-04-01 --period week

  # Schedule from CSV, export to PDF and CSV
  python cli.py --csv availability.csv --start 2026-04-01 --period week \\
      --out-pdf schedule.pdf --out-csv schedule.csv
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from core.models import Worker, ShiftType
from core.formatting import build_period, date_range
from core.scheduler import Scheduler
from core.export import export_schedule_csv, export_schedule_pdf


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

# Expected format — one row per worker per available day:
#
#   name,date,morning,closing
#   Alice,2026-04-01,yes,no
#   Alice,2026-04-02,yes,yes
#   Bob,2026-04-01,no,yes
#
# date    — YYYY-MM-DD
# morning — yes/no  (also accepts: y, 1, true, x — case-insensitive)
# closing — yes/no  (same)

_TRUTHY = {"yes", "y", "1", "true", "x"}


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in _TRUTHY


def load_workers_from_csv(path: str | Path) -> list[Worker]:
    """
    Load worker availability from a CSV file.
    Returns a list of Worker objects ready to pass into Scheduler.
    Raises ValueError for missing columns or unparseable dates.
    """
    path = Path(path)
    workers: dict[str, Worker] = {}

    with path.open(newline="", encoding="utf-8-sig") as f:   # utf-8-sig strips Excel BOM
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError("CSV file appears to be empty.")

        actual   = {col.strip().lower() for col in reader.fieldnames}
        required = {"name", "date", "morning", "closing"}
        missing  = required - actual
        if missing:
            raise ValueError(f"CSV missing required column(s): {', '.join(sorted(missing))}")

        for line_num, row in enumerate(reader, start=2):
            row  = {k.strip().lower(): v.strip() for k, v in row.items()}
            name = row["name"].strip()
            if not name:
                continue

            raw_date = row["date"].strip()
            try:
                day = date.fromisoformat(raw_date)
            except ValueError:
                raise ValueError(
                    f"Line {line_num}: cannot parse date '{raw_date}'. Use YYYY-MM-DD."
                )

            shifts = []
            if _parse_bool(row["morning"]):
                shifts.append(ShiftType.MORNING)
            if _parse_bool(row["closing"]):
                shifts.append(ShiftType.CLOSING)

            if name not in workers:
                workers[name] = Worker(name=name)
            workers[name].add_availability(day, shifts)

    return list(workers.values())


def write_sample_csv(path: str | Path, period_start: date, period_end: date) -> None:
    """
    Write a blank availability template CSV for the given period.
    Managers can share this with workers to fill in their availability.
    """
    path = Path(path)
    days = date_range(period_start, period_end)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "date", "morning", "closing"])
        for name in ["Worker1", "Worker2"]:
            for day in days:
                writer.writerow([name, day.isoformat(), "no", "no"])

    print(f"Template written to: {path}")


# ---------------------------------------------------------------------------
# Demo data builder
# ---------------------------------------------------------------------------

def build_demo_workers(period_start: date, period_end: date) -> list[Worker]:
    workers_data = [
        ("Alice",  {0, 1, 2, 3, 4},       True),
        ("Bob",    {1, 2, 3, 5, 6},       False),
        ("Carol",  {0, 2, 4, 5, 6},       True),
        ("David",  {0, 1, 3, 4, 6},       False),
        ("Eva",    {2, 3, 4, 5, 6},       True),
        ("Frank",  {0, 1, 2, 5, 6},       False),
        ("Grace",  {0, 1, 2, 3, 4, 5, 6}, True),
        ("Henry",  {0, 4, 5, 6},          False),
    ]
    days = date_range(period_start, period_end)

    workers = []
    for name, weekdays, prefers_morning in workers_data:
        w = Worker(name=name)
        for day in days:
            if day.weekday() not in weekdays:
                continue
            shifts = []
            if prefers_morning:
                shifts.append(ShiftType.MORNING)
                if random.random() < 0.5:
                    shifts.append(ShiftType.CLOSING)
            else:
                shifts.append(ShiftType.CLOSING)
                if random.random() < 0.5:
                    shifts.append(ShiftType.MORNING)
            w.add_availability(day, shifts)
        workers.append(w)
    return workers


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Worker Shift Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with demo data, print to console
  python cli.py

  # Generate a blank availability template
  python cli.py --sample template.csv --start 2026-04-01 --period week

  # Schedule from CSV, export to both PDF and CSV
  python cli.py --csv availability.csv --start 2026-04-01 --period week \\
      --out-pdf schedule.pdf --out-csv schedule.csv
        """,
    )
    parser.add_argument("--csv",     metavar="FILE",
                        help="Worker availability CSV file")
    parser.add_argument("--sample",  metavar="FILE",
                        help="Write a blank template CSV and exit")
    parser.add_argument("--start",   metavar="DATE",
                        help="Period start date YYYY-MM-DD (default: today)")
    parser.add_argument("--period",  metavar="LENGTH", default="2week",
                        help="week | 2week | month  (default: 2week)")
    parser.add_argument("--seed",    metavar="INT", type=int, default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--swaps",   metavar="INT", type=int, default=5,
                        help="Fairness swap passes (default: 5)")
    parser.add_argument("--out-csv", metavar="FILE",
                        help="Export generated schedule to a CSV file")
    parser.add_argument("--out-pdf", metavar="FILE",
                        help="Export generated schedule to a PDF file")
    args = parser.parse_args()

    if args.start:
        try:
            start = date.fromisoformat(args.start)
        except ValueError:
            print(f"Error: --start '{args.start}' is not a valid YYYY-MM-DD date.",
                  file=sys.stderr)
            sys.exit(1)
    else:
        start = date.today()

    period_start, period_end = build_period(start, args.period)

    if args.sample:
        write_sample_csv(args.sample, period_start, period_end)
        print(f"Fill in 'yes'/'no' for morning/closing per worker per day, then run:")
        print(f"  python cli.py --csv {args.sample} --start {period_start} --period {args.period}")
        sys.exit(0)

    if args.csv:
        print(f"\nLoading worker availability from: {args.csv}")
        try:
            workers = load_workers_from_csv(args.csv)
        except (ValueError, FileNotFoundError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Loaded {len(workers)} worker(s): {', '.join(w.name for w in workers)}")
    else:
        print("\n(No --csv supplied — running with demo workers.)")
        random.seed(args.seed)
        workers = build_demo_workers(period_start, period_end)

    print(f"Building a {args.period} schedule: {period_start} → {period_end}\n")

    scheduler = Scheduler(workers, period_start, period_end)
    scheduler.generate(swap_passes=args.swaps, seed=args.seed)
    scheduler.print_schedule()

    understaffed = scheduler.understaffed_slots()
    if understaffed:
        print(f"⚠  {len(understaffed)} slot(s) could not be fully staffed:")
        for s in understaffed:
            assigned = sorted(s.workers) if s.workers else ["nobody"]
            print(f"   {s.day}  {s.shift.value}  — assigned: {assigned}  need {s.shortfall} more")
    else:
        print("✓  All shifts fully staffed.")
    print()

    if args.out_csv:
        export_schedule_csv(scheduler, args.out_csv)
    if args.out_pdf:
        export_schedule_pdf(scheduler, args.out_pdf)
