"""Entry point used by PyInstaller (absolute imports, no package context)."""

import sys

from pulse_studio.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
