import json
import re
import sqlite3
from pathlib import Path

import pandas as pd

from stock_lab.modules.market_data.helpers import normalize_symbol, normalize_ts_code
from stock_lab.modules.dragon_tiger.repository import HISTORY_COLUMNS, LISTING_COLUMNS
from stock_lab.modules.dragon_tiger.repository import DragonTigerRepository
from stock_lab.modules.market_data.repository import MarketDataRepository

from .context import ResearchContext, ResearchExecutionError
from .data import ResearchData


DAILY_COLUMNS = (
    "data_id", "ts_code", "trade_date", "open_price", "high_price", "low_price",
    "close_price", "previous_close", "change_amount", "change_pct", "volume",
    "turnover", "total_market_value", "circulating_market_value", "free_float_shares",
    "free_float_market_value", "stock_name", "dde_net_amount",
)
TABLE_COLUMNS = {
    "securities": ("ts_code", "symbol", "name", "area", "industry", "market", "list_date", "list_status"),
    "daily_quotes": DAILY_COLUMNS,
    "index_daily": ("trade_date", "open_price", "close_price", "high_price", "low_price", "volume", "turnover", "change_pct"),
    "kdj_indicators": ("data_id", "ts_code", "trade_date", "k_value", "d_value", "j_value"),
    "intraday_bars_5m": ("data_id", "trade_date", "trade_time", "stock_code", "open_price", "high_price", "low_price", "close_price", "volume", "turnover", "adjustment_flag"),
    "dragon_tiger": LISTING_COLUMNS,
    "broker_listing_history": HISTORY_COLUMNS,
    "jiuyan_actions": ("data_id", "trade_date", "board_name", "board_stock_count", "stock_code", "stock_name", "source_code", "limit_up_at", "board_streak", "change_pct", "limit_up_reason"),
}


class OfflineQueryProvider:
    is_offline = True

    def __init__(self, tables):
        self.cache = FixtureRedis(tables.get("redis_lists", {}))
        self.engine = sqlite3.connect(":memory:")
        self.engine.row_factory = sqlite3.Row
        self.engine.create_function("SUBSTRING_INDEX", 3, self._substring_index)
        self.engine.create_function("LPAD", 3, lambda value, size, fill: str(value).rjust(int(size), str(fill)))
        self.engine.create_function("REGEXP", 2, lambda pattern, value: bool(re.search(pattern, str(value or ""))))
        for table, columns in TABLE_COLUMNS.items():
            frame = pd.DataFrame(tables.get(table, []), columns=columns)
            frame.to_sql(table, self.engine, index=False, if_exists="replace")

    @staticmethod
    def _substring_index(value, delimiter, count):
        parts = str(value or "").split(str(delimiter))
        return str(delimiter).join(parts[: int(count)])

    def query(self, sql=None, params=None, fetch=False, commit=False):
        sql = str(sql).replace("%s", "?")
        try:
            cursor = self.engine.execute(sql, tuple(params or ()))
        except sqlite3.Error as error:
            raise ResearchExecutionError(f"offline SQL failed: {error}; SQL: {sql}") from error
        if fetch:
            return [dict(row) for row in cursor.fetchall()]
        if commit:
            self.engine.commit()
            return cursor.rowcount
        return None

    def read_sql(self, sql, params=None):
        sql = str(sql).replace("%s", "?")
        try:
            return pd.read_sql(sql, self.engine, params=tuple(params or ()))
        except Exception as error:
            raise ResearchExecutionError(f"offline SQL failed: {error}; SQL: {sql}") from error


class FixtureRedis:
    def __init__(self, lists):
        self._lists = {str(key): list(values) for key, values in lists.items()}

    def get(self, key):
        return None

    def lrange(self, key, start, end):
        values = self._lists.get(str(key), [])
        stop = None if int(end) == -1 else int(end) + 1
        return values[int(start):stop]


