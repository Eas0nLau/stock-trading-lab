import contextlib
import importlib.util
import io
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from loguru import logger

from .config import validate_tdx_root

_DLL_HANDLES = []


def load_tq(root: Path, session_source: Path | None = None) -> Any:
    root = validate_tdx_root(root)
    plugin_dir = root / "PYPlugins"
    user_dir = plugin_dir / "user"
    if hasattr(os, "add_dll_directory"):
        _DLL_HANDLES.extend((os.add_dll_directory(str(plugin_dir)), os.add_dll_directory(str(root))))
    if str(user_dir) not in sys.path:
        sys.path.insert(0, str(user_dir))
    source = Path(session_source or __file__).resolve()
    name = f"_tdx_tqcenter_{source.stem}_{os.getpid()}_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(name, user_dir / "tqcenter.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load TDX plugin: {user_dir / 'tqcenter.py'}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    session = source.with_name(f"{source.stem}_{os.getpid()}_{datetime.now():%H%M%S}_{time.time_ns()}.py")
    with contextlib.redirect_stdout(io.StringIO()):
        module.tq.initialize(str(session))
    return module.tq


def refresh_tdx_cache(tq: Any) -> Any:
    with contextlib.redirect_stdout(io.StringIO()):
        return tq.refresh_cache()


def get_market_snapshot(tq: Any, code: str) -> dict:
    with contextlib.redirect_stdout(io.StringIO()):
        return tq.get_market_snapshot(stock_code=code)


def close_tq(tq: Any) -> None:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            tq.close()
    except Exception as exc:
        logger.warning("Closing TDX connection failed: {}", exc)


class TdxQuoteSubscription:
    def __init__(self, enabled=True, warmup_seconds=2.0, max_codes=100):
        self.enabled = enabled
        self.warmup_seconds = max(0.0, float(warmup_seconds))
        self.max_codes = max_codes
        self.latest_by_code = {}
        self.subscribed_codes = []

    def on_data(self, data: str) -> None:
        try:
            payload = json.loads(data)
        except (TypeError, ValueError):
            return
        code = str(payload.get("Code") or payload.get("code") or "").strip().upper()
        if code and any(payload.get(key) not in (None, "", 0, "0") for key in ("Price", "Open", "Volume", "Amount")):
            self.latest_by_code[code] = payload

    def subscribe(self, tq: Any, codes: Iterable[str]) -> bool:
        codes = list(dict.fromkeys(str(code).strip().upper() for code in codes if str(code).strip()))
        if not self.enabled or not codes or len(codes) > self.max_codes:
            return False
        with contextlib.redirect_stdout(io.StringIO()):
            tq.subscribe_hq(stock_list=codes, callback=self.on_data)
        self.subscribed_codes = codes
        if self.warmup_seconds:
            time.sleep(self.warmup_seconds)
        return True

    def get_latest(self, code: str) -> dict | None:
        return self.latest_by_code.get(str(code).strip().upper())

    def unsubscribe(self, tq: Any) -> None:
        if self.subscribed_codes:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    tq.unsubscribe_hq(stock_list=self.subscribed_codes)
            finally:
                self.subscribed_codes = []
                self.latest_by_code.clear()
