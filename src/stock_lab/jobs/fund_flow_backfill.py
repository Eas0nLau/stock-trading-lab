import datetime as dt
import importlib
import math
import time
from typing import Protocol

from stock_lab.config import Settings
from stock_lab.infrastructure.cache import create_redis_client
from stock_lab.infrastructure.database import create_database_client
from stock_lab.modules.fund_flow.contracts import normalize_net_inflow_100m, translate_legacy_fund_flow
from stock_lab.modules.fund_flow.mysql_repository import FundFlowMySQLRepository
from stock_lab.modules.fund_flow.repository import FundFlowRepository

LEGACY_REDIS_MIGRATION_KEY = "fund_flow:v1:legacy-normalized"
FLOW_TYPES = ("industry", "concept")
DAYKLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
DAYKLINE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://data.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
}


class FundFlowSourceError(RuntimeError):
    pass


class FundFlowDailySource(Protocol):
    def fetch(self, flow_type: str, trade_date: int) -> list[dict]:
        ...


class ConfiguredFundFlowDailySource:
    """Explicit production boundary; deployments must provide the historical adapter."""

    def __init__(self, fetcher=None):
        self.fetcher = fetcher

    def fetch(self, flow_type, trade_date):
        if self.fetcher is None:
            raise RuntimeError("No fund-flow historical source is configured")
        return self.fetcher(flow_type, trade_date)


class AkShareFundFlowSource:
    def __init__(self, akshare_module=None):
        self._akshare_module = akshare_module

    @property
    def akshare(self):
        if self._akshare_module is None:
            self._akshare_module = importlib.import_module("akshare")
        return self._akshare_module

    def list_boards(self, flow_type):
        sector_type = "行业资金流" if flow_type == "industry" else "概念资金流"
        frame = self.akshare.stock_sector_fund_flow_rank(indicator="今日", sector_type=sector_type)
        records = _frame_records(frame)
        boards = []
        for row in records:
            name = _first_value(row, "板块名称", "名称", "name", "board_name")
            if name:
                boards.append({
                    "board_code": str(_first_value(row, "板块代码", "代码", "f12", "code", "board_code") or ""),
                    "board_name": str(name).strip(),
                    "leader": str(_first_value(row, "龙头", "领涨股", "今日主力净流入最大股", "f204", "leader") or "").strip(),
                })
        if not boards:
            raise FundFlowSourceError(f"AkShare returned no {flow_type} board names")
        return boards

    def board_history(self, board_name):
        return self.akshare.stock_sector_fund_flow_hist(symbol=board_name)


def _frame_records(frame):
    if frame is None or getattr(frame, "empty", True):
        raise FundFlowSourceError("source returned no data")
    return frame.where(frame.notna(), None).to_dict("records")


def _first_value(row, *columns):
    for column in columns:
        value = row.get(column)
        if value is not None and str(value).strip() and not (isinstance(value, float) and math.isnan(value)):
            return value
    return None


def normalize_history_rows(frame, board, flow_type):
    rows = []
    for row in _frame_records(frame):
        trade_date = _date_int(_first_value(row, "trade_date", "日期", "date", "f51"))
        value = _first_value(row, "net_inflow_yuan", "主力净流入-净额", "今日主力净流入-净额", "f62", "net_inflow")
        try:
            amount = float(value) / 100_000_000
        except (TypeError, ValueError):
            amount = None
        if trade_date and amount is not None and math.isfinite(amount):
            rows.append({"trade_date": trade_date, **board, "net_inflow_100m": amount, "flow_type": flow_type})
    if not rows:
        raise FundFlowSourceError(f"source returned no usable history for {board['board_name']}")
    return rows


