# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
python scheduler_app.py
```

Requires Python 3 with `tkinter` (standard library). PDF export optionally requires `reportlab`:

```bash
pip install reportlab
```

There is also a CLI:

```bash
python cli.py                          # run with demo data
python cli.py --sample template.csv   # generate blank availability template
python cli.py --csv availability.csv --start 2026-04-01 --period week --out-pdf schedule.pdf
```

## Architecture

The project is split into three layers:

```
scheduler_app.py   — entry point (thin wrapper that launches SchedulerApp)
scheduler.py       — backwards-compatibility shim; re-exports the public API
                     so old imports still work. New code should import from core/ directly.
cli.py             — command-line interface (argparse)
core/
  models.py        — data types: ShiftType, Worker, ShiftAssignment, Slot, constants
  scheduler.py     — scheduling engine (Scheduler class)
  formatting.py    — build_period, date_range, sorted_workers, understaffed_text
  export.py        — export_schedule_csv, export_schedule_pdf
ui/
  app.py           — SchedulerApp main window
  worker_dialog.py — WorkerDialog modal popup
  theme.py         — colour palette, fonts, widget factories (styled_button, card_frame, Tooltip)
```

### GUI Structure

`SchedulerApp` ([ui/app.py](ui/app.py)) is the main window with:
- **Left sidebar** — worker list with add/edit/remove buttons and a "Generate Schedule" button
- **Right content** — a two-tab `ttk.Notebook`:
  - **Setup tab** — start date, period length (week/2-week/month), swap passes
  - **Results tab** — schedule display + CSV/PDF export buttons + "Switch to Calendar / Switch to List" toggle

`WorkerDialog` ([ui/worker_dialog.py](ui/worker_dialog.py)) is a modal popup for entering a worker's name and per-day shift availability. Each day has a dropdown cycling: none → AM → PM → AM+PM. Days are laid out in rows of 7 (one week per row) with a vertical scrollbar.

### Data Flow

1. User adds workers via `WorkerDialog` → stored as `Worker` objects and auto-saved to `workers.json`
2. On startup, workers are loaded from `workers.json` (project root) if it exists
3. "Generate Schedule" reads start date + period config, calls `Scheduler`, renders results in both views
4. Understaffed shifts are highlighted in red; a summary bar shows shift counts
5. Export delegates to `export_schedule_csv()` / `export_schedule_pdf()` from `core/export.py`

### Worker Persistence

Workers are auto-saved to `workers.json` in the project root after every add/edit/remove. The file is loaded on startup. Serialization helpers live on the `Worker` dataclass (`to_dict()` / `from_dict()`). If the file is missing or corrupt, the app starts with an empty worker list. Save errors (e.g. permissions, full disk) show a user-visible error dialog rather than crashing silently.

### Start Date Snapping

When the period length dropdown changes, the start date is automatically snapped to the appropriate boundary, always relative to today:
- **week / 2-week** — next future Monday (or today if today is Monday)
- **month** — first day of next month

Snapping only happens on period-length selection. Dates chosen via the calendar picker are used as-is.

### Theme / UI Constants

Colors, fonts, shift-state colours, and widget factories live in [ui/theme.py](ui/theme.py):
- Colour constants: `C_BG`, `C_SIDEBAR`, `C_ACCENT`, `C_TEXT`, etc.
- Shift-state colours: `C_MORNING`, `C_CLOSING`, `C_BOTH`, `C_NONE`
- Calendar colours: `C_CAL_UNDERSTAFFED` (red tint for understaffed cells), `C_CAL_OUT_OF_PERIOD` (grey for days outside the scheduled period)
- Font constants: `FONT_TITLE`, `FONT_HEAD`, `FONT_BODY`, `FONT_SMALL`, `FONT_MONO`
- Widget factories: `styled_button()`, `card_frame()`, `Tooltip`

### Results Tab Views

The Results tab has two display modes toggled by the "Switch to Calendar / Switch to List" button:

- **List view** — `ttk.Treeview` with one row per shift slot (date, weekday, shift, worker 1, worker 2, status). Understaffed rows tagged `"understaffed"` (red bg); alternating rows tagged `"alt"`.
- **Calendar view** — scrollable canvas containing one week-band per ISO week. Each band is a grid: shift-label column (Morning / Closing) × 7 day columns (Mon–Sun). Worker names shown in each cell; understaffed cells in `C_CAL_UNDERSTAFFED`; days outside the scheduled period in `C_CAL_OUT_OF_PERIOD`. Implemented in `_build_calendar_view()` / `_populate_calendar()` on `SchedulerApp`.

Both views are populated together on every `_populate_results()` call. The toggle (`_toggle_view()`) uses `grid_remove()` / `grid()` to swap the `Treeview`+scrollbars vs. the `Canvas`+scrollbar in the same grid cell.

### PDF Export Layout

`export_schedule_pdf()` renders the schedule as a **calendar grid** (matching the GUI calendar view):
- One `Table` per ISO week: 8 columns (shift-label + Mon–Sun), 3 rows (header + Morning + Closing)
- Understaffed cells highlighted red; days outside the period shown in grey
- Followed by a Shift Count Summary table

### Sidebar Buttons

Sidebar action buttons (`+ Add Worker`, `Edit`, `Remove`, `▶ Generate Schedule`) use `styled_button()` from `ui/theme.py`. Default `fg` is `C_TEXT` (dark) to remain readable on macOS where tkinter often ignores the `bg` color on buttons.
