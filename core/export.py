"""
Schedule exporters: CSV and PDF.

Both functions accept a Scheduler instance and a file path.
PDF export requires the optional 'reportlab' package.
"""

from __future__ import annotations

import csv
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from core.formatting import sorted_workers
from core.models import ShiftType

if TYPE_CHECKING:
    from core.scheduler import Scheduler


def export_schedule_csv(scheduler: "Scheduler", path: str | Path) -> None:
    """
    Export the generated schedule to a CSV file.

    Two sections are written in sequence:

    Section 1 — Daily schedule (one row per shift slot):
        date, weekday, shift, worker_1, worker_2, understaffed

    Section 2 — Shift count summary (one row per worker):
        worker, total_shifts
    """
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow(["date", "weekday", "shift", "worker_1", "worker_2", "understaffed"])
        for a in scheduler.schedule:
            sw = sorted_workers(a)
            w1 = sw[0] if len(sw) > 0 else ""
            w2 = sw[1] if len(sw) > 1 else ""
            writer.writerow([
                a.day.isoformat(),
                a.day.strftime("%A"),
                a.shift.value,
                w1,
                w2,
                "YES" if a.shortfall > 0 else "",
            ])

        writer.writerow([])
        writer.writerow(["--- Shift Count Summary ---"])
        writer.writerow(["worker", "total_shifts"])
        for name, count in sorted(scheduler.shift_counts().items(), key=lambda x: -x[1]):
            writer.writerow([name, count])

    print(f"Schedule CSV written to: {path}")


def export_schedule_pdf(scheduler: "Scheduler", path: str | Path) -> None:
    """
    Export the generated schedule to a formatted PDF using reportlab.

    Layout:
      - Title block with period dates
      - Schedule table grouped by week, with alternating row shading
        and red highlighting for understaffed slots
      - Shift count summary table on the same or following page

    Raises ImportError if reportlab is not installed.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )

    path = Path(path)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ScheduleTitle",
        parent=styles["Title"],
        fontSize=18,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ScheduleSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#555555"),
        spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "SectionHead",
        parent=styles["Heading2"],
        fontSize=11,
        spaceBefore=14,
        spaceAfter=4,
        textColor=colors.HexColor("#1a1a2e"),
    )

    COL_HEADER       = colors.HexColor("#1a1a2e")
    COL_ROW_ALT      = colors.HexColor("#f0f4ff")
    COL_UNDERSTAFFED = colors.HexColor("#ffe0e0")
    COL_WHITE        = colors.white
    COL_GRID         = colors.HexColor("#cccccc")

    story: list = []

    story.append(Paragraph("Staff Schedule", title_style))
    story.append(Paragraph(
        f"{scheduler.period_start.strftime('%B %d, %Y')}  &ndash;  "
        f"{scheduler.period_end.strftime('%B %d, %Y')}",
        subtitle_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=COL_HEADER, spaceAfter=12))

    # Calendar grid, grouped by week
    COL_LABEL_BG = COL_HEADER
    COL_EMPTY    = colors.HexColor("#eeeeee")

    SHIFT_COL_W = 0.85 * inch
    DAY_COL_W   = (7.0 * inch - SHIFT_COL_W) / 7
    cal_col_widths = [SHIFT_COL_W] + [DAY_COL_W] * 7

    # Build lookup: {day: {shift: assignment}}
    assign_map: dict = {}
    for a in scheduler.schedule:
        assign_map.setdefault(a.day, {})[a.shift] = a

    # Group days into ISO weeks
    all_days = sorted(assign_map.keys())
    weeks: list[list] = []
    current_week_key = None
    week_days_acc: list = []
    for d in all_days:
        wk = d.isocalendar()[:2]
        if wk != current_week_key:
            if week_days_acc:
                weeks.append(week_days_acc)
            week_days_acc = [d]
            current_week_key = wk
        else:
            week_days_acc.append(d)
    if week_days_acc:
        weeks.append(week_days_acc)

    for week_days_list in weeks:
        week_start = min(week_days_list)
        week_end   = max(week_days_list)
        story.append(Paragraph(
            f"Week of {week_start.strftime('%B %d')} &ndash; {week_end.strftime('%B %d, %Y')}",
            section_style,
        ))

        monday = week_start - timedelta(days=week_start.weekday())
        week_col_days = [monday + timedelta(days=i) for i in range(7)]

        # Row 0: day headers
        header_row = [""]
        for day in week_col_days:
            if day in assign_map:
                header_row.append(f"{day.strftime('%a')}\n{day.strftime('%b')} {day.day}")
            else:
                header_row.append("")

        table_data = [header_row]
        table_styles: list = [
            ("BACKGROUND", (0, 0), (-1, 0),  COL_LABEL_BG),
            ("TEXTCOLOR",  (0, 0), (-1, 0),  COL_WHITE),
            ("FONTNAME",   (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, 0),  8),
            ("BACKGROUND", (0, 1), (0, -1),  COL_LABEL_BG),
            ("TEXTCOLOR",  (0, 1), (0, -1),  COL_WHITE),
            ("FONTNAME",   (0, 1), (0, -1),  "Helvetica-Bold"),
            ("FONTSIZE",   (0, 1), (0, -1),  8),
            ("FONTNAME",   (1, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",   (1, 1), (-1, -1), 8),
            ("GRID",       (0, 0), (-1, -1), 0.4, COL_GRID),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]

        # Mark out-of-period header cells grey
        for col_idx, day in enumerate(week_col_days, start=1):
            if day not in assign_map:
                table_styles.append(
                    ("BACKGROUND", (col_idx, 0), (col_idx, 0), COL_EMPTY)
                )

        # Rows 1–2: Morning and Closing
        for shift_row_idx, shift in enumerate(
                [ShiftType.MORNING, ShiftType.CLOSING], start=1):
            row = [shift.value]
            for col_idx, day in enumerate(week_col_days, start=1):
                if day not in assign_map or shift not in assign_map[day]:
                    row.append("")
                    table_styles.append(
                        ("BACKGROUND", (col_idx, shift_row_idx),
                         (col_idx, shift_row_idx), COL_EMPTY)
                    )
                else:
                    a  = assign_map[day][shift]
                    sw = sorted_workers(a)
                    row.append("\n".join(sw) if sw else "\u2014")
                    if a.shortfall:
                        table_styles.append(
                            ("BACKGROUND", (col_idx, shift_row_idx),
                             (col_idx, shift_row_idx), COL_UNDERSTAFFED)
                        )
            table_data.append(row)

        t = Table(table_data, colWidths=cal_col_widths)
        t.setStyle(TableStyle(table_styles))
        story.append(t)
        story.append(Spacer(1, 10))

    # Shift count summary
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=COL_GRID, spaceAfter=8))
    story.append(Paragraph("Shift Count Summary", section_style))

    summary_data = [["Worker", "Total Shifts"]]
    for name, count in sorted(scheduler.shift_counts().items(), key=lambda x: -x[1]):
        summary_data.append([name, str(count)])

    summary_table = Table(summary_data, colWidths=[2.5*inch, 1.2*inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), COL_HEADER),
        ("TEXTCOLOR",     (0, 0), (-1, 0), COL_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("ROWBACKGROUND", (0, 1), (-1, -1), [COL_WHITE, COL_ROW_ALT]),
        ("GRID",          (0, 0), (-1, -1), 0.4, COL_GRID),
        ("ALIGN",         (1, 0), (1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)

    doc.build(story)
    print(f"Schedule PDF written to: {path}")
