"""
SchedulerApp — the main tkinter application window.

Responsible for:
  - Top bar and sidebar layout
  - Setup tab (period config, swap passes)
  - Results tab (schedule treeview, export buttons, summary bar)
  - Worker CRUD: add / edit / remove via WorkerDialog
  - Schedule generation and results population
"""

from __future__ import annotations

import json
import os
import platform
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, timedelta
from pathlib import Path

try:
    from tkcalendar import Calendar as _TkCalendar
    _HAS_TKCALENDAR = True
except ImportError:
    _HAS_TKCALENDAR = False

from core.models import Worker, ShiftType
from core.scheduler import Scheduler
from core.formatting import build_period, date_range, sorted_workers, understaffed_text
from core.export import export_schedule_csv, export_schedule_pdf
from ui.theme import (
    C_BG, C_SIDEBAR, C_SIDEBAR_LB, C_SIDEBAR_DIM, C_SIDEBAR_DIV,
    C_ACCENT, C_ACCENT2, C_TEXT, C_TEXT_LIGHT, C_CARD, C_BORDER, C_ROW_ALT,
    C_BTN_EDIT, C_BTN_GEN, C_BTN_TOGGLE,
    C_TEXT_MID, C_TEXT_DIM, C_HINT_TEXT,
    C_CAL_UNDERSTAFFED, C_CAL_OUT_OF_PERIOD,
    FONT_TITLE, FONT_HEAD, FONT_BODY, FONT_SMALL,
    PERIODS, styled_button, card_frame, Tooltip,
)
from ui.worker_dialog import WorkerDialog


def _get_data_dir() -> Path:
    """Return a writable user-data directory for workers.json.

    When frozen by PyInstaller, redirects to a platform-standard location
    since the app bundle directory is read-only. In development, uses the
    original project root.
    """
    if getattr(sys, "frozen", False):
        system = platform.system()
        if system == "Darwin":
            base = Path.home() / "Library" / "Application Support" / "SchedulerApp"
        elif system == "Windows":
            app_data = os.environ.get("APPDATA")
            base = Path(app_data) / "SchedulerApp" if app_data else Path.home() / "AppData" / "Roaming" / "SchedulerApp"
        else:  # Linux and other Unix
            xdg = os.environ.get("XDG_DATA_HOME")
            base = Path(xdg) / "SchedulerApp" if xdg else Path.home() / ".local" / "share" / "SchedulerApp"
        base.mkdir(parents=True, exist_ok=True)
        return base
    return Path(__file__).parent.parent


class SchedulerApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Shift Scheduler")
        self.configure(bg=C_BG)
        self.minsize(900, 640)
        self.geometry("1100x720")

        self._workers: list[Worker] = []
        self._scheduler: Scheduler | None = None
        self._save_file = _get_data_dir() / "workers.json"

        self._build_ui()
        self._load_workers()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        topbar = tk.Frame(self, bg=C_SIDEBAR, pady=14)
        topbar.pack(fill="x")
        tk.Label(topbar, text="⏱  Shift Scheduler", font=FONT_TITLE,
                 bg=C_SIDEBAR, fg=C_TEXT_LIGHT).pack(side="left", padx=20)

        main = tk.Frame(self, bg=C_BG)
        main.pack(fill="both", expand=True)

        left = tk.Frame(main, bg=C_SIDEBAR, width=230)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        right = tk.Frame(main, bg=C_BG)
        right.pack(side="left", fill="both", expand=True, padx=20, pady=16)

        self._build_sidebar(left)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",     background=C_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=C_BG, foreground=C_TEXT,
                        padding=[14, 6], font=FONT_BODY)
        style.map("TNotebook.Tab",
                  background=[("selected", C_ACCENT)],
                  foreground=[("selected", C_TEXT_LIGHT)])

        self._notebook = ttk.Notebook(right)
        self._notebook.pack(fill="both", expand=True)

        setup_tab   = tk.Frame(self._notebook, bg=C_BG)
        results_tab = tk.Frame(self._notebook, bg=C_BG)
        self._notebook.add(setup_tab,   text="  Setup  ")
        self._notebook.add(results_tab, text="  Results  ")

        self._build_setup_tab(setup_tab)
        self._build_results_tab(results_tab)

    def _build_sidebar(self, parent):
        tk.Label(parent, text="WORKERS", font=("Helvetica", 9, "bold"),
                 bg=C_SIDEBAR, fg=C_SIDEBAR_DIM).pack(anchor="w", padx=16, pady=(20, 6))

        lb_frame = tk.Frame(parent, bg=C_SIDEBAR)
        lb_frame.pack(fill="both", expand=True, padx=10)

        self._worker_lb = tk.Listbox(
            lb_frame, font=FONT_BODY,
            bg=C_SIDEBAR_LB, fg=C_TEXT_LIGHT,
            selectbackground=C_ACCENT, selectforeground=C_TEXT_LIGHT,
            relief="flat", bd=0, highlightthickness=0,
            activestyle="none",
        )
        self._worker_lb.pack(fill="both", expand=True)
        self._worker_lb.bind("<Double-Button-1>", lambda e: self._edit_worker())

        btn_area = tk.Frame(parent, bg=C_SIDEBAR, pady=10)
        btn_area.pack(fill="x", padx=10)

        for label, cmd, bg in [
            ("＋  Add Worker",  self._add_worker,    C_ACCENT),
            ("✎  Edit",        self._edit_worker,   C_BTN_EDIT),
            ("✕  Remove",      self._remove_worker, C_ACCENT2),
        ]:
            styled_button(btn_area, label, cmd, bg=bg, font=FONT_SMALL,
                          padx=8, pady=5, anchor="w"
                          ).pack(fill="x", pady=2)

        tk.Frame(parent, bg=C_SIDEBAR_DIV, height=1).pack(fill="x", padx=10, pady=8)

        styled_button(parent, "▶  Generate Schedule",
                      self._generate, bg=C_BTN_GEN, font=FONT_BODY,
                      padx=8, pady=8
                      ).pack(fill="x", padx=10, pady=(0, 6))

    def _build_setup_tab(self, parent):
        period_card = card_frame(parent)
        period_card.pack(fill="x", pady=(0, 14))

        tk.Label(period_card, text="Scheduling Period", font=FONT_HEAD,
                 bg=C_CARD, fg=C_TEXT).grid(row=0, column=0, columnspan=4,
                                             sticky="w", padx=16, pady=(12, 8))

        tk.Label(period_card, text="Start date:", font=FONT_BODY,
                 bg=C_CARD, fg=C_TEXT).grid(row=1, column=0, sticky="w", padx=(16, 6), pady=6)
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7
        self._start_var = tk.StringVar(
            value=(today + timedelta(days=days_until_monday)).isoformat()
        )
        date_row = tk.Frame(period_card, bg=C_CARD)
        date_row.grid(row=1, column=1, columnspan=2, sticky="w", pady=6)
        self._date_lbl = tk.Label(
            date_row, textvariable=self._start_var, font=FONT_BODY,
            bg="white", fg=C_TEXT, relief="solid", bd=1,
            padx=8, pady=3, cursor="hand2", width=11, anchor="w",
        )
        self._date_lbl.pack(side="left")
        if _HAS_TKCALENDAR:
            cal_btn = tk.Label(
                date_row, text="📅", font=FONT_BODY,
                bg=C_ACCENT, fg="white", relief="flat",
                padx=6, pady=3, cursor="hand2",
            )
            cal_btn.pack(side="left", padx=(2, 0))
            cal_btn.bind("<Button-1>", self._open_calendar)
            self._date_lbl.bind("<Button-1>", self._open_calendar)
        else:
            tk.Label(period_card, text="YYYY-MM-DD", font=FONT_SMALL,
                     bg=C_CARD, fg=C_HINT_TEXT).grid(row=1, column=2, sticky="w", padx=6)

        tk.Label(period_card, text="Period length:", font=FONT_BODY,
                 bg=C_CARD, fg=C_TEXT).grid(row=2, column=0, sticky="w", padx=(16, 6), pady=6)
        self._period_var = tk.StringVar(value="week")
        period_combo = ttk.Combobox(period_card, textvariable=self._period_var,
                                    values=PERIODS, state="readonly", width=12,
                                    font=FONT_BODY)
        period_combo.grid(row=2, column=1, sticky="w", pady=6)

        def _on_period_change(event=None):
            self._start_var.set(self._snap_start_date(self._period_var.get(), date.today()).isoformat())

        period_combo.bind("<<ComboboxSelected>>", _on_period_change)

        swaps_label_frame = tk.Frame(period_card, bg=C_CARD)
        swaps_label_frame.grid(row=3, column=0, sticky="w", padx=(16, 6), pady=6)
        tk.Label(swaps_label_frame, text="Swap passes:", font=FONT_BODY,
                 bg=C_CARD, fg=C_TEXT).pack(side="left")
        info_lbl = tk.Label(swaps_label_frame, text="ⓘ", font=FONT_SMALL,
                            bg=C_CARD, fg=C_ACCENT, cursor="question_arrow")
        info_lbl.pack(side="left", padx=(4, 0))
        Tooltip(info_lbl,
                "Swap passes control how hard the scheduler tries to balance\n"
                "shifts fairly between workers. Each pass attempts to swap\n"
                "shifts to reduce imbalances. More passes = fairer result,\n"
                "but slightly slower. 3–7 is a good range for most teams.")
        self._swaps_var = tk.IntVar(value=5)
        swaps_row = tk.Frame(period_card, bg=C_CARD)
        swaps_row.grid(row=3, column=1, sticky="w", pady=(6, 12))

        def _dec_swaps():
            self._swaps_var.set(max(0, self._swaps_var.get() - 1))

        def _inc_swaps():
            self._swaps_var.set(min(20, self._swaps_var.get() + 1))

        for text, cmd in [("−", _dec_swaps), ("+", _inc_swaps)]:
            lbl = tk.Label(swaps_row, text=text, font=FONT_BODY,
                           bg=C_BORDER, fg=C_TEXT, cursor="hand2",
                           padx=8, pady=2, relief="flat")
            lbl.bind("<Button-1>", lambda _e, c=cmd: c())
            lbl.bind("<Enter>", lambda _e, l=lbl: l.config(bg=C_ACCENT, fg=C_TEXT_LIGHT))
            lbl.bind("<Leave>", lambda _e, l=lbl: l.config(bg=C_BORDER, fg=C_TEXT))
            if text == "−":
                lbl.pack(side="left")
                tk.Entry(swaps_row, textvariable=self._swaps_var, font=FONT_BODY,
                         width=3, relief="solid", bd=1, justify="center"
                         ).pack(side="left", padx=2)
            else:
                lbl.pack(side="left")

        hint = card_frame(parent)
        hint.pack(fill="x")
        hint_text = (
            "1.  Set the period start date and length above.\n"
            "2.  Add each worker using the sidebar — set their available days and shifts.\n"
            "3.  Click  ▶ Generate Schedule  to run the scheduler.\n"
            "4.  Switch to the Results tab to view, export CSV, or export PDF."
        )
        tk.Label(hint, text="How to use", font=FONT_HEAD,
                 bg=C_CARD, fg=C_TEXT).pack(anchor="w", padx=16, pady=(12, 4))
        tk.Label(hint, text=hint_text, font=FONT_BODY, bg=C_CARD,
                 fg=C_TEXT_MID, justify="left"
                 ).pack(anchor="w", padx=16, pady=(0, 14))

    def _build_results_tab(self, parent):
        self._view_mode = "list"

        toolbar = tk.Frame(parent, bg=C_BG)
        toolbar.pack(fill="x", pady=(0, 10))
        tk.Label(toolbar, text="Generated Schedule", font=FONT_HEAD,
                 bg=C_BG, fg=C_TEXT).pack(side="left")
        styled_button(toolbar, "Export CSV", self._export_csv,
                      bg=C_ACCENT, font=FONT_SMALL, padx=12, pady=4
                      ).pack(side="right", padx=(6, 0))
        styled_button(toolbar, "Export PDF", self._export_pdf,
                      bg=C_ACCENT2, font=FONT_SMALL, padx=12, pady=4
                      ).pack(side="right", padx=(6, 0))
        self._toggle_btn = styled_button(toolbar, "Switch to Calendar",
                                         self._toggle_view,
                                         bg=C_BTN_TOGGLE, font=FONT_SMALL, padx=12, pady=4)
        self._toggle_btn.pack(side="right")

        tbl_frame = tk.Frame(parent, bg=C_BG)
        tbl_frame.pack(fill="both", expand=True)

        cols = ("date", "weekday", "shift", "worker_1", "worker_2", "status")
        style = ttk.Style()
        style.configure("Schedule.Treeview",
                        background=C_CARD, fieldbackground=C_CARD,
                        foreground=C_TEXT, font=FONT_BODY, rowheight=28)
        style.configure("Schedule.Treeview.Heading",
                        background=C_SIDEBAR, foreground=C_TEXT_LIGHT,
                        font=("Helvetica", 10, "bold"), relief="flat")
        style.map("Schedule.Treeview", background=[("selected", C_ACCENT)])

        self._tree = ttk.Treeview(tbl_frame, columns=cols, show="headings",
                                  style="Schedule.Treeview")
        col_widths = {"date": 90, "weekday": 90, "shift": 80,
                      "worker_1": 130, "worker_2": 130, "status": 110}
        for col in cols:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=col_widths[col], anchor="center")

        self._tree_vsb = ttk.Scrollbar(tbl_frame, orient="vertical",   command=self._tree.yview)
        self._tree_hsb = ttk.Scrollbar(tbl_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=self._tree_vsb.set, xscrollcommand=self._tree_hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        self._tree_vsb.grid(row=0, column=1, sticky="ns")
        self._tree_hsb.grid(row=1, column=0, sticky="ew")
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        self._tree.tag_configure("understaffed", background=C_CAL_UNDERSTAFFED)
        self._tree.tag_configure("alt",          background=C_ROW_ALT)

        self._build_calendar_view(tbl_frame)

        self._summary_var = tk.StringVar(value="No schedule generated yet.")
        tk.Label(parent, textvariable=self._summary_var, font=FONT_BODY,
                 bg=C_BG, fg=C_TEXT_DIM, anchor="w"
                 ).pack(fill="x", pady=(6, 0))

    # ------------------------------------------------------------------
    # Worker management
    # ------------------------------------------------------------------

    def _open_calendar(self, event=None):
        try:
            initial = date.fromisoformat(self._start_var.get().strip())
        except ValueError:
            initial = date.today()

        popup = tk.Toplevel(self)
        popup.title("Select Date")
        popup.resizable(False, False)
        popup.transient(self)

        # Position near the date label
        x = self._date_lbl.winfo_rootx()
        y = self._date_lbl.winfo_rooty() + self._date_lbl.winfo_height() + 2
        popup.geometry(f"+{x}+{y}")

        cal = _TkCalendar(
            popup,
            selectmode="day",
            year=initial.year, month=initial.month, day=initial.day,
            date_pattern="yyyy-mm-dd",
            background=C_ACCENT, foreground="white",
            headersbackground=C_SIDEBAR, headersforeground="white",
            selectbackground=C_ACCENT2, selectforeground="white",
            normalbackground="white", normalforeground=C_TEXT,
            weekendbackground="#f5f5f5", weekendforeground=C_TEXT,
            font=FONT_BODY,
        )
        cal.pack(padx=6, pady=6)

        def _pick():
            self._start_var.set(cal.get_date())
            popup.destroy()

        styled_button(popup, "Select", _pick, bg=C_ACCENT, font=FONT_BODY,
                      padx=10, pady=4).pack(pady=(0, 8))

        # Close when focus moves outside the popup and all its descendants
        def _on_focus_out(e):
            # After a short delay, check if focus is still inside the popup tree
            def _check():
                focused = popup.focus_get()
                if focused is None or not str(focused).startswith(str(popup)):
                    popup.destroy()
            popup.after(50, _check)

        popup.bind("<FocusOut>", _on_focus_out)
        popup.focus_set()

    def _snap_start_date(self, period: str, d: date) -> date:
        p = period.lower().replace("-", "").replace(" ", "")
        if p in ("week", "2week", "twoweek", "biweek"):
            days_until_monday = (7 - d.weekday()) % 7
            return d + timedelta(days=days_until_monday)
        elif p == "month":
            if d.month == 12:
                return date(d.year + 1, 1, 1)
            return date(d.year, d.month + 1, 1)
        return d

    def _get_start_date(self) -> date | None:
        try:
            return date.fromisoformat(self._start_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid date", "Start date must be in YYYY-MM-DD format.")
            return None

    def _get_period_days(self) -> list[date] | None:
        start = self._get_start_date()
        if start is None:
            return None
        period_start, period_end = build_period(start, self._period_var.get())
        return date_range(period_start, period_end)

    def _add_worker(self):
        days = self._get_period_days()
        if days is None:
            return
        dlg = WorkerDialog(self, days)
        self.wait_window(dlg)
        if dlg.result:
            if any(w.name == dlg.result.name for w in self._workers):
                messagebox.showwarning("Duplicate name",
                                       f"A worker named '{dlg.result.name}' already exists.")
                return
            self._workers.append(dlg.result)
            self._refresh_worker_list()
            self._save_workers()

    def _edit_worker(self):
        sel = self._worker_lb.curselection()
        if not sel:
            messagebox.showinfo("No selection", "Select a worker to edit.")
            return
        days = self._get_period_days()
        if days is None:
            return
        idx    = sel[0]
        worker = self._workers[idx]
        dlg    = WorkerDialog(self, days, worker=worker)
        self.wait_window(dlg)
        if dlg.result:
            self._workers[idx] = dlg.result
            self._refresh_worker_list()
            self._save_workers()

    def _remove_worker(self):
        sel = self._worker_lb.curselection()
        if not sel:
            messagebox.showinfo("No selection", "Select a worker to remove.")
            return
        name = self._workers[sel[0]].name
        if messagebox.askyesno("Confirm", f"Remove worker '{name}'?"):
            self._workers.pop(sel[0])
            self._refresh_worker_list()
            self._save_workers()

    def _load_workers(self):
        if not self._save_file.exists():
            self._refresh_worker_list()
            return
        try:
            with open(self._save_file) as f:
                data = json.load(f)
            self._workers = [Worker.from_dict(w) for w in data.get("workers", [])]
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass  # Corrupt or unreadable file — start fresh
        self._refresh_worker_list()

    def _save_workers(self):
        data = {"version": 1, "workers": [w.to_dict() for w in self._workers]}
        try:
            with open(self._save_file, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            messagebox.showerror("Save Error", f"Could not save workers:\n{e}")

    def _refresh_worker_list(self):
        self._worker_lb.delete(0, "end")
        for w in self._workers:
            slots = len(w.availability)
            self._worker_lb.insert("end", f"  {w.name}  ({slots} slots)")

    # ------------------------------------------------------------------
    # Schedule generation
    # ------------------------------------------------------------------

    def _generate(self):
        if not self._workers:
            messagebox.showwarning("No workers", "Add at least one worker before generating.")
            return
        start = self._get_start_date()
        if start is None:
            return

        period_start, period_end = build_period(start, self._period_var.get())
        self._scheduler = Scheduler(self._workers, period_start, period_end)
        self._scheduler.generate(swap_passes=self._swaps_var.get())

        self._populate_results()
        self._notebook.select(1)

    def _populate_results(self):
        if not self._scheduler:
            return

        for row in self._tree.get_children():
            self._tree.delete(row)

        alt = False
        for a in self._scheduler.schedule:
            sw = sorted_workers(a)
            w1 = sw[0] if len(sw) > 0 else "—"
            w2 = sw[1] if len(sw) > 1 else "—"
            status = understaffed_text(a)
            tag = "understaffed" if a.shortfall else ("alt" if alt else "")
            self._tree.insert("", "end", values=(
                a.day.isoformat(),
                a.day.strftime("%A"),
                a.shift.value,
                w1, w2, status,
            ), tags=(tag,))
            alt = not alt

        counts  = self._scheduler.shift_counts()
        us      = self._scheduler.understaffed_slots()
        total   = len(self._scheduler.schedule)
        summary = (
            f"  {total} slots scheduled  |  "
            f"{len(us)} understaffed  |  "
            f"Shifts per worker: " +
            ",  ".join(f"{n} {c}" for n, c in
                       sorted(counts.items(), key=lambda x: -x[1]))
        )
        self._summary_var.set(summary)
        self._populate_calendar()

    def _build_calendar_view(self, tbl_frame):
        self._cal_canvas = tk.Canvas(tbl_frame, bg=C_BG, highlightthickness=0)
        self._cal_vsb = ttk.Scrollbar(tbl_frame, orient="vertical",
                                       command=self._cal_canvas.yview)
        self._cal_canvas.configure(yscrollcommand=self._cal_vsb.set)

        self._cal_inner = tk.Frame(self._cal_canvas, bg=C_BG)
        self._cal_window = self._cal_canvas.create_window(
            (0, 0), window=self._cal_inner, anchor="nw")

        def _on_inner_configure(e):
            self._cal_canvas.configure(scrollregion=self._cal_canvas.bbox("all"))

        def _on_canvas_configure(e):
            self._cal_canvas.itemconfig(self._cal_window, width=e.width)

        self._cal_inner.bind("<Configure>", _on_inner_configure)
        self._cal_canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(e):
            self._cal_canvas.yview_scroll(int(-1 * e.delta), "units")

        self._cal_canvas.bind("<Enter>",
                               lambda e: self._cal_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self._cal_canvas.bind("<Leave>",
                               lambda e: self._cal_canvas.unbind_all("<MouseWheel>"))

        self._cal_canvas.grid(row=0, column=0, sticky="nsew")
        self._cal_vsb.grid(row=0, column=1, sticky="ns")
        self._cal_canvas.grid_remove()
        self._cal_vsb.grid_remove()

    def _populate_calendar(self):
        if not self._scheduler:
            return

        for child in self._cal_inner.winfo_children():
            child.destroy()

        # Build lookup: {day: {shift: assignment}}
        assign_map: dict = {}
        for a in self._scheduler.schedule:
            assign_map.setdefault(a.day, {})[a.shift] = a

        all_days = sorted(assign_map.keys())
        if not all_days:
            return

        # Group days into ISO weeks
        weeks: list[list] = []
        current_week_key = None
        week_days: list = []
        for d in all_days:
            wk = d.isocalendar()[:2]
            if wk != current_week_key:
                if week_days:
                    weeks.append(week_days)
                week_days = [d]
                current_week_key = wk
            else:
                week_days.append(d)
        if week_days:
            weeks.append(week_days)

        band_row = 0
        for week_days_list in weeks:
            week_start = min(week_days_list)
            week_end   = max(week_days_list)
            week_label = (
                f"Week of {week_start.strftime('%b')} {week_start.day}"
                f" \u2013 {week_end.strftime('%b')} {week_end.day}, {week_end.year}"
            )
            tk.Label(self._cal_inner, text=week_label, font=FONT_HEAD,
                     bg=C_BG, fg=C_TEXT, anchor="w"
                     ).grid(row=band_row, column=0, sticky="ew", padx=4, pady=(10, 2))
            band_row += 1

            band = tk.Frame(self._cal_inner, bg=C_BORDER, bd=1, relief="solid")
            band.grid(row=band_row, column=0, sticky="ew", padx=4, pady=(0, 4))
            band_row += 1

            # 7 day columns Mon–Sun relative to the first day of this week
            monday = week_start - timedelta(days=week_start.weekday())
            week_col_days = [monday + timedelta(days=i) for i in range(7)]

            # Day header row (row 0, cols 1–7; col 0 is shift-label placeholder)
            tk.Label(band, text="", bg=C_SIDEBAR, width=9
                     ).grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

            for col_idx, day in enumerate(week_col_days):
                in_period = day in assign_map
                day_text  = f"{day.strftime('%a')}\n{day.strftime('%b')} {day.day}"
                bg = C_SIDEBAR  if in_period else C_CAL_OUT_OF_PERIOD
                fg = C_TEXT_LIGHT if in_period else "#aaaaaa"
                tk.Label(band, text=day_text, font=FONT_SMALL, bg=bg, fg=fg,
                         width=12, justify="center", pady=4
                         ).grid(row=0, column=col_idx + 1, sticky="nsew", padx=1, pady=1)

            # AM and PM rows
            for shift_row, shift in enumerate(
                    [ShiftType.MORNING, ShiftType.CLOSING], start=1):
                tk.Label(band, text=shift.value, font=FONT_SMALL,
                         bg=C_SIDEBAR, fg=C_TEXT_LIGHT, width=9, pady=6
                         ).grid(row=shift_row, column=0, sticky="nsew", padx=1, pady=1)

                for col_idx, day in enumerate(week_col_days):
                    if day not in assign_map or shift not in assign_map[day]:
                        tk.Label(band, text="", bg=C_CAL_OUT_OF_PERIOD, width=12, pady=6
                                 ).grid(row=shift_row, column=col_idx + 1,
                                        sticky="nsew", padx=1, pady=1)
                    else:
                        a  = assign_map[day][shift]
                        sw = sorted_workers(a)
                        workers_text = "\n".join(sw) if sw else "\u2014"
                        bg = C_CAL_UNDERSTAFFED if a.shortfall else C_CARD
                        tk.Label(band, text=workers_text, font=FONT_SMALL,
                                 bg=bg, fg=C_TEXT, width=12, justify="center",
                                 pady=6, wraplength=100
                                 ).grid(row=shift_row, column=col_idx + 1,
                                        sticky="nsew", padx=1, pady=1)

            for col_idx in range(8):
                band.columnconfigure(col_idx, weight=1)

        self._cal_inner.columnconfigure(0, weight=1)

    def _toggle_view(self):
        if self._view_mode == "list":
            self._view_mode = "calendar"
            self._tree.grid_remove()
            self._tree_vsb.grid_remove()
            self._tree_hsb.grid_remove()
            self._cal_canvas.grid()
            self._cal_vsb.grid()
            self._toggle_btn.config(text="Switch to List")
        else:
            self._view_mode = "list"
            self._cal_canvas.grid_remove()
            self._cal_vsb.grid_remove()
            self._tree.grid()
            self._tree_vsb.grid()
            self._tree_hsb.grid()
            self._toggle_btn.config(text="Switch to Calendar")

    # ------------------------------------------------------------------
    # Exports
    # ------------------------------------------------------------------

    def _export(self, fmt: str):
        if not self._scheduler:
            messagebox.showinfo("No schedule", "Generate a schedule first.")
            return
        if fmt == "csv":
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Save Schedule CSV",
            )
            if path:
                export_schedule_csv(self._scheduler, path)
                messagebox.showinfo("Exported", f"CSV saved to:\n{path}")
        else:
            path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                title="Save Schedule PDF",
            )
            if path:
                try:
                    export_schedule_pdf(self._scheduler, path)
                    messagebox.showinfo("Exported", f"PDF saved to:\n{path}")
                except ImportError:
                    messagebox.showerror(
                        "Missing library",
                        "PDF export requires reportlab.\n"
                        "Install it with:  pip install reportlab"
                    )

    def _export_csv(self):
        self._export("csv")

    def _export_pdf(self):
        self._export("pdf")
