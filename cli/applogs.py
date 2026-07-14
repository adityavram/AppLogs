#!/usr/bin/env python3
"""AppLogs CLI - Understand your behavior on your computer."""

import sys
from pathlib import Path

cli_dir = Path(__file__).parent
sys.path.insert(0, str(cli_dir))

from app import main

if __name__ == '__main__':
    sys.exit(main())