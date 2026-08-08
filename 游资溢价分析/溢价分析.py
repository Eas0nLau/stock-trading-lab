import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
for _path in (_ROOT, _SRC):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from stock_lab.modules.dragon_tiger.runtime import main as _run_analysis


def main(start_date, latest_date):
    return _run_analysis(int(start_date), int(latest_date))


if __name__ == "__main__":
    main(20260404, 20260803)
