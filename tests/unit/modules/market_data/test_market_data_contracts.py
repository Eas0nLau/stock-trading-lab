from pathlib import Path

from stock_lab.modules.market_data import MarketDataRepository, normalize_ts_code


ROOT = Path(__file__).parents[4]


def test_public_market_data_contract_is_exported():
    assert MarketDataRepository is not None
    assert normalize_ts_code("1.SZ") == "000001.SZ"


def test_shared_utility_sql_has_no_legacy_market_tables():
    for name in ("common.py", "account.py"):
        source = (ROOT / "utils" / name).read_text(encoding="utf-8")
        assert "FROM stock_basic" not in source
        assert "FROM stock_daily" not in source
        assert "FROM akshare_sh000001" not in source


def test_migration_docs_name_market_data_compatibility_boundary():
    migration = (ROOT / "docs" / "migration.md").read_text(encoding="utf-8")
    assert "market_data" in migration
    assert "daily_quotes" in migration
    assert "000001.SZ" in migration
