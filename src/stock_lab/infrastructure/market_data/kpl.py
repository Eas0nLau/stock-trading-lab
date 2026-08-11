import datetime as dt
import time
import uuid

import requests

from stock_lab.shared.errors import DataValidationError, InfrastructureError
from stock_lab.shared.rate_limit import RequestRateLimiter


KPL_HISTORY_URL = "https://apphis.longhuvip.com/w1/api/index.php"
KPL_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; PHU110 Build/W528JS)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
}


def normalize_stock_code(value):
    raw = str(value or "").strip().upper()
    if raw.endswith(".0"):
        raw = raw[:-2]
    if "." in raw:
        first, second = raw.split(".", 1)
        raw = second if first in {"SH", "SZ", "BJ"} else first
    for prefix in ("SH", "SZ", "BJ"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    if not raw.isdigit() or len(raw) > 6:
        raise DataValidationError(f"Invalid KPL stock code: {value!r}")
    return raw.zfill(6)


def _date_text(value):
    if value in (None, ""):
        return None
    raw = str(value).strip().replace("-", "")
    try:
        return dt.datetime.strptime(raw, "%Y%m%d").strftime("%Y%m%d")
    except ValueError as error:
        raise DataValidationError(f"Invalid KPL date: {value!r}") from error


class KplDdeSource:
    def __init__(
        self,
        session=None,
        limiter=None,
        sleep=time.sleep,
        device_id=None,
        today=dt.date.today,
    ):
        self.session = session or requests.Session()
        self.session.headers.update(KPL_HEADERS)
        self.limiter = limiter or RequestRateLimiter(0.5)
        self.sleep = sleep
        self.device_id = device_id or str(uuid.uuid4())
        self.today = today

    def _request(self, params, timeout, retries):
        retries = max(int(retries), 1)
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                self.limiter.wait()
                response = self.session.post(
                    KPL_HISTORY_URL,
                    data=params,
                    timeout=timeout,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError(
                        f"KPL returned {type(payload).__name__}, expected object"
                    )
                if str(payload.get("errcode")) != "0":
                    raise RuntimeError(f"KPL returned business error: {payload}")
                return payload
            except Exception as error:
                last_error = error
                if attempt < retries:
                    self.sleep(0.5 * attempt)
        raise InfrastructureError(f"KPL request failed: {last_error}") from last_error

    def fetch_daily_dde(
        self,
        stock_code,
        *,
        count=100,
        start_date=None,
        end_date=None,
        timeout=20,
        retries=3,
    ):
        stock_code = normalize_stock_code(stock_code)
        start_date = _date_text(start_date)
        end_date = _date_text(end_date)
        if start_date and not end_date:
            end_date = self.today().strftime("%Y%m%d")
        elif end_date and not start_date:
            start_date = end_date
        if start_date and start_date > end_date:
            raise DataValidationError(
                f"Invalid KPL date range: {start_date} > {end_date}"
            )
        if start_date:
            calendar_days = max(
                0,
                (self.today() - dt.datetime.strptime(start_date, "%Y%m%d").date()).days,
            )
            page_size = min(600, max(10, calendar_days + 10))
            target_count = None
        else:
            target_count = int(count)
            if target_count <= 0:
                raise DataValidationError("KPL count must be greater than zero")
            page_size = min(600, max(10, target_count))

        records = []
        index = 0
        while True:
            payload = self._request(
                {
                    "apiv": "w44",
                    "PhoneOSNew": "2",
                    "DeviceID": self.device_id,
                    "VerSion": "5.23.0.4",
                    "Token": "0",
                    "UserID": "0",
                    "StockID": stock_code,
                    "a": "GetDaDanKLine2New",
                    "c": "StockLineData",
                    "Type": "d",
                    "Index": str(index),
                    "st": str(page_size),
                },
                timeout,
                retries,
            )
            page = list(zip(
                payload.get("Date", []) or [],
                payload.get("DDJE", []) or [],
            ))
            if not page:
                break
            records.extend(page)
            valid_dates = []
            for raw_date, _value in page:
                try:
                    valid_dates.append(_date_text(raw_date))
                except DataValidationError:
                    continue
            if start_date and valid_dates and min(valid_dates) <= start_date:
                break
            if target_count is not None and len(records) >= target_count:
                break
            index += len(page)

        rows_by_date = {}
        for raw_date, raw_value in records:
            try:
                trade_date = int(_date_text(raw_date))
                value = float(raw_value)
            except (DataValidationError, TypeError, ValueError):
                continue
            rows_by_date.setdefault(trade_date, {
                "stock_code": stock_code,
                "trade_date": trade_date,
                "dde": value,
            })
        rows = [rows_by_date[date] for date in sorted(rows_by_date, reverse=True)]
        if start_date:
            start_int, end_int = int(start_date), int(end_date)
            return [
                row for row in rows
                if start_int <= row["trade_date"] <= end_int
            ]
        return rows[:target_count]
