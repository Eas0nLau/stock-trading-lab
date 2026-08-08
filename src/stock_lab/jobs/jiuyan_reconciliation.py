import argparse
import json
from dataclasses import asdict, dataclass, field

from sqlalchemy import text

from stock_lab.infrastructure.database import create_database_client


class DuplicateJiuyanSourceKeys(RuntimeError):
    pass


@dataclass
class JiuyanReconciliationReport:
    source_count: int = 0
    target_count: int = 0
    missing_count: int = 0
    written_count: int = 0
    missing_ids: tuple[str, ...] = ()
    missing_dates: tuple[int, ...] = ()
    duplicate_source_ids: tuple[str, ...] = ()
    recalculated_dates: list[int] = field(default_factory=list)
    skipped_dates: list[dict] = field(default_factory=list)


_SUMMARY_SQL = """
SELECT
    (SELECT COUNT(*) FROM `t_韭研公社异动解析`) AS `source_count`,
    (SELECT COUNT(*) FROM `jiuyan_actions`) AS `target_count`
"""

_DUPLICATE_SQL = """
SELECT `data_id`, COUNT(*) AS `row_count`
FROM `t_韭研公社异动解析`
GROUP BY `data_id`
HAVING COUNT(*) > 1
"""

_MISSING_SQL = """
SELECT
    `source`.`data_id`, `source`.`date`, `source`.`板块`, `source`.`板块个股数量`,
    `source`.`股票代码`, `source`.`股票名称`, `source`.`code`, `source`.`涨停时间`,
    `source`.`几天几板`, `source`.`涨幅`, `source`.`涨停解析`
FROM `t_韭研公社异动解析` AS `source`
WHERE NOT EXISTS (
    SELECT 1
    FROM `jiuyan_actions` AS `target`
    WHERE CONVERT(`target`.`data_id` USING utf8mb4) COLLATE utf8mb4_bin
        = CONVERT(`source`.`data_id` USING utf8mb4) COLLATE utf8mb4_bin
)
ORDER BY `source`.`date`, `source`.`data_id`
"""

_INSERT_SQL = text("""
INSERT INTO `jiuyan_actions` (
    `data_id`, `trade_date`, `board_name`, `board_stock_count`, `stock_code`,
    `stock_name`, `source_code`, `limit_up_at`, `board_streak`, `change_pct`,
    `limit_up_reason`
) VALUES (
    :data_id, :trade_date, :board_name, :board_stock_count, :stock_code,
    :stock_name, :source_code, :limit_up_at, :board_streak, :change_pct,
    :limit_up_reason
)
ON DUPLICATE KEY UPDATE `data_id` = `data_id`
""")

_TRADING_DATES_SQL = """
SELECT DISTINCT `trade_date`
FROM `index_daily`
ORDER BY `trade_date`
"""

_JIUYAN_DATES_SQL = """
SELECT DISTINCT `trade_date`
FROM `jiuyan_actions`
ORDER BY `trade_date`
"""

_CANONICAL_VALIDATION_SQL = """
SELECT
    (SELECT COUNT(*) FROM (
        SELECT `data_id`
        FROM `jiuyan_actions`
        GROUP BY `data_id`
        HAVING COUNT(*) > 1
    ) AS `duplicates`) AS `duplicate_target_ids`,
    (SELECT COUNT(*)
     FROM `hot_board_emotion_daily`
     WHERE `decision_reasons_json` IS NOT NULL
       AND NOT JSON_VALID(`decision_reasons_json`)) AS `invalid_emotion_json`
"""


def reconcile_jiuyan_data(*, database, write=False, recalculate=False):
    if recalculate and not write:
        raise ValueError("recalculate requires write=True")

    summary = (database.query(_SUMMARY_SQL, fetch=True) or [{}])[0]
    duplicate_rows = database.query(_DUPLICATE_SQL, fetch=True) or []
    duplicate_ids = tuple(str(row["data_id"]) for row in duplicate_rows)
    if duplicate_ids:
        raise DuplicateJiuyanSourceKeys(
            "Duplicate Jiuyan source data_id values: " + ", ".join(duplicate_ids)
        )

    missing_rows = database.query(_MISSING_SQL, fetch=True) or []
    canonical_rows = [_canonical_row(row) for row in missing_rows]
    written_count = 0
    if write and canonical_rows:
        with database.engine.begin() as connection:
            connection.execute(_INSERT_SQL, canonical_rows)
        written_count = len(canonical_rows)

    missing_dates = tuple(sorted({int(row["trade_date"]) for row in canonical_rows}))
    return JiuyanReconciliationReport(
        source_count=int(summary.get("source_count") or 0),
        target_count=int(summary.get("target_count") or 0),
        missing_count=len(canonical_rows),
        written_count=written_count,
        missing_ids=tuple(str(row["data_id"]) for row in canonical_rows),
        missing_dates=missing_dates,
        duplicate_source_ids=duplicate_ids,
    )