class EastMoneyFundFlowSource:
    """Official historical source backed by the accessible EastMoney endpoint."""

    def __init__(self, mysql_repository, session=None, timeout=20):
        self.mysql_repository = mysql_repository
        self._session = session
        self.timeout = timeout
        self._boards = {}

    @property
    def session(self):
        if self._session is None:
            requests = importlib.import_module("requests")
            self._session = requests.Session()
        return self._session

    def list_boards(self, flow_type):
        try:
            boards = self.mysql_repository.board_catalog(flow_type)
        except AttributeError:
            boards = self.mysql_repository.list_boards(flow_type)
        if not boards:
            raise RuntimeError(f"no MySQL board catalog for {flow_type}")
        for board in boards:
            self._boards[(flow_type, board["board_name"])] = dict(board)
        return boards

    def board_history(self, board_name, flow_type=None):
        if isinstance(board_name, dict):
            board = board_name
            flow_type = flow_type or board.get("flow_type") or "industry"
        else:
            board = self._boards.get((flow_type, board_name)) if flow_type else None
            if board is None:
                matches = [item for (item_flow, item_name), item in self._boards.items() if item_name == board_name]
                board = matches[0] if len(matches) == 1 else None
        if board is None:
            raise ValueError(f"unknown board: {board_name}")
        response = self.session.get(
            DAYKLINE_URL,
            params={
                "secid": f"90.{board['board_code']}",
                "klt": "101",
                "lmt": "0",
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            },
            headers=DAYKLINE_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return parse_daykline_response(response.json(), board, flow_type or "industry")


def parse_daykline_response(payload, board, flow_type):
    try:
        klines = payload["data"]["klines"]
    except (KeyError, TypeError):
        raise ValueError("EastMoney response missing data.klines")
    if not isinstance(klines, list):
        raise ValueError("EastMoney response klines is not a list")
    rows = []
    for kline in klines:
        fields = str(kline).split(",") if isinstance(kline, str) else kline
        if not isinstance(fields, (list, tuple)) or len(fields) < 6:
            continue
        trade_date = _date_int(fields[0])
        try:
            amount = float(fields[1]) / 100_000_000
        except (TypeError, ValueError):
            continue
        if not trade_date or not math.isfinite(amount):
            continue
        rows.append({
            "trade_date": trade_date,
            "board_code": str(board.get("board_code", "")),
            "board_name": str(board.get("board_name", "")),
            "leader": str(board.get("leader", "")),
            "net_inflow_100m": amount,
            "flow_type": flow_type,
        })
    if not rows:
        raise ValueError("EastMoney response contained no usable klines")
    return rows


def _date_int(value):
    text = str(value or "").strip().replace("-", "").replace("/", "")[:8]
    return int(text) if len(text) == 8 and text.isdigit() else 0


def _call_with_retry(operation, retries, retry_delay, sleep):
    for attempt in range(retries + 1):
        try:
            return operation()
        except Exception:
            if attempt >= retries:
                raise
            if retry_delay > 0:
                sleep(retry_delay)


def collect_fund_flow_records(source, retries=2, retry_delay=1.0, rate_delay=0.2, sleep=time.sleep):
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
        boards = request(lambda flow_type=flow_type: source.list_boards(flow_type))
        for board in boards:
            if isinstance(source, EastMoneyFundFlowSource):
                history = request(lambda board=board, flow_type=flow_type: source.board_history(board["board_name"], flow_type))
            else:
                history = request(lambda board=board: source.board_history(board["board_name"]))
            if hasattr(history, "to_dict"):
                history = normalize_history_rows(history, board, flow_type)
            for row in history:
                records_by_type[flow_type].setdefault(row["trade_date"], []).append(row)
    return records_by_type


def _default_trading_dates():
    from stock_lab.modules.market_data.collectors import trading_dates

    return trading_dates(400)


def _default_repositories(settings=None, connection_factory=None, redis_factory=None):
    settings = settings or Settings.from_env()
    if connection_factory is None:
        database = create_database_client(settings)
        connection_factory = lambda: database.resources.get_pool().get_connection()
    mysql_repository = FundFlowMySQLRepository(connection_factory)
    redis_repository = FundFlowRepository((redis_factory or create_redis_client)(settings))
    return mysql_repository, redis_repository


def _default_writer(mysql_repository, redis_repository):
    def write(flow_type, trade_date, snapshot_time, rows):
        records = [
            {
                "board_code": str(row.get("board_code", "")),
                "board_name": str(row.get("board_name", "")),
                "leader": str(row.get("leader", "")),
                "net_inflow_100m": float(normalize_net_inflow_100m(row.get("net_inflow_100m"), row.get("source_unit", "100m"))),
                "time": snapshot_time,
            }
            for row in sorted(rows, key=lambda item: (item.get("board_name", ""), item.get("board_code", "")))
        ]
        mysql_repository.save_snapshot(flow_type, trade_date, snapshot_time, records)
        redis_repository.save_history(flow_type, trade_date, records)
    return write


class _NoopMySQLRepository:
    def has_snapshot(self, flow_type, trade_date):
        return False


def _backfill_legacy_fund_flow(start_date, end_date, source, mysql_repository, redis_repository, trading_dates):
    dates = trading_dates(start_date, end_date)
    result = {"saved": [], "skipped": [], "failed": []}
    for trade_date in sorted(dates, reverse=True):
        for flow_type in ("industry", "concept"):
            if mysql_repository.has_snapshot(flow_type, trade_date):
                result["skipped"].append({"flow_type": flow_type, "trade_date": trade_date})
                continue
            try:
                records = source.fetch(flow_type, trade_date)
                if not records:
                    raise ValueError("source returned no records")
                records = translate_legacy_fund_flow(records)
                records = [
                    {
                        **record,
                        "net_inflow_100m": float(normalize_net_inflow_100m(record.get("net_inflow_100m"), record.get("source_unit", "100m"))),
                    }
                    for record in records
                ]
                collected_at = records[0].get("collected_at") or records[0].get("time") or dt.datetime.min.strftime("%H:%M:%S")
                mysql_repository.save_snapshot(flow_type, trade_date, collected_at, records)
                redis_repository.save_history(flow_type, trade_date, [records])
                result["saved"].append({"flow_type": flow_type, "trade_date": trade_date})
            except Exception as error:
                result["failed"].append({"flow_type": flow_type, "trade_date": trade_date, "error": str(error)})
    return result


def backfill_fund_flow(*args, **kwargs):
    """Canonical backfill entry point with compatibility for the old job contract."""
    if len(args) == 6 and not kwargs:
        return _backfill_legacy_fund_flow(*args)
    return run_backfill(*args, **kwargs)


def run_backfill(trading_dates=None, source=None, now=None, days=365, retries=2, retry_delay=1.0, rate_delay=0.2, sleep=time.sleep, writer=None, mysql_repository=None, redis_repository=None):
    today = now.date() if isinstance(now, dt.datetime) else (now or dt.date.today())
    cutoff = today - dt.timedelta(days=max(int(days), 1))
    dates = sorted({
        _date_int(value) for value in (trading_dates if trading_dates is not None else _default_trading_dates())
        if int(cutoff.strftime("%Y%m%d")) <= _date_int(value) <= int(today.strftime("%Y%m%d"))
    }, reverse=True)
    if mysql_repository is None and writer is not None and source is not None:
        mysql_repository = _NoopMySQLRepository()
    if mysql_repository is None or (redis_repository is None and writer is None):
        mysql_repository, redis_repository = _default_repositories()
    source = source or EastMoneyFundFlowSource(mysql_repository)
    writer = writer or _default_writer(mysql_repository, redis_repository)
    try:
        records = collect_fund_flow_records(source, retries, retry_delay, rate_delay, sleep)
    except Exception as error:
        return {"status": "failed", "processed_dates": [], "failed_dates": dates, "errors": [{"trade_date": date, "error": str(error)} for date in dates]}
    processed, errors = [], []
    for trade_date in dates:
        pending = [flow_type for flow_type in FLOW_TYPES if not mysql_repository.has_snapshot(flow_type, trade_date)]
        missing = [flow_type for flow_type in pending if not records[flow_type].get(trade_date)]
        if missing:
            errors.append({"trade_date": trade_date, "error": f"missing source history: {', '.join(missing)}"})
            continue
        try:
            for flow_type in pending:
                writer(flow_type, str(trade_date), "15:00:00", records[flow_type][trade_date])
            processed.append(trade_date)
        except Exception as error:
            errors.append({"trade_date": trade_date, "error": str(error)})
    return {"status": "success" if not errors else "failed", "processed_dates": processed, "failed_dates": [item["trade_date"] for item in errors], "errors": errors}


def migrate_legacy_redis(redis_repository, mysql_repository, flow_types=("industry", "concept")):
    """Normalize existing V1 Redis snapshots into MySQL and rebuild their cache."""
    if redis_repository.redis.get(LEGACY_REDIS_MIGRATION_KEY):
        return {"saved": [], "failed": [], "skipped": True}
    result = {"saved": [], "failed": []}
    for flow_type in flow_types:
        for trade_date in redis_repository.dates(flow_type):
            try:
                is_canonical = getattr(redis_repository, "is_canonical_history", None)
                if callable(is_canonical) and is_canonical(flow_type, trade_date):
                    continue
                history = translate_legacy_fund_flow(redis_repository.history(flow_type, trade_date))
                if not isinstance(history, list):
                    raise ValueError("legacy history is not a snapshot list")
                canonical_history = []
                for snapshot in history:
                    canonical = []
                    for record in snapshot:
                        item = dict(record)
                        item["net_inflow_100m"] = float(normalize_net_inflow_100m(item.get("net_inflow_100m"), "wan"))
                        canonical.append(item)
                    if canonical:
                        mysql_repository.save_snapshot(flow_type, trade_date, canonical[0].get("time", "00:00:00"), canonical)
                        canonical_history.append(canonical)
                redis_repository.replace_history(flow_type, trade_date, canonical_history)
                result["saved"].append({"flow_type": flow_type, "trade_date": trade_date})
            except Exception as error:
                result["failed"].append({"flow_type": flow_type, "trade_date": trade_date, "error": str(error)})
    if not result["failed"]:
        redis_repository.redis.set(LEGACY_REDIS_MIGRATION_KEY, "1")
    return result
