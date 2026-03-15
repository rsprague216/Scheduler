# Shift Scheduler

A desktop app for generating fair shift schedules based on worker availability. Built with Python and tkinter — no external dependencies beyond the standard library (PDF export optionally requires `reportlab`).

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue) ![tkinter](https://img.shields.io/badge/GUI-tkinter-lightgrey)

---

## Features

- **GUI app** — add workers, configure the period, generate and view schedules visually
- **Calendar & list views** — Results tab toggles between a week-grid calendar and a flat list; understaffed cells highlighted in red
- **Worker persistence** — workers are auto-saved to `workers.json` and reloaded on next launch
- **Smart date snapping** — changing the period length automatically snaps the start date to the nearest Monday (week/2-week) or first of month
- **Fairness balancing** — greedy scheduler with configurable swap passes to distribute shifts evenly
- **Understaffing detection** — slots that can't be filled are highlighted in red
- **CSV & PDF export** — one-click export from the Results tab; PDF renders as a calendar grid
- **CLI mode** — headless scheduling from a CSV availability file or demo data

---

## Quick Start

### GUI

```bash
python scheduler_app.py
```

1. Set the **Start date** and **Period length** (week / 2-week / month) in the Setup tab.
2. Click **＋ Add Worker** to enter each worker's name and per-day shift availability.
3. Click **▶ Generate Schedule**.
4. Switch to the **Results** tab to view the schedule and export it. Use the **Switch to Calendar / Switch to List** button to toggle views.

### CLI

```bash
# Run with built-in demo workers
python cli.py

# Generate a blank availability template
python cli.py --sample template.csv --start 2026-04-01 --period week

# Schedule from a filled-in CSV
python cli.py --csv availability.csv --start 2026-04-01 --period week

# Export to CSV and PDF
python cli.py --csv availability.csv --start 2026-04-01 --period week \
    --out-csv schedule.csv --out-pdf schedule.pdf
```

---

## Installation

No package installation is required for the GUI or CLI. Python 3.10+ with the standard library is sufficient.

**Optional — PDF export:**

```bash
pip install reportlab
```

---

## Availability CSV Format

The input CSV has one row per worker per available day:

```
name,date,morning,closing
Alice,2026-04-01,yes,no
Alice,2026-04-02,yes,yes
Bob,2026-04-01,no,yes
```

| Column    | Format     | Notes                                      |
|-----------|------------|--------------------------------------------|
| `name`    | text       | Worker name; rows with the same name are merged |
| `date`    | YYYY-MM-DD |                                            |
| `morning` | yes / no   | Also accepts: `y`, `1`, `true`, `x`        |
| `closing` | yes / no   | Same truthy values                         |

Generate a blank template for any period with `--sample`:

```bash
python cli.py --sample template.csv --start 2026-04-01 --period week
```

---

## CLI Reference

```
python cli.py [options]

Options:
  --csv FILE       Worker availability CSV file
  --sample FILE    Write a blank template CSV and exit
  --start DATE     Period start date YYYY-MM-DD (default: today)
  --period LENGTH  week | 2week | month  (default: 2week)
  --seed INT       Random seed for reproducibility (default: 42)
  --swaps INT      Fairness swap passes (default: 5)
  --out-csv FILE   Export generated schedule to CSV
  --out-pdf FILE   Export generated schedule to PDF
```

---

## Project Structure

```
schedular_app/
  scheduler_app.py        Entry point — launches the GUI
  cli.py                  Command-line interface
  core/
    models.py             Data models: Worker, ShiftType, ShiftAssignment
    scheduler.py          Scheduling algorithm (greedy + swap balancing)
    formatting.py         Shared utilities: date_range, build_period, sorted_workers
    export.py             CSV and PDF exporters
  ui/
    theme.py              Colour palette, fonts, widget factories
    worker_dialog.py      WorkerDialog — availability entry popup
    app.py                SchedulerApp — main window
  scheduler.py            Backwards-compatibility re-export shim
```

---

## Scheduling Algorithm

1. **Greedy pass** — for each (day, shift) slot, rank available workers by current shift count (fewest first), breaking ties randomly. Assign the top `WORKERS_PER_SHIFT` (default: 2).
2. **Swap passes** (repeated `--swaps` times):
   - *Fill understaffed* — any slot still short is topped up with available workers ranked by load.
   - *Balance loads* — swap one shift from the heaviest worker to the lightest worker where availability permits, if the imbalance is ≥ 2 shifts.

---

## Shift Types

| Shift   | Label |
|---------|-------|
| Morning | AM    |
| Closing | PM    |

Workers can be available for AM, PM, both, or neither on any given day.
