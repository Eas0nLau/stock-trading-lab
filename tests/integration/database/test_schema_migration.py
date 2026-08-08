import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MAPPING_PATH = ROOT / "db" / "schema_mapping.json"
CREATE_PATH = ROOT / "db" / "migrations" / "001_create_english_schema.sql"
MIGRATE_PATH = ROOT / "db" / "migrations" / "002_migrate_legacy_data.sql"
DROP_PATH = ROOT / "db" / "migrations" / "003_drop_legacy_schema.sql"
INIT_PATH = ROOT / "init" / "stock_trading_lab_v2.sql"
OLD_INIT_PATH = ROOT / "init" / "stock_trading_lab.sql"
LEGACY_INIT_PATH = ROOT / "init" / "LEGACY_stock_trading_lab_chinese_schema.sql"


MIGRATIONS = {
    "index_daily": {
        "source": "akshare_sh000001",
        "keys": ("trade_date",),
        "date": True,
        "aggregate": True,
    },
    "index_market_breadth": {
        "source": "t_指数情绪周期_市场宽度",
        "keys": ("trade_date",),
        "date": True,
        "aggregate": True,
    },
    "index_emotion_daily": {
        "source": "t_指数情绪周期_每日分析",
        "keys": ("trade_date",),
        "date": True,
        "aggregate": True,
        "json": True,
    },
    "hot_board_emotion_daily": {
        "source": "t_热门板块情绪_每日分析",
        "keys": ("trade_date", "board_name"),
        "date": True,
        "aggregate": True,
        "json": True,
    },
    "securities": {"source": "stock_basic", "keys": ("ts_code",)},
    "daily_quotes": {
        "source": "stock_daily",
        "keys": ("data_id",),
        "date": True,
        "aggregate": True,
    },
    "kdj_indicators": {
        "source": "stock_kdj",
        "keys": ("data_id",),
        "date": True,
        "aggregate": True,
    },
    "intraday_bars_5m": {
        "source": "t_stock_5_min_k",
        "keys": ("data_id",),
        "date": True,
        "aggregate": True,
    },
    "jiuyan_actions": {
        "source": "t_韭研公社异动解析",
        "keys": ("data_id",),
        "date": True,
        "aggregate": True,
    },
    "dragon_tiger": {
        "source": "t_龙虎榜",
        "keys": ("data_id",),
        "date": True,
        "aggregate": True,
    },
    "broker_listing_history": {
        "source": "t_龙虎榜_营业部_上榜历史数据",
        "keys": ("data_id",),
        "date": True,
        "aggregate": True,
    },
    "broker_top_stats": {
        "source": "t_龙虎榜_营业部_上榜次数最多",
        "keys": ("broker_id",),
        "aggregate": True,
    },
    "brokers": {"source": "t_龙虎榜_营业部_全部", "keys": ("broker_id",)},
    "ths_boards": {
        "source": "t_同花顺板块列表",
        "keys": ("board_code",),
        "date": True,
    },
    "ths_board_constituents": {
        "source": "t_同花顺板块成分股",
        "keys": ("board_code", "stock_code"),
        "date": True,
    },
    "ths_stock_relations": {
        "source": "t_同花顺股票板块概念对应关系",
        "keys": ("stock_code",),
        "date": True,
    },
}


def load_mapping():
    return json.loads(MAPPING_PATH.read_text(encoding="utf-8"))


def sql_identifiers(sql):
    return re.findall(r"`([^`]+)`", sql)


def copied_statement(sql, target_table, source_table):
    match = re.search(
        rf"INSERT INTO `{re.escape(target_table)}` \((.*?)\)\s*"
        rf"SELECT\s+(.*?)\s*FROM `{re.escape(source_table)}`(?:\s+WHERE.*?)?\s*"
        r"ON DUPLICATE KEY UPDATE (.*?);",
        sql,
        re.DOTALL,
    )
    assert match is not None, f"missing copy statement for {target_table}"
    return match.groups()


def parity_call(sql, target_table):
    match = re.search(
        rf"CALL assert_mapping_parity\(\s*'{re.escape(target_table)}',(.*?)\n\);",
        sql,
        re.DOTALL,
    )
    assert match is not None, f"missing executable parity gate for {target_table}"
    return match.group(1)


