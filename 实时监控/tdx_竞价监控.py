"""Compatibility launcher for the English TDX auction monitor."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from stock_lab.modules.tdx.auction_monitor import main


if __name__ == "__main__":
    main()
