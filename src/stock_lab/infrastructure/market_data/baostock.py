import importlib

from stock_lab.modules.market_data.helpers import normalize_symbol, normalize_ts_code
from stock_lab.shared.errors import DataValidationError, InfrastructureError


BAOSTOCK_5M_FIELDS = "open,close,date,time,code,high,low,volume,amount,adjustflag"


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
    """Lazy BaoStock adapter for the narrow five-minute bar source contract."""

    def __init__(self, client=None):
        self._injected_client = client

    def _client(self):
        return self._injected_client or importlib.import_module("baostock")

    def fetch_5m_bars(self, start_date, end_date, ts_code):
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
                _baostock_code(ts_code),
                BAOSTOCK_5M_FIELDS,
                start_date=_iso_date(start_date),
                end_date=_iso_date(end_date),
                frequency="5",
                adjustflag="3",
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
