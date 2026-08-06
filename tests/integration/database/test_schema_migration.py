import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAPPING_PATH = ROOT / "db" / "schema_mapping.json"
CREATE_PATH = ROOT / "db" / "migrations" / "001_create_english_schema.sql"
MIGRATE_PATH = ROOT / "db" / "migrations" / "002_migrate_legacy_data.sql"
DROP_PATH = ROOT / "db" / "migrations" / "003_drop_legacy_schema.sql"
INIT_PATH = ROOT / "init" / "stock_trading_lab_v2.sql"


def load_mapping():
    return json.loads(MAPPING_PATH.read_text(encoding="utf-8"))


def sql_identifiers(sql):
    return re.findall(r"`([^`]+)`", sql)


def test_schema_mapping_contains_all_legacy_tables():
    mapping = load_mapping()["tables"]

    assert mapping["t_指数情绪周期_每日分析"]["table"] == "index_emotion_daily"
    assert mapping["t_同花顺板块成分股"]["table"] == "ths_board_constituents"
    assert len(mapping) == 16


def test_new_schema_contains_only_ascii_identifiers():
    sql = CREATE_PATH.read_text(encoding="utf-8")

    assert sql_identifiers(sql)
    assert all(identifier.isascii() for identifier in sql_identifiers(sql))


def test_every_mapped_table_is_created_and_copied_explicitly():
    mapping = load_mapping()["tables"]
    create_sql = CREATE_PATH.read_text(encoding="utf-8")
    migrate_sql = MIGRATE_PATH.read_text(encoding="utf-8")

    assert "SELECT *" not in migrate_sql.upper()
    for legacy_table, definition in mapping.items():
        new_table = definition["table"]
        assert f"CREATE TABLE `{new_table}`" in create_sql
        assert f"INSERT INTO `{new_table}`" in migrate_sql
        assert f"FROM `{legacy_table}`" in migrate_sql


def test_clean_initialization_never_runs_legacy_drop_script():
    init_sql = INIT_PATH.read_text(encoding="utf-8")
    drop_sql = DROP_PATH.read_text(encoding="utf-8")

    assert "003_drop_legacy_schema" not in init_sql
    assert "DROP TABLE IF EXISTS" in drop_sql
    assert all(identifier.isascii() for identifier in sql_identifiers(init_sql))
