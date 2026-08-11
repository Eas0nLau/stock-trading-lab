import importlib
import datetime as dt

from stock_lab.modules.market_data.helpers import normalize_symbol, normalize_ts_code
from stock_lab.shared.errors import DataValidationError, InfrastructureError


BAOSTOCK_5M_FIELDS = "open,close,date,time,code,high,low,volume,amount,adjustflag"
BAOSTOCK_INDEX_FIELDS = "date,code,open,close,high,low,volume,amount,adjustflag,turn,pctChg"


def _iso_date(value):
    raw = str(value or "").replace("-", "").replace("/", "")[:8]
    if len(raw) != 8 or not raw.isdigit():
        raise DataValidationError(f"Invalid BaoStock date: {value!r}")
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _baostock_code(value):
    raw = str(value or "").strip().lower()
    if raw.startswith(("sh.", "sz.", "bj.")):
        return raw
    ts_code = normalize_ts_code(value)
    symbol = normalize_symbol(ts_code)
    if not symbol.isdigit() or len(symbol) != 6:
        raise DataValidationError(f"Invalid stock code: {value!r}")
    if "." in ts_code:
        exchange = ts_code.rsplit(".", 1)[1].lower()
    elif symbol.startswith(("5", "6", "9")):
        exchange = "sh"
    elif symbol.startswith(("4", "8")):
        exchange = "bj"
    else:
        exchange = "sz"
    if exchange not in {"sh", "sz", "bj"}:
        raise DataValidationError(f"Unsupported stock exchange: {value!r}")
    return f"{exchange}.{symbol}"


class BaoStockSource:
    """Lazy BaoStock adapter for historical index and five-minute bars."""

    def __init__(self, client=None):
        self._injected_client = client

    def _client(self):
        return self._injected_client or importlib.import_module("baostock")

    def fetch_5m_bars(self, start_date, end_date, ts_code):
        return self._query_rows(
            _baostock_code(ts_code),
            BAOSTOCK_5M_FIELDS,
            start_date=_iso_date(start_date),
            end_date=_iso_date(end_date),
            frequency="5",
            adjustflag="3",
        )

    def fetch_index_daily(self, start_date, end_date):
        try:
            requested_start = dt.datetime.strptime(str(start_date), "%Y%m%d").date()
            requested_end = dt.datetime.strptime(str(end_date), "%Y%m%d").date()
        except ValueError as error:
            raise DataValidationError(
                f"Invalid BaoStock index range: {start_date!r}-{end_date!r}"
            ) from error
        if requested_start > requested_end:
            raise DataValidationError(
                f"Invalid BaoStock index range: {start_date!r}-{end_date!r}"
            )
        rows = self._query_rows(
            "sh.000001",
            BAOSTOCK_INDEX_FIELDS,
            start_date=(requested_start - dt.timedelta(days=20)).strftime("%Y-%m-%d"),
            end_date=requested_end.strftime("%Y-%m-%d"),
            frequency="d",
            adjustflag="3",
        )
        normalized = []
        previous_close = None
        try:
            for row in rows:
                trade_date = dt.datetime.strptime(str(row["date"]), "%Y-%m-%d").date()
                close = float(row["close"])
                if (
                    previous_close not in (None, 0)
                    and requested_start <= trade_date <= requested_end
                ):
                    high = float(row["high"])
                    low = float(row["low"])
                    normalized.append({
                        "date": row["date"],
                        "open": float(row["open"]),
                        "close": close,
                        "high": high,
                        "low": low,
                        "volume": float(row["volume"]) / 100,
                        "amount": float(row["amount"]),
                        "amplitude": (high - low) / previous_close * 100,
                        "pct_chg": float(row["pctChg"]),
                        "change": close - previous_close,
                        "turnover": float(row["turn"]),
                    })
                previous_close = close
        except (KeyError, TypeError, ValueError) as error:
            raise InfrastructureError(f"BaoStock returned malformed index data: {error}") from error
        return normalized

    def _query_rows(self, code, fields, **options):
        try:
            client = self._client()
            login = client.login()
        except Exception as error:
            raise InfrastructureError(f"BaoStock login failed: {error}") from error
        if str(login.error_code) != "0":
            raise InfrastructureError(f"BaoStock login failed: {login.error_msg}")

        request_error = None
        request_cause = None
        try:
            result = client.query_history_k_data_plus(
                code,
                fields,
                **options,
            )
            if str(result.error_code) != "0":
                raise InfrastructureError(f"BaoStock query failed: {result.error_msg}")
            rows = []
            while result.next():
                values = result.get_row_data()
                if len(values) != len(result.fields):
                    raise InfrastructureError("BaoStock returned a malformed row")
                rows.append(dict(zip(result.fields, values)))
        except (DataValidationError, InfrastructureError) as error:
            request_error = error
        except Exception as error:
            request_error = InfrastructureError(f"BaoStock request failed: {error}")
            request_cause = error
        finally:
            try:
                client.logout()
            except Exception as error:
                if request_error is None:
                    raise InfrastructureError(f"BaoStock logout failed: {error}") from error
        if request_error is not None:
            if request_cause is not None:
                raise request_error from request_cause
            raise request_error
        return rows