def split_sql_list(sql):
    items = []
    start = 0
    depth = 0
    quote = None
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote:
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    index += 1
                else:
                    quote = None
        elif char in "'\"`":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            assert depth >= 0
        elif char == "," and depth == 0:
            items.append(sql[start:index].strip())
            start = index + 1
        index += 1
    assert quote is None and depth == 0
    items.append(sql[start:].strip())
    return tuple(items)


def test_schema_mapping_contains_exactly_the_16_migrations():
    mapping = load_mapping()["tables"]

    assert len(mapping) == 16
    assert {definition["table"] for definition in mapping.values()} == set(MIGRATIONS)
    assert all(mapping[item["source"]]["table"] == target for target, item in MIGRATIONS.items())


def test_001_is_resumable_but_validates_compatibility_before_recording():
    sql = CREATE_PATH.read_text(encoding="utf-8")
    mapped_tables = set(MIGRATIONS)

    created_tables = re.findall(r"CREATE TABLE IF NOT EXISTS `([^`]+)`", sql)
    assert set(created_tables) == mapped_tables | {
        "schema_migrations",
        "migration_validations",
        "fund_flow_snapshots",
        "fund_flow_records",
        "strategy_definitions",
        "strategy_pick_snapshots",
        "strategy_pick_stocks",
        "strategy_pick_events",
    }
    compatibility_calls = re.findall(
        r"CALL assert_table_compatible\(\s*'([^']+)',\s*'([^']*)',\s*'([^']*)'\s*\)",
        sql,
        re.DOTALL,
    )
    assert {call[0] for call in compatibility_calls} == set(created_tables)
    assert sql.index("DROP PROCEDURE IF EXISTS assert_table_compatible;") < sql.index(
        "CREATE PROCEDURE assert_table_compatible("
    )
    assert sql.index("DROP PROCEDURE IF EXISTS validate_english_schema;") < sql.index(
        "CREATE PROCEDURE validate_english_schema()"
    )
    assert sql.index("CALL validate_english_schema();") < sql.index(
        "INSERT INTO `schema_migrations` (`version`)"
    )
    assert "ON DUPLICATE KEY UPDATE `applied_at`=`applied_at`" in sql
    assert "SIGNAL SQLSTATE '45000'" in sql


def test_001_compatibility_signatures_match_the_declared_ddl():
    sql = CREATE_PATH.read_text(encoding="utf-8")
    calls = {
        table: (columns, indexes)
        for table, columns, indexes in re.findall(
            r"CALL assert_table_compatible\(\s*'([^']+)',\s*'([^']*)',\s*'([^']*)'\s*\)",
            sql,
            re.DOTALL,
        )
    }

    for table, (column_signature, index_signature) in calls.items():
        body = re.search(
            rf"CREATE TABLE IF NOT EXISTS `{table}` \((.*?)\) ENGINE=InnoDB",
            sql,
            re.DOTALL,
        ).group(1)
        columns = []
        for name, data_type, remainder in re.findall(
            r"^\s*`([^`]+)`\s+([a-z]+(?:\([0-9,]+\))?)(.*?)(?:,)?$",
            body,
            re.MULTILINE | re.IGNORECASE,
        ):
            nullable = "NO" if "NOT NULL" in remainder.upper() else "YES"
            columns.append(f"{name}:{data_type.lower()}:{nullable}")
        assert column_signature == "|".join(columns), table

        indexes = []
        primary = re.search(r"PRIMARY KEY \(([^)]+)\)", body)
        if primary:
            indexes.append(f"PRIMARY:0({','.join(sql_identifiers(primary.group(1)))})")
        indexes.extend(
            f"{name}:0({','.join(sql_identifiers(key_columns))})"
            for name, key_columns in re.findall(r"UNIQUE KEY `([^`]+)` \(([^)]+)\)", body)
        )
        indexes.extend(
            f"{name}:1({','.join(sql_identifiers(key_columns))})"
            for name, key_columns in re.findall(r"(?<!UNIQUE )KEY `([^`]+)` \(([^)]+)\)", body)
        )
        assert index_signature == "|".join(sorted(indexes, key=str.lower)), table


