"""Runs the desktop app: python -m desktop (from backend/), or Dedalo.exe once packaged."""

import sys

from desktop.launcher import main

if __name__ == "__main__":
    sys.exit(main())