class FixtureMarketDataRepository:
    def __init__(self, fixture):
        self._securities = fixture.get("securities", [])
        self._daily_quotes = fixture.get("daily_quotes", [])
        self._index_daily = fixture.get("index_daily", [])
        self._kdj = fixture.get("kdj_indicators", [])
        self._intraday = fixture.get("intraday_bars_5m", [])

    def securities(self, market=None):
        rows = self._securities
        return [dict(row) for row in rows if market is None or row.get("market") == market]

    def security_codes(self, market=None):
        return [row["ts_code"] for row in self.securities(market)]

    def daily_quotes(self, stock_codes=None, start_date=None, end_date=None):
        symbols = {normalize_symbol(code) for code in stock_codes or []}
        return [
            dict(row) for row in self._daily_quotes
            if (not symbols or normalize_symbol(row.get("ts_code")) in symbols)
            and (start_date is None or int(row["trade_date"]) >= int(start_date))
            and (end_date is None or int(row["trade_date"]) <= int(end_date))
        ]

    def index_daily(self, start_date=None, end_date=None, limit=None):
        rows = [
            dict(row) for row in self._index_daily
            if (start_date is None or int(row["trade_date"]) >= int(start_date))
            and (end_date is None or int(row["trade_date"]) <= int(end_date))
        ]
        return rows[-int(limit):] if limit is not None else rows

    def trading_dates(self, limit=160):
        dates = sorted({int(row["trade_date"]) for row in self._daily_quotes})
        return dates[-int(limit):]

    def kdj_indicators(self, stock_codes=None, start_date=None, end_date=None):
        return [dict(row) for row in self._kdj]

    def intraday_bars_5m(self, trade_date=None, stock_code=None):
        return [dict(row) for row in self._intraday]


class FixtureDragonTigerRepository:
    def __init__(self, fixture):
        self._fixture = fixture

    def listings(self, **filters):
        return [dict(row) for row in self._fixture.get("dragon_tiger", [])]

    def broker_history(self, **filters):
        return [dict(row) for row in self._fixture.get("broker_listing_history", [])]