def test_001_declares_stable_indexes_for_all_foreign_key_columns():
    sql = CREATE_PATH.read_text(encoding="utf-8")

    for table_body in re.findall(r"CREATE TABLE IF NOT EXISTS `[^`]+` \((.*?)\) ENGINE=InnoDB", sql, re.DOTALL):
        indexed_columns = {
            sql_identifiers(columns)[0]
            for columns in re.findall(r"(?:PRIMARY KEY|(?:UNIQUE )?KEY `[^`]+`) \(([^)]+)\)", table_body)
        }
        for foreign_columns in re.findall(r"FOREIGN KEY \(([^)]+)\)", table_body):
            assert sql_identifiers(foreign_columns)[0] in indexed_columns


def test_new_schema_contains_only_ascii_identifiers():
    sql = CREATE_PATH.read_text(encoding="utf-8")

    assert sql_identifiers(sql)
    assert all(identifier.isascii() for identifier in sql_identifiers(sql))


def test_002_refreshes_every_copied_non_key_column_on_rerun():
    sql = MIGRATE_PATH.read_text(encoding="utf-8")

    assert "SELECT *" not in sql.upper()
    for target, definition in MIGRATIONS.items():
        target_sql, source_sql, update_sql = copied_statement(
            sql, target, definition["source"]
        )
        target_columns = tuple(sql_identifiers(target_sql))
        assert len(split_sql_list(source_sql)) == len(target_columns), target
        updated_columns = tuple(re.findall(r"`([^`]+)`\s*=\s*VALUES", update_sql))
        assert updated_columns == tuple(
            column for column in target_columns if column not in definition["keys"]
        ), target


def test_002_preflights_json_and_free_form_stats_before_copying():
    sql = MIGRATE_PATH.read_text(encoding="utf-8")
    first_copy = min(sql.index(f"INSERT INTO `{target}`") for target in MIGRATIONS)

    assert sql.index("CALL preflight_legacy_data();") < first_copy
    assert "JSON_VALID" in sql[:first_copy]
    assert "Invalid legacy JSON" in sql[:first_copy]
    assert "source_table" in sql[:first_copy]
    assert "source_column" in sql[:first_copy]
    assert "source_key" in sql[:first_copy]
    assert "Invalid broker statistic" in sql[:first_copy]
    assert "REGEXP_LIKE" in sql[:first_copy]
    assert "CAST(`市场宽度JSON` AS JSON)" in sql
    assert "CAST(`判定依据JSON` AS JSON)" in sql
    for source_table, source_column in (
        ("t_指数情绪周期_每日分析", "市场宽度JSON"),
        ("t_指数情绪周期_每日分析", "信号JSON"),
        ("t_指数情绪周期_每日分析", "最近走势JSON"),
        ("t_指数情绪周期_每日分析", "波动图JSON"),
        ("t_指数情绪周期_每日分析", "完整结果JSON"),
        ("t_热门板块情绪_每日分析", "判定依据JSON"),
    ):
        assert f"SELECT '{source_table}'" in sql[:first_copy]
        assert f"'{source_column}'" in sql[:first_copy]
    assert "LEFT(CONCAT(" in sql[:first_copy]
    assert "COALESCE(v_source_key, '<NULL>')" in sql[:first_copy]


def test_002_has_executable_parity_gates_for_all_16_mappings():
    sql = MIGRATE_PATH.read_text(encoding="utf-8")

    assert sql.count("CALL assert_mapping_parity(") == 16
    for target, definition in MIGRATIONS.items():
        call = parity_call(sql, target)
        assert f"FROM `{definition['source']}`" in call
        assert f"FROM `{target}`" in call
        assert call.count("COUNT(") >= 4, target
        assert "COUNT(DISTINCT" in call, target
        if definition.get("date"):
            assert "MIN(" in call and "MAX(" in call, target
        if definition.get("aggregate"):
            assert "SUM(" in call, target
            assert call.count("JSON_OBJECT(") == 2, target
        if definition.get("json"):
            assert "JSON_VALID" in call, target


