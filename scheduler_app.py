"""
Shift Scheduler — Desktop Application
======================================
Entry point. Run with:

    python scheduler_app.py

Requires Python 3 with tkinter (standard library).
PDF export optionally requires reportlab:  pip install reportlab
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ui.app import SchedulerApp

if __name__ == "__main__":
    app = SchedulerApp()
    app.mainloop()
