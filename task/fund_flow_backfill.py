import argparse
import datetime as dt
import importlib
import json
import math
import time

from stock_lab.config import Settings
from stock_lab.infrastructure.cache import create_redis_client
from stock_lab.infrastructure.database import create_database_client
from stock_lab.modules.fund_flow.contracts import normalize_net_inflow_100m
from stock_lab.modules.fund_flow.mysql_repository import FundFlowMySQLRepository
from stock_lab.modules.fund_flow.repository import FundFlowRepository


FLOW_TYPES = {
    "industry": {"sector_type": "行业资金流"},
    "concept": {"sector_type": "概念资金流"},
}


class FundFlowSourceError(RuntimeError):
    pass


class AkShareFundFlowSource:
    def __init__(self, akshare_module=None):
        self._akshare_module = akshare_module

    @property
    def akshare(self):
        if self._akshare_module is None:
            self._akshare_module = importlib.import_module("akshare")
        return self._akshare_module

    def list_boards(self, flow_type):
        try:
            sector_type = FLOW_TYPES[flow_type]["sector_type"]
        except KeyError as error:
            raise ValueError(f"unsupported flow type: {flow_type}") from error
        frame = self.akshare.stock_sector_fund_flow_rank(
            indicator="今日",
            sector_type=sector_type,
        )
        records = _frame_records(frame, f"{flow_type} board rank")
        boards = []
        for row in records:
            board_name = _first_value(row, "板块名称", "名称", "name", "board_name")
            if not board_name:
                continue
            boards.append({
                "board_code": str(_first_value(row, "板块代码", "代码", "f12", "code", "board_code") or ""),
                "board_name": str(board_name).strip(),
                "leader": str(_first_value(
                    row,
                    "龙头",
                    "领涨股",
                    "今日主力净流入最大股",
                    "f204",
                    "leader",
                ) or "").strip(),
            })
        if not boards:
            raise FundFlowSourceError(f"AkShare returned no {flow_type} board names")
        return boards

    def board_history(self, board_name):
        return self.akshare.stock_sector_fund_flow_hist(symbol=board_name)


def _frame_records(frame, source_name):
    if frame is None or getattr(frame, "empty", True):
        raise FundFlowSourceError(f"AkShare returned no {source_name} data")
    return frame.where(frame.notna(), None).to_dict("records")


def _first_value(row, *columns):
    for column in columns:
        value = row.get(column)
        if value is not None and not _is_nan(value) and str(value).strip():
            return value
    return None


def _is_nan(value):
    try:
        return math.isnan(value)
    except (TypeError, ValueError):
        return False


def _date_int(value):
    if isinstance(value, (dt.datetime, dt.date)):
        return int(value.strftime("%Y%m%d"))
    text = str(value or "").strip().replace("-", "").replace("/", "")[:8]
    if len(text) != 8 or not text.isdigit():
        return 0
    return int(text)


