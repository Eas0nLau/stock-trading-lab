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


def test_market_data_migration_uses_canonical_ids_and_beijing_exchange():
    migrate_sql = MIGRATE_PATH.read_text(encoding="utf-8")

    assert "CONCAT(LPAD(CAST(`code` AS CHAR), 6, '0'), '_', `time`, '_', `adjustflag`)" in migrate_sql
    assert migrate_sql.count("THEN CONCAT(LPAD(`ts_code`, 6, '0'), '.BJ')") == 4


THS_MIGRATIONS = {
    "ths_boards": {
        "legacy_table": "t_同花顺板块列表",
        "target_columns": (
            "board_code", "board_type", "board_name", "page_code",
            "detail_path", "collected_date", "updated_at",
        ),
        "source_columns": (
            "板块代码", "板块类型", "板块名称", "页面代码",
            "详情路径", "采集日期", "更新时间",
        ),
        "key_columns": ("board_code",),
    },
    "ths_board_constituents": {
        "legacy_table": "t_同花顺板块成分股",
        "target_columns": (
            "board_code", "stock_code", "board_type", "board_name",
            "page_code", "stock_name", "collected_date", "updated_at",
        ),
        "source_columns": (
            "板块代码", "股票代码", "板块类型", "板块名称",
            "页面代码", "股票名称", "采集日期", "更新时间",
        ),
        "key_columns": ("board_code", "stock_code"),
    },
    "ths_stock_relations": {
        "legacy_table": "t_同花顺股票板块概念对应关系",
        "target_columns": (
            "stock_code", "stock_name", "industry_names", "industry_codes",
            "concept_names", "concept_codes", "collected_date", "updated_at",
        ),
        "source_columns": (
            "股票代码", "股票名称", "同花顺行业", "同花顺行业代码",
            "同花顺概念", "同花顺概念代码", "采集日期", "更新时间",
        ),
        "key_columns": ("stock_code",),
    },
}


def ths_migration_statement(sql, target_table, legacy_table):
    match = re.search(
        rf"INSERT INTO `{target_table}` \((.*?)\)\s*"
        rf"SELECT (.*?)\s*FROM `{legacy_table}`\s*"
        r"ON DUPLICATE KEY UPDATE (.*?);",
        sql,
        re.DOTALL,
    )
    assert match is not None
    return match.groups()


def test_ths_imports_map_every_column_and_refresh_all_non_key_values():
    create_sql = CREATE_PATH.read_text(encoding="utf-8")
    migrate_sql = MIGRATE_PATH.read_text(encoding="utf-8")

    for target_table, definition in THS_MIGRATIONS.items():
        create_match = re.search(
            rf"CREATE TABLE `{target_table}` \((.*?)\) ENGINE=InnoDB",
            create_sql,
            re.DOTALL,
        )
        assert create_match is not None
        created_columns = tuple(
            re.findall(r"^\s*`([^`]+)`\s+", create_match.group(1), re.MULTILINE)
        )
        assert created_columns == definition["target_columns"]
        target_sql, source_sql, update_sql = ths_migration_statement(
            migrate_sql,
            target_table,
            definition["legacy_table"],
        )
        assert tuple(sql_identifiers(target_sql)) == definition["target_columns"]
        assert tuple(sql_identifiers(source_sql)) == definition["source_columns"]
        updated_columns = tuple(re.findall(r"`([^`]+)`\s*=\s*VALUES", update_sql))
        assert updated_columns == tuple(
            column
            for column in definition["target_columns"]
            if column not in definition["key_columns"]
        )


def test_ths_imports_have_row_count_validation_queries():
    migrate_sql = MIGRATE_PATH.read_text(encoding="utf-8")

    for target_table, definition in THS_MIGRATIONS.items():
        expected = (
            f"SELECT '{target_table}' AS `table_name`, "
            f"(SELECT COUNT(*) FROM `{definition['legacy_table']}`) AS `legacy_rows`, "
            f"(SELECT COUNT(*) FROM `{target_table}`) AS `new_rows`;"
        )
        assert expected in migrate_sql