def test_002_records_success_only_after_all_gates_succeed():
    sql = MIGRATE_PATH.read_text(encoding="utf-8")
    last_gate = sql.rindex("CALL assert_mapping_parity(")
    validation_record = sql.index("INSERT INTO `migration_validations`", last_gate)
    version_record = sql.index("INSERT INTO `schema_migrations` (`version`)")

    assert "DELETE FROM `migration_validations`" in sql[:last_gate]
    assert last_gate < validation_record < version_record
    assert "'002_parity_v1', 'succeeded'" in sql[validation_record:version_record]
    assert "'002_migrate_legacy_data'" in sql[version_record:]
    assert "ON DUPLICATE KEY UPDATE `applied_at`=`applied_at`" in sql[version_record:]


def test_002_has_durable_running_failed_and_succeeded_state_transitions():
    sql = MIGRATE_PATH.read_text(encoding="utf-8")

    assert "'002_parity_v1', 'running'" in sql
    assert "'002_parity_v1', 'failed'" in sql
    assert "GET DIAGNOSTICS" in sql
    assert "DECLARE EXIT HANDLER FOR SQLEXCEPTION" in sql


def test_003_checks_versions_and_successful_validation_before_any_drop():
    sql = DROP_PATH.read_text(encoding="utf-8")
    guard_call = sql.index("CALL guard_legacy_drop();")
    first_drop = sql.index("DROP TABLE IF EXISTS")

    assert guard_call < first_drop
    assert "001_create_english_schema" in sql[:guard_call]
    assert "002_migrate_legacy_data" in sql[:guard_call]
    assert "002_parity_v1" in sql[:guard_call]
    assert "succeeded" in sql[:guard_call]
    assert "SIGNAL SQLSTATE '45000'" in sql[:guard_call]
    assert "ON DUPLICATE KEY UPDATE `applied_at`=`applied_at`" in sql


def test_clean_initializer_is_self_contained_and_matches_001_ddl():
    init_sql = INIT_PATH.read_text(encoding="utf-8")
    create_sql = CREATE_PATH.read_text(encoding="utf-8")

    assert re.search(r"CREATE DATABASE IF NOT EXISTS `stock_trading_lab`", init_sql)
    assert re.search(r"USE `stock_trading_lab`", init_sql)
    assert "SOURCE " not in init_sql.upper()
    assert "003_drop_legacy_schema" not in init_sql
    assert "INSERT INTO `schema_migrations`" not in init_sql
    assert all(identifier.isascii() for identifier in sql_identifiers(init_sql))
    assert set(re.findall(r"CREATE TABLE IF NOT EXISTS `([^`]+)`", init_sql)) == set(
        re.findall(r"CREATE TABLE IF NOT EXISTS `([^`]+)`", create_sql)
    )
    for table in set(MIGRATIONS) | {
        "schema_migrations",
        "migration_validations",
        "fund_flow_snapshots",
        "fund_flow_records",
        "strategy_definitions",
        "strategy_pick_snapshots",
        "strategy_pick_stocks",
        "strategy_pick_events",
    }:
        init_ddl = re.search(
            rf"CREATE TABLE IF NOT EXISTS `{table}` \((.*?)\) ENGINE=InnoDB",
            init_sql,
            re.DOTALL,
        )
        migration_ddl = re.search(
            rf"CREATE TABLE IF NOT EXISTS `{table}` \((.*?)\) ENGINE=InnoDB",
            create_sql,
            re.DOTALL,
        )
        assert init_ddl and migration_ddl
        assert init_ddl.group(1) == migration_ddl.group(1), table


def test_historical_initializer_cannot_be_mistaken_for_current_setup():
    assert not OLD_INIT_PATH.exists()
    legacy_sql = LEGACY_INIT_PATH.read_text(encoding="utf-8")
    warning = legacy_sql[:1000].upper()

    assert "LEGACY" in warning
    assert "DO NOT USE" in warning
    assert "STOCK_TRADING_LAB_V2.SQL" in warning


def test_mysql_compose_uses_the_clean_database_and_optional_initializer():
    compose = (ROOT / "init" / "docker" / "mysql" / "docker-compose.yml").read_text(
        encoding="utf-8"
    )

    assert "MYSQL_DATABASE: stock_trading_lab" in compose
    assert "stock_trading_lab_v2.sql:/docker-entrypoint-initdb.d/001-stock-trading-lab.sql:ro" in compose
