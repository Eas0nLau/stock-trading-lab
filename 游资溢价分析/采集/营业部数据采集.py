import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _path in (_ROOT, _SRC):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from stock_lab.modules.dragon_tiger.runtime import collect_broker_directory_data


def main():
    return collect_broker_directory_data()


if __name__ == "__main__":
    main()
