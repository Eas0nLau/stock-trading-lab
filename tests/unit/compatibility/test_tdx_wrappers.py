from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).parents[3]


def test_tdx_wrappers_delegate_without_legacy_database_coupling():
    for name in ("tdx_全局监控.py", "tdx_竞价监控.py"):
        source = (ROOT / "实时监控" / name).read_text(encoding="utf-8")
        assert "import pymysql" not in source
        assert "import config" not in source
        assert "from stock_lab.modules.tdx" in source
        assert len(source.splitlines()) < 40


def test_wrapper_can_import_from_checkout_without_installed_package():
    wrapper = ROOT / "实时监控" / "tdx_全局监控.py"
    result = subprocess.run([sys.executable, "-c", f"import runpy; runpy.run_path(r'{wrapper}', run_name='wrapper')"], cwd=ROOT, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
