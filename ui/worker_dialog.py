"""
WorkerDialog — modal popup for entering or editing a worker's availability.

Displays a scrollable grid of days × shift-state dropdowns.
Each dropdown cycles: none → AM → PM → AM+PM.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from datetime import date

from core.models import Worker, ShiftType
from ui.theme import (
    C_BG, C_SIDEBAR, C_TEXT, C_TEXT_LIGHT, C_CARD, C_BORDER,
    C_MORNING, C_CLOSING, C_BOTH, C_NONE, C_ACCENT, C_HINT_TEXT,
    FONT_TITLE, FONT_BODY, FONT_SMALL,
    styled_button,
)


class WorkerDialog(tk.Toplevel):
    """
    Pop-up dialog for entering or editing a single worker's availability.
    """

    STATES  = ["none", "morning", "closing", "both"]
    LABELS  = {"none": "—", "morning": "AM", "closing": "PM", "both": "AM+PM"}
    COLOURS = {"none": C_NONE, "morning": C_MORNING, "closing": C_CLOSING, "both": C_BOTH}

    def __init__(self, parent, days: list[date], worker: Worker | None = None):
        super().__init__(parent)
        self.title("Worker Availability")
        self.configure(bg=C_BG)
        self.resizable(True, True)
        self.grab_set()   # modal

        self.days = days
        self.result: Worker | None = None

        self._worker = worker
        self._states: list[str] = ["none"] * len(days)
        self._vars:   list[tk.StringVar] = []
        self._menus:  list[tk.Menubutton] = []
        self._name_var = tk.StringVar(value=worker.name if worker else "")

        self._build()
        self.update_idletasks()
        # Width must fit the day grid (canvas content doesn't propagate reqwidth)
        body_padding = 40   # padx=20 on each side of body frame
        w = max(self.winfo_reqwidth(), self._grid_frame.winfo_reqwidth() + body_padding)
        h = self.winfo_reqheight()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        self.geometry(f"{w}x{h}+{px + (pw - w)//2}+{py + (ph - h)//2}")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self):
        self._build_header()
        self._build_footer()   # packed first so body's expand=True doesn't push it off-screen
        body = tk.Frame(self, bg=C_BG, padx=20, pady=16)
        body.pack(fill="both", expand=True)
        self._build_name_row(body)
        self._build_legend(body)
        self._build_day_grid(body)
        self._build_quickfill(body)

    def _build_header(self):
        hdr = tk.Frame(self, bg=C_SIDEBAR, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Worker Availability", font=FONT_TITLE,
                 bg=C_SIDEBAR, fg=C_TEXT_LIGHT).pack(padx=20)

    def _build_name_row(self, body: tk.Frame):
        name_row = tk.Frame(body, bg=C_BG)
        name_row.pack(fill="x", pady=(0, 14))
        tk.Label(name_row, text="Worker name:", font=FONT_BODY,
                 bg=C_BG, fg=C_TEXT).pack(side="left")
        tk.Entry(name_row, textvariable=self._name_var, font=FONT_BODY,
                 width=24, relief="solid", bd=1).pack(side="left", padx=(8, 0))

    def _build_legend(self, body: tk.Frame):
        leg = tk.Frame(body, bg=C_BG)
        leg.pack(fill="x", pady=(0, 10))
        for state, colour in self.COLOURS.items():
            lf = tk.Frame(leg, bg=colour, relief="solid",
                          highlightbackground=C_BORDER, highlightthickness=1,
                          width=14, height=14)
            lf.pack(side="left", padx=(0, 2))
            lf.pack_propagate(False)
            tk.Label(leg, text=self.LABELS[state], font=FONT_SMALL,
                     bg=C_BG, fg=C_TEXT).pack(side="left", padx=(0, 12))
        tk.Label(leg, text="Select availability per day",
                 font=FONT_SMALL, bg=C_BG, fg="#888").pack(side="left")

    def _build_day_grid(self, body: tk.Frame):
        # Wrap in a canvas so long periods (month+) scroll cleanly
        canvas_frame = tk.Frame(body, bg=C_BG)
        canvas_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(canvas_frame, bg=C_BG, highlightthickness=0, height=340)
        vsb = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        grid_frame = tk.Frame(canvas, bg=C_BG)
        self._grid_frame = grid_frame
        win = canvas.create_window((0, 0), window=grid_frame, anchor="nw")

        def _on_inner_configure(_e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Only show scrollbar when content exceeds canvas height
            if grid_frame.winfo_reqheight() > canvas.winfo_height():
                vsb.pack(side="right", fill="y")
            else:
                vsb.pack_forget()

        def _on_canvas_configure(e):
            canvas.itemconfig(win, width=e.width)

        grid_frame.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * e.delta), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        canvas.pack(side="left", fill="both", expand=True)

        WEEK = 7
        weeks = [self.days[i:i + WEEK] for i in range(0, len(self.days), WEEK)]
        grid_row = 0
        for week_idx, week_days in enumerate(weeks):
            if week_idx > 0:
                tk.Frame(grid_frame, bg=C_BG, height=8).grid(
                    row=grid_row, column=0, columnspan=WEEK, sticky="ew"
                )
                grid_row += 1

            for col, day in enumerate(week_days):
                day_idx = week_idx * WEEK + col
                tk.Label(
                    grid_frame,
                    text=f"{day.strftime('%a')}\n{day.strftime('%m/%d')}",
                    font=FONT_SMALL, bg=C_SIDEBAR, fg=C_TEXT_LIGHT,
                    width=7, pady=4, relief="flat"
                ).grid(row=grid_row, column=col, padx=1, pady=(0, 2))

                if self._worker:
                    avail = [st for st in ShiftType if self._worker.is_available(day, st)]
                    if len(avail) == len(list(ShiftType)):
                        self._states[day_idx] = "both"
                    elif avail:
                        self._states[day_idx] = avail[0].name.lower()

                state = self._states[day_idx]
                var = tk.StringVar(value=self.LABELS[state])
                mb = tk.Menubutton(
                    grid_frame,
                    textvariable=var,
                    bg=self.COLOURS[state],
                    fg=C_TEXT,
                    font=FONT_SMALL,
                    width=7, pady=6,
                    relief="solid", bd=1,
                    cursor="hand2",
                    direction="below",
                )
                menu = tk.Menu(mb, tearoff=False, bg=C_CARD, fg=C_TEXT, font=FONT_SMALL)
                mb["menu"] = menu
                for s in self.STATES:
                    menu.add_command(
                        label=self.LABELS[s],
                        background=self.COLOURS[s],
                        command=lambda s=s, i=day_idx: self._on_select(i, s),
                    )
                mb.grid(row=grid_row + 1, column=col, padx=1, pady=1)
                self._vars.append(var)
                self._menus.append(mb)

            grid_row += 2


    def _build_quickfill(self, body: tk.Frame):
        qf = tk.Frame(body, bg=C_BG)
        qf.pack(fill="x", pady=(12, 0))
        tk.Label(qf, text="Quick fill:", font=FONT_SMALL, bg=C_BG, fg=C_TEXT).pack(side="left")
        for label, state, bg in [
            ("All AM",    "morning", C_MORNING),
            ("All PM",    "closing", C_CLOSING),
            ("All AM+PM", "both",    C_BOTH),
            ("Clear all", "none",    C_HINT_TEXT),
        ]:
            styled_button(qf, label, lambda s=state: self._fill_all(s),
                          bg=bg, fg=C_TEXT,
                          font=FONT_SMALL, padx=10, pady=3
                          ).pack(side="left", padx=4)

    def _build_footer(self):
        footer = tk.Frame(self, bg=C_BG, pady=12, padx=20)
        footer.pack(fill="x", side="bottom")
        styled_button(footer, "Cancel", self.destroy,
                      bg=C_BORDER, fg=C_TEXT).pack(side="right", padx=(6, 0))
        styled_button(footer, "Save Worker", self._save,
                      bg=C_ACCENT).pack(side="right")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_select(self, idx: int, state: str):
        self._states[idx] = state
        self._vars[idx].set(self.LABELS[state])
        self._menus[idx].configure(bg=self.COLOURS[state])

    def _fill_all(self, state: str):
        for i, (var, mb) in enumerate(zip(self._vars, self._menus)):
            self._states[i] = state
            var.set(self.LABELS[state])
            mb.configure(bg=self.COLOURS[state])

    def _save(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Please enter a worker name.", parent=self)
            return

        worker = Worker(name=name)
        for i, day in enumerate(self.days):
            state = self._states[i]
            shifts = []
            if state in ("morning", "both"):
                shifts.append(ShiftType.MORNING)
            if state in ("closing", "both"):
                shifts.append(ShiftType.CLOSING)
            worker.add_availability(day, shifts)

        self.result = worker
        self.destroy()