class OfflineResearchProvider:
    def __init__(self, fixture):
        self.fixture = _normalize_fixture(fixture)
        self.query_provider = OfflineQueryProvider(self.fixture)
        self.market_repository = FixtureMarketDataRepository(self.fixture)
        self.dragon_repository = FixtureDragonTigerRepository(self.fixture)

    @classmethod
    def builtin(cls):
        return cls({
            "securities": [{
                "ts_code": "000001.SZ", "symbol": "000001", "name": "Fixture Bank",
                "market": "主板", "list_status": "L",
            }],
            "daily_quotes": [{
                "data_id": "000001.SZ_20260102", "ts_code": "000001.SZ", "trade_date": 20260102,
                "open_price": 10.0, "high_price": 11.0, "low_price": 9.5, "close_price": 10.5,
                "previous_close": 10.0, "change_amount": 0.5, "change_pct": 5.0,
                "volume": 1000.0, "turnover": 10000.0, "stock_name": "Fixture Bank",
            }],
            "index_daily": [{"trade_date": 20260102, "open_price": 3000, "close_price": 3010}],
            "kdj_indicators": [{
                "data_id": "000001.SZ_20260102", "ts_code": "000001.SZ",
                "trade_date": 20260102, "k_value": 50.0, "d_value": 48.0, "j_value": 54.0,
            }],
            "intraday_bars_5m": [{
                "data_id": "20260102_0930_000001_2", "trade_date": 20260102,
                "trade_time": 930, "stock_code": "000001", "open_price": 10.0,
                "high_price": 10.2, "low_price": 9.9, "close_price": 10.1,
                "volume": 100.0, "turnover": 1000.0, "adjustment_flag": "2",
            }],
            "dragon_tiger": [{
                "data_id": "fixture", "trade_date": 20260102, "stock_code": "000001",
                "stock_name": "Fixture Bank", "detail_type": "Fixture Reason",
                "date_type": "day", "net_buy_amount": 0.0,
                "buy_1_broker_name": "Fixture Broker", "buy_1_buy_amount": 0.0, "buy_1_sell_amount": 0.0,
                "buy_2_broker_name": None, "buy_2_buy_amount": 0.0, "buy_2_sell_amount": 0.0,
                "buy_3_broker_name": None, "buy_3_buy_amount": 0.0, "buy_3_sell_amount": 0.0,
                "buy_4_broker_name": None, "buy_4_buy_amount": 0.0, "buy_4_sell_amount": 0.0,
                "buy_5_broker_name": None, "buy_5_buy_amount": 0.0, "buy_5_sell_amount": 0.0,
            }],
            "broker_listing_history": [{
                "data_id": "fixture", "trade_date": 20260102, "broker_id": "fixture",
                "broker_name": "Fixture Broker", "stock_code": "000001",
                "stock_name": "Fixture Bank", "listing_reason": "Fixture Reason",
                "net_amount": 3000.0,
            }],
        })

    @classmethod
    def from_json(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def context(self, target_date):
        data = ResearchData(self.market_repository, self.dragon_repository)
        return ResearchContext(
            market_data=data,
            dragon_tiger=self.dragon_repository,
            target_date=int(target_date),
            query_provider=self.query_provider,
            parameters={"target_date": int(target_date)},
        )


class LocalQueryProvider:
    is_offline = False

    def __init__(self, resources, cache=None):
        self.resources = resources
        self.cache = cache

    @property
    def engine(self):
        return self.resources.get_engine()

    def query(self, sql=None, params=None, fetch=False, commit=False):
        connection = self.resources.get_pool().get_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(sql, tuple(params or ()))
            result = cursor.fetchall() if fetch else None
            if commit:
                connection.commit()
            return result
        finally:
            cursor.close()
            connection.close()

    def read_sql(self, sql, params=None):
        return pd.read_sql(sql, self.engine, params=tuple(params or ()))


def configured_local_context(target_date):
    from stock_lab.config import get_settings
    from stock_lab.infrastructure.cache.redis_client import create_redis_client
    from stock_lab.infrastructure.database import MysqlResources

    settings = get_settings()
    resources = MysqlResources.from_settings(settings)
    query_provider = LocalQueryProvider(resources, create_redis_client(settings))
    market_repository = MarketDataRepository(query_provider.query, query_provider.engine)
    dragon_repository = DragonTigerRepository(query_provider.query, query_provider.engine)
    return ResearchContext(
        market_data=ResearchData(market_repository, dragon_repository),
        dragon_tiger=dragon_repository,
        target_date=int(target_date),
        query_provider=query_provider,
        parameters={"target_date": int(target_date)},
    )


def _normalize_fixture(fixture):
    result = {
        name: ({str(key): list(values) for key, values in rows.items()}
               if name == "redis_lists" else [dict(row) for row in rows])
        for name, rows in fixture.items()
    }
    securities = []
    for row in result.get("securities", []):
        row["ts_code"] = normalize_ts_code(row.get("ts_code", row.get("symbol")))
        row["symbol"] = normalize_symbol(row.get("symbol", row["ts_code"]))
        securities.append(row)
    result["securities"] = securities
    quotes = []
    for row in result.get("daily_quotes", []):
        normalized = {column: row.get(column) for column in DAILY_COLUMNS}
        normalized.update(row)
        normalized["ts_code"] = normalize_ts_code(row.get("ts_code"))
        normalized["data_id"] = row.get("data_id") or f"{normalized['ts_code']}_{row.get('trade_date')}"
        quotes.append(normalized)
    result["daily_quotes"] = quotes
    for table, column in (
        ("kdj_indicators", "ts_code"),
        ("dragon_tiger", "stock_code"),
        ("broker_listing_history", "stock_code"),
        ("jiuyan_actions", "stock_code"),
    ):
        for row in result.get(table, []):
            if row.get(column):
                row[column] = normalize_ts_code(row[column])
    return result
