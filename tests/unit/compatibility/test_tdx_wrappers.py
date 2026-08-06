from pathlib import Path


ROOT = Path(__file__).parents[3]


def test_tdx_wrappers_delegate_without_legacy_database_coupling():
    for name in ("tdx_全局监控.py", "tdx_竞价监控.py"):
        source = (ROOT / "实时监控" / name).read_text(encoding="utf-8")
        assert "import pymysql" not in source
        assert "import config" not in source
        assert "from stock_lab.modules.tdx" in source
        assert len(source.splitlines()) < 40