def _canonical_row(row):
    return {
        "data_id": row["data_id"],
        "trade_date": int(row["date"]),
        "board_name": row["板块"],
        "board_stock_count": int(row["板块个股数量"] or 0),
        "stock_code": str(row["股票代码"]).zfill(6),
        "stock_name": row.get("股票名称"),
        "source_code": row.get("code"),
        "limit_up_at": row.get("涨停时间"),
        "board_streak": row.get("几天几板"),
        "change_pct": row.get("涨幅"),
        "limit_up_reason": row.get("涨停解析"),
    }


def recalculate_complete_hot_board_emotion(*, database, emotion_runner=None, report=None):
    report = report or JiuyanReconciliationReport()
    trading_dates = _date_values(database.query(_TRADING_DATES_SQL, fetch=True))
    jiuyan_dates = set(_date_values(database.query(_JIUYAN_DATES_SQL, fetch=True)))
    if emotion_runner is None:
        emotion_runner = _default_emotion_runner(database)

    for previous_date, trade_date in zip(trading_dates, trading_dates[1:]):
        if previous_date not in jiuyan_dates or trade_date not in jiuyan_dates:
            report.skipped_dates.append({
                "trade_date": trade_date,
                "reason": "missing Jiuyan action rows",
            })
            continue
        emotion_runner(trade_date, previous_date)
        report.recalculated_dates.append(trade_date)
    return report


def _date_values(rows):
    return [int(row["trade_date"]) for row in rows or []]


def _default_emotion_runner(database):
    from stock_lab.modules.emotion.jobs import run_hot_board_emotion_job, write_tables
    from stock_lab.modules.emotion.repository import EmotionRepository
    from stock_lab.modules.market_data.repository import MarketDataRepository

    market_data = MarketDataRepository(database.query, database.engine)
    repository = EmotionRepository(database.query, market_data=market_data)
    writer = lambda tables: write_tables(database.engine, tables)
    return lambda trade_date, sample_trade_date: run_hot_board_emotion_job(
        trade_date,
        sample_trade_date,
        repository=repository,
        writer=writer,
    )


def verify_jiuyan_parity(database):
    missing_rows = database.query(_MISSING_SQL, fetch=True) or []
    validation = (database.query(_CANONICAL_VALIDATION_SQL, fetch=True) or [{}])[0]
    duplicate_count = int(validation.get("duplicate_target_ids") or 0)
    invalid_json_count = int(validation.get("invalid_emotion_json") or 0)
    if duplicate_count:
        raise RuntimeError(f"jiuyan_actions contains {duplicate_count} duplicate data_id values")
    if invalid_json_count:
        raise RuntimeError(
            f"hot_board_emotion_daily contains {invalid_json_count} invalid decision_reasons_json values"
        )
    return [str(row["data_id"]) for row in missing_rows]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reconcile legacy Jiuyan rows into jiuyan_actions")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="report differences without writing")
    mode.add_argument("--write", action="store_true", help="write missing rows")
    parser.add_argument("--recalculate", action="store_true", help="recalculate hot-board emotion")
    args = parser.parse_args(argv)
    if args.recalculate and not args.write:
        parser.error("--recalculate requires --write")
    database = create_database_client()
    report = reconcile_jiuyan_data(
        database=database,
        write=args.write,
        recalculate=args.recalculate,
    )
    if args.recalculate:
        report = recalculate_complete_hot_board_emotion(database=database, report=report)
    if args.write:
        remaining_ids = verify_jiuyan_parity(database)
        if remaining_ids:
            raise RuntimeError(
                "Jiuyan reconciliation left missing data_id values: " + ", ".join(remaining_ids[:10])
            )
    print(json.dumps(asdict(report), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