def _amount_100m(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(amount):
        return None
    return round(amount / 100_000_000, 4)


def normalize_history_rows(frame, board, flow_type):
    records = _frame_records(frame, f"{board['board_name']} history")
    rows = []
    for source_row in records:
        trade_date = _date_int(_first_value(source_row, "trade_date", "日期", "date", "f51"))
        amount = _amount_100m(_first_value(
            source_row,
            "net_inflow_yuan",
            "主力净流入-净额",
            "今日主力净流入-净额",
            "f62",
            "net_inflow",
        ))
        if not trade_date or amount is None:
            continue
        rows.append({
            "trade_date": trade_date,
            "board_code": board.get("board_code", ""),
            "board_name": board["board_name"],
            "leader": board.get("leader", ""),
            "net_inflow_100m": amount,
            "flow_type": flow_type,
        })
    if not rows:
        raise FundFlowSourceError(
            f"AkShare returned no usable history for {board['board_name']}"
        )
    return rows


def _call_with_retry(operation, retries, retry_delay, sleep):
    for attempt in range(retries + 1):
        try:
            return operation()
        except Exception:
            if attempt >= retries:
                raise
            if retry_delay > 0:
                sleep(retry_delay)
    raise AssertionError("unreachable")


def collect_fund_flow_records(
    source,
    retries=2,
    retry_delay=1.0,
    rate_delay=0.2,
    sleep=time.sleep,
):
    records_by_type = {flow_type: {} for flow_type in FLOW_TYPES}
    request_count = 0

    def request(operation):
        nonlocal request_count
        if request_count and rate_delay > 0:
            sleep(rate_delay)
        result = _call_with_retry(operation, retries, retry_delay, sleep)
        request_count += 1
        return result

    for flow_type in FLOW_TYPES:
        boards = request(
            lambda flow_type=flow_type: source.list_boards(flow_type)
        )
        for board in boards:
            frame = request(
                lambda board_name=board["board_name"]: source.board_history(board_name)
            )
            for row in normalize_history_rows(frame, board, flow_type):
                records_by_type[flow_type].setdefault(row["trade_date"], []).append(row)
    return records_by_type


def _default_trading_dates():
    from task.data_sources import 交易日期列表

    return 交易日期列表(400)


def _default_writer(settings=None, connection_factory=None, redis_factory=None):
    settings = settings or Settings.from_env()
    if connection_factory is None:
        database = create_database_client(settings)
        connection_factory = lambda: database.resources.get_pool().get_connection()
    redis_client = (redis_factory or create_redis_client)(settings)
    mysql_repository = FundFlowMySQLRepository(connection_factory)
    redis_repository = FundFlowRepository(redis_client)

    def write(flow_type, trade_date, snapshot_time, rows):
        records = [
            {
                "board_code": str(row.get("board_code", "")),
                "board_name": str(row.get("board_name", "")),
                "leader": str(row.get("leader", "")),
                "net_inflow_100m": float(normalize_net_inflow_100m(
                    row.get("net_inflow_100m"), row.get("source_unit", "100m")
                )),
                "time": snapshot_time,
            }
            for row in sorted(rows, key=lambda item: (item.get("board_name", ""), item.get("board_code", "")))
        ]
        mysql_repository.save_snapshot(flow_type, trade_date, snapshot_time, records)
        redis_repository.save_history(flow_type, trade_date, records)

    return write


def backfill_fund_flow(
    trading_dates=None,
    source=None,
    now=None,
    days=365,
    retries=2,
    retry_delay=1.0,
    rate_delay=0.2,
    sleep=time.sleep,
    writer=None,
):
    today = now.date() if isinstance(now, dt.datetime) else (now or dt.date.today())
    cutoff = today - dt.timedelta(days=max(int(days), 1))
    cutoff_int = int(cutoff.strftime("%Y%m%d"))
    today_int = int(today.strftime("%Y%m%d"))
    available_dates = trading_dates if trading_dates is not None else _default_trading_dates()
    target_dates = sorted({
        _date_int(value)
        for value in available_dates
        if cutoff_int <= _date_int(value) <= today_int
    }, reverse=True)

    source = source or AkShareFundFlowSource()
    writer = writer or _default_writer()
    try:
        records_by_type = collect_fund_flow_records(
            source,
            retries=retries,
            retry_delay=retry_delay,
            rate_delay=rate_delay,
            sleep=sleep,
        )
    except Exception as error:
        return {
            "status": "failed",
            "processed_dates": [],
            "failed_dates": target_dates,
            "errors": [{"trade_date": date, "error": str(error)} for date in target_dates],
        }

    processed_dates = []
    errors = []
    for trade_date in target_dates:
        missing_types = [
            flow_type for flow_type in FLOW_TYPES
            if not records_by_type[flow_type].get(trade_date)
        ]
        if missing_types:
            errors.append({
                "trade_date": trade_date,
                "error": f"missing AkShare history: {', '.join(missing_types)}",
            })
            continue
        try:
            for flow_type in FLOW_TYPES:
                writer(
                    flow_type,
                    str(trade_date),
                    "15:00:00",
                    records_by_type[flow_type][trade_date],
                )
        except Exception as error:
            errors.append({"trade_date": trade_date, "error": str(error)})
            continue
        processed_dates.append(trade_date)

    return {
        "status": "success" if not errors else "failed",
        "processed_dates": processed_dates,
        "failed_dates": [item["trade_date"] for item in errors],
        "errors": errors,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Backfill AkShare board fund-flow history")
    parser.add_argument("--days", type=int, default=365, help="calendar-day lookback (default: 365)")
    parser.add_argument("--retries", type=int, default=2, help="retries per AkShare request")
    parser.add_argument("--retry-delay", type=float, default=1.0, help="seconds between retries")
    parser.add_argument("--rate-delay", type=float, default=0.2, help="seconds between AkShare requests")
    args = parser.parse_args(argv)
    result = backfill_fund_flow(
        days=args.days,
        retries=max(args.retries, 0),
        retry_delay=max(args.retry_delay, 0),
        rate_delay=max(args.rate_delay, 0),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
