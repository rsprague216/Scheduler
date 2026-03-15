"""
UI theme: colour palette, fonts, and reusable widget factories.

All visual constants live here so any file can import them without
pulling in the rest of the GUI layer.
"""

from __future__ import annotations

import tkinter as tk

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

C_BG         = "#f5f6fa"
C_SIDEBAR    = "#1a1a2e"
C_SIDEBAR_LB = "#0f0f1e"       # listbox background (darker than sidebar)
C_SIDEBAR_DIM = "#8899bb"      # dimmed label text on sidebar
C_SIDEBAR_DIV = "#2a2a4a"      # divider line on sidebar
C_ACCENT     = "#4f8ef7"
C_ACCENT2    = "#e94560"
C_TEXT       = "#1a1a2e"
C_TEXT_LIGHT = "#ffffff"
C_CARD       = "#ffffff"
C_BORDER     = "#dde1f0"
C_ROW_ALT    = "#ecf0ff"
C_TOOLTIP_BG = "#fffbe6"

# Semantic button colours
C_BTN_EDIT   = "#2a5db0"       # sidebar Edit button
C_BTN_GEN    = "#27ae60"       # Generate Schedule button
C_BTN_TOGGLE = "#555566"       # Switch to Calendar/List toggle

# Text shades
C_TEXT_MID   = "#444444"       # medium-contrast body text
C_TEXT_DIM   = "#666666"       # dimmed text (summary bar, hints)
C_HINT_TEXT  = "#aaaaaa"       # placeholder / hint text

# Shift-state colours (used in WorkerDialog availability grid)
C_MORNING    = "#fff7e0"
C_CLOSING    = "#e0f0ff"
C_BOTH       = "#e8f8e8"
C_NONE       = "#f5f6fa"

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

FONT_TITLE   = ("Helvetica", 20, "bold")
FONT_HEAD    = ("Helvetica", 14, "bold")
FONT_BODY    = ("Helvetica", 12)
FONT_SMALL   = ("Helvetica", 11)
FONT_MONO    = ("Courier", 11)

# ---------------------------------------------------------------------------
# App-level constants
# ---------------------------------------------------------------------------

PERIODS  = ["week", "2week", "month"]

# Calendar view colours
C_CAL_UNDERSTAFFED  = "#fccfcf"
C_CAL_OUT_OF_PERIOD = "#efefef"

# ---------------------------------------------------------------------------
# Widget factories
# ---------------------------------------------------------------------------

def _darken(hex_color: str, factor: float = 0.82) -> str:
    """Return a darker shade of a hex color for hover states."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2  # expand #ccc → #cccccc
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"


def styled_button(parent, text, command, bg=C_ACCENT, fg=C_TEXT,
                  font=FONT_BODY, padx=16, pady=6, **kw) -> tk.Button:
    """Create a flat, hand-cursor tk.Button with hover darkening."""
    btn = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg, font=font,
        relief="flat", cursor="hand2",
        activebackground=bg, activeforeground=fg,
        padx=padx, pady=pady, **kw
    )
    hover = _darken(bg)
    btn.bind("<Enter>", lambda _e: btn.config(bg=hover, activebackground=hover))
    btn.bind("<Leave>", lambda _e: btn.config(bg=bg, activebackground=bg))
    return btn


def card_frame(parent, **kw) -> tk.Frame:
    """Return a white card-style frame with a border."""
    return tk.Frame(parent, bg=C_CARD, relief="flat",
                    highlightbackground=C_BORDER, highlightthickness=1, **kw)


class Tooltip:
    """Show a small popup label when the mouse hovers over a widget."""

    def __init__(self, widget, text: str):
        self._widget = widget
        self._text = text
        self._tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _e):
        x = self._widget.winfo_rootx() + self._widget.winfo_width() + 6
        y = self._widget.winfo_rooty() + self._widget.winfo_height() // 2
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self._tip, text=self._text, font=FONT_SMALL,
                 bg=C_TOOLTIP_BG, fg=C_TEXT, relief="solid", bd=1,
                 padx=8, pady=6, wraplength=240, justify="left"
                 ).pack()

    def _hide(self, _e):
        if self._tip:
            self._tip.destroy()
            self._tip = None
