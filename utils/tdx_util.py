"""通达信 PYPlugins 通用工具。

这个模块只封装和通达信客户端交互的公共动作：
- 从 config.py 配置的通达信目录加载 PYPlugins/user/tqcenter.py；
- 初始化/关闭 TQ 数据接口；
- 按间隔刷新通达信客户端行情缓存；
- 静默读取单股实时快照；
- 把“读取原始快照 + 调用业务解析函数”串成一个通用流程。

这里不放竞价抢筹、突破均线、表格格式化等业务逻辑，避免工具模块依赖具体监控脚本。
"""

import contextlib
import importlib.util
import io
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from loguru import logger


def get_configured_tdx_root() -> Path:
    """从 config.py 读取通达信安装目录。

    以后如果通达信换目录，只需要改 config.py 里的 tdx_root。
    这里故意不在工具模块里写固定路径，避免路径散落在多个脚本中。
    """
    try:
        import config
    except Exception as exc:
        raise RuntimeError("无法导入 config.py，请确认项目根目录在 Python 搜索路径中。") from exc

    value = getattr(config, "tdx_root", None)
    if not value:
        raise RuntimeError("config.py 中缺少 tdx_root 配置，请设置为你的通达信安装目录。")
    return Path(value)


# 通达信安装目录。工具函数默认读取这里的 PYPlugins，不会写入通达信目录。
DEFAULT_TDX_ROOT = get_configured_tdx_root()


def get_configured_cache_refresh_interval_seconds() -> float:
    """从 config.py 读取 TDX 缓存刷新间隔，缺省为 20 秒。"""
    try:
        import config
    except Exception:
        return 20.0

    value = getattr(config, "tdx_cache_refresh_interval_seconds", 20)
    try:
        interval = float(value)
    except (TypeError, ValueError):
        return 20.0
    return interval if interval > 0 else 20.0


DEFAULT_TDX_CACHE_REFRESH_INTERVAL_SECONDS = get_configured_cache_refresh_interval_seconds()

# subscribe_hq 可能推送只有 Code 的空消息。只有出现这些行情字段且值有效时，
# 才把回调当成一条可用实时行情保存，避免覆盖上一条有效报价。
QUOTE_VALUE_KEYS = {
    "Price",
    "Now",
    "Last",
    "LastPrice",
    "Open",
    "PreClose",
    "High",
    "Low",
    "Average",
    "AvgPrice",
    "Volume",
    "Amount",
    "NowVol",
    "Buyp",
    "Buyv",
    "Sellp",
    "Sellv",
    "RefreshNum",
    "ItemNum",
    "CJBS",
    "最新价",
    "开盘价",
    "昨收价",
    "买一价",
    "卖一价",
}

# Windows 下 os.add_dll_directory 返回的 handle 必须保留引用；
# 如果 handle 被释放，后续 tqcenter 依赖的 DLL 可能又找不到。
DLL_DIRECTORY_HANDLES = []

# 同一个 app.py 进程里如果同时启动多个监控线程，底层 TDX DLL 调用不一定是线程安全的。
# 用进程内锁把初始化、刷新、读取快照串行化，减少互相抢同一套 DLL 状态的风险。
TDX_API_LOCK = threading.RLock()


def print_json(data: Any) -> None:
    """统一按中文友好的 JSON 格式打印调试结果。"""
    logger.info(json.dumps(data, ensure_ascii=False, default=str))


def log_captured_stdout(text: str, level: str = "INFO") -> None:
    """把通达信插件内部 print 的内容转成带时间的 logger 输出。"""
    for line in text.splitlines():
        line = line.strip()
        if line:
            logger.log(level, line)


def _has_meaningful_quote_value(value: Any) -> bool:
    """判断回调字段值是否像一条真实行情，而不是空字符串/全 0 占位。"""
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return abs(float(value)) > 0
    if isinstance(value, str):
        text = value.strip()
        if not text or text in {"--", "-", "None", "null", "NULL"}:
            return False
        try:
            return abs(float(text.replace(",", "").replace("%", ""))) > 0
        except ValueError:
            return True
    if isinstance(value, (list, tuple)):
        return any(_has_meaningful_quote_value(item) for item in value)
    return False


def is_meaningful_quote_payload(data: Dict[str, Any]) -> bool:
    """判断 subscribe_hq 回调是否包含有效行情字段。"""
    for key in QUOTE_VALUE_KEYS:
        if key in data and _has_meaningful_quote_value(data.get(key)):
            return True
    return False


def load_tq(tdx_root: Optional[Path] = None, session_source: Optional[Path] = None) -> Any:
    """加载并初始化通达信 TQ 数据接口。

    参数：
    - tdx_root：通达信安装目录；不传时读取 config.py 里的 tdx_root。
    - session_source：用于生成本次会话名的文件路径；只作为名字来源，不会创建这个文件。

    为什么要生成唯一会话名、并独立加载 tqcenter.py：
    通达信插件会用传给 initialize 的路径识别当前“策略/脚本”会话。
    如果多个 Python 进程使用同名路径，容易报“已有同名策略运行”。
    如果 app.py 在同一个 Python 进程内同时启动多个监控，也要避免共享同一份 tqcenter 模块状态。
    """
    tdx_root = Path(tdx_root or DEFAULT_TDX_ROOT)
    plugin_dir = tdx_root / "PYPlugins"
    user_dir = plugin_dir / "user"
    tqcenter_path = user_dir / "tqcenter.py"
    if not tqcenter_path.exists():
        raise FileNotFoundError(tqcenter_path)

    if hasattr(os, "add_dll_directory"):
        # tqcenter 依赖通达信安装目录和 PYPlugins 下的 DLL，加入当前进程搜索路径。
        DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(plugin_dir)))
        DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(tdx_root)))

    if str(user_dir) not in sys.path:
        sys.path.insert(0, str(user_dir))

    source = Path(session_source or __file__).resolve()
    unique_suffix = f"{source.stem}_{os.getpid()}_{time.time_ns()}"
    module_name = f"_tdx_tqcenter_{unique_suffix}"
    spec = importlib.util.spec_from_file_location(module_name, tqcenter_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载通达信 tqcenter 模块：{tqcenter_path}")

    tqcenter = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = tqcenter

    session_name = source.with_name(
        f"{source.stem}_{os.getpid()}_{datetime.now().strftime('%H%M%S')}_{time.time_ns()}.py"
    )
    with TDX_API_LOCK:
        spec.loader.exec_module(tqcenter)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            tqcenter.tq.initialize(str(session_name))
    log_captured_stdout(stdout.getvalue())
    return tqcenter.tq


def refresh_tdx_cache(tq: Any, print_result: bool = False) -> Any:
    """刷新通达信客户端缓存行情。

    通达信这个接口本身叫 refresh_cache，本质上仍是刷新客户端侧缓存，
    不是绕过缓存直连行情源。默认静默掉插件可能打印到 stdout 的内容。
    """
    with TDX_API_LOCK:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            refresh_result = tq.refresh_cache()
    log_captured_stdout(stdout.getvalue())

    if print_result:
        print_json({"refresh_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "refresh": refresh_result})
    return refresh_result


class TdxCacheRefresher:
    """按固定间隔刷新通达信缓存。

    监控循环里每一轮调用 maybe_refresh 即可；它会自行判断是否到达刷新间隔。
    这样多个脚本不用重复维护 last_refresh_at、异常处理和 stdout 静默逻辑。
    """

    def __init__(self, enabled: bool = True, interval: Optional[float] = None, print_result: bool = False) -> None:
        self.enabled = enabled
        self.interval = interval if interval is not None else DEFAULT_TDX_CACHE_REFRESH_INTERVAL_SECONDS
        self.print_result = print_result
        self.last_refresh_at = 0.0

    def refresh_now(self, tq: Any) -> None:
        """立即刷新一次缓存；失败时只打印提示，不中断调用方流程。"""
        if not self.enabled:
            return
        try:
            refresh_tdx_cache(tq, self.print_result)
            self.last_refresh_at = time.time()
        except Exception as exc:
            logger.warning("刷新通达信行情缓存失败，继续读取快照：{}", exc)

    def maybe_refresh(self, tq: Any) -> None:
        """如果已到刷新间隔，则刷新一次；刷新失败时只打印提示，不中断监控。"""
        if not self.enabled:
            return
        if time.time() - self.last_refresh_at < self.interval:
            return
        self.refresh_now(tq)


class TdxQuoteSubscription:
    """通达信实时行情订阅辅助。

    get_market_snapshot 读的是报表快照缓存；如果某只股票没有被客户端实时更新，
    快照里可能出现最新价、盘口、成交量全是 0 的情况。subscribe_hq 会把股票加入
    行情更新订阅队列，回调里拿到的数据也会保存到本进程内存，供监控循环优先使用。

    注意：tqcenter.py 里订阅列表硬限制最多 100 只股票，超过时这里会跳过订阅。
    """

    def __init__(
        self,
        enabled: bool = True,
        warmup_seconds: float = 2.0,
        print_result: bool = False,
        max_codes: int = 100,
    ) -> None:
        self.enabled = enabled
        self.warmup_seconds = max(0.0, float(warmup_seconds))
        self.print_result = print_result
        self.max_codes = max_codes
        self.latest_by_code: Dict[str, Dict[str, Any]] = {}
        self.latest_at_by_code: Dict[str, float] = {}
        self.subscribed_codes: List[str] = []

    def on_data(self, data_str: str) -> None:
        """保存通达信推送来的最新行情。

        tqcenter 的回调入参是 JSON 字符串，里面通常包含 Code、Price、Volume 等字段。
        这里不做业务解析，只按 Code 放进内存缓存。
        """
        try:
            data = json.loads(data_str)
        except Exception:
            return

        code = str(data.get("Code") or data.get("code") or "").strip().upper()
        if not code:
            return
        if not is_meaningful_quote_payload(data):
            return
        self.latest_by_code[code] = data
        self.latest_at_by_code[code] = time.time()

    def subscribe(self, tq: Any, codes: Iterable[str]) -> bool:
        """订阅一批股票行情；成功后会等待 warmup_seconds 让首批回调到达。"""
        if not self.enabled:
            return False

        normalized = [str(code).strip().upper() for code in codes if str(code).strip()]
        normalized = list(dict.fromkeys(normalized))
        if not normalized:
            return False
        if len(normalized) > self.max_codes:
            logger.warning(
                "订阅行情跳过：通达信 subscribe_hq 最多支持 {} 只，当前 {} 只。",
                self.max_codes,
                len(normalized),
            )
            return False

        try:
            with TDX_API_LOCK:
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    result = tq.subscribe_hq(stock_list=normalized, callback=self.on_data)
            log_captured_stdout(stdout.getvalue())
            self.subscribed_codes = normalized
            if self.print_result:
                print_json(
                    {
                        "subscribe_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "subscribe": result,
                        "codes": normalized,
                    }
                )
            if self.warmup_seconds > 0:
                time.sleep(self.warmup_seconds)
            return True
        except Exception as exc:
            logger.warning("订阅通达信实时行情失败，继续读取快照缓存：{}", exc)
            return False

    def get_latest(self, code: str, max_age_seconds: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """返回某只股票最近一次订阅回调数据。

        max_age_seconds 用来避免一直复用旧订阅数据；超过有效期后返回 None，
        调用方会回退到 get_market_snapshot，读取刷新后的报表快照缓存。
        """
        normalized = str(code).strip().upper()
        data = self.latest_by_code.get(normalized)
        if data is None:
            return None
        if max_age_seconds is not None:
            updated_at = self.latest_at_by_code.get(normalized, 0.0)
            if time.time() - updated_at > max_age_seconds:
                return None
        return data

    def unsubscribe(self, tq: Any) -> None:
        """取消订阅；失败不影响进程退出。"""
        if not self.subscribed_codes:
            return
        try:
            with TDX_API_LOCK:
                with contextlib.redirect_stdout(io.StringIO()):
                    tq.unsubscribe_hq(stock_list=self.subscribed_codes)
        except Exception:
            pass
        finally:
            self.subscribed_codes = []
            self.latest_by_code.clear()
            self.latest_at_by_code.clear()


def get_tdx_market_snapshot(tq: Any, code: str) -> Dict[str, Any]:
    """静默读取单只股票实时快照。

    tqcenter.get_market_snapshot 有时会把原始 json 打印到 stdout。
    监控脚本只需要结构化返回值，所以这里默认压掉这些输出。
    """
    with TDX_API_LOCK:
        with contextlib.redirect_stdout(io.StringIO()):
            return tq.get_market_snapshot(stock_code=code)


def close_tq(tq: Any) -> None:
    """关闭通达信连接，并把插件内部 print 转为 logger 输出。"""
    with TDX_API_LOCK:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            tq.close()
    log_captured_stdout(stdout.getvalue())


def read_tdx_snapshot_row(
    tq: Any,
    code: str,
    row_builder: Callable[[str, Any, datetime], Dict[str, Any]],
    read_time: Optional[datetime] = None,
    print_raw: bool = False,
    record_getter: Optional[Callable[[Any], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """读取实时快照，并交给业务层解析成一行数据。

    row_builder 由调用方传入，例如全局监控里的 extract_snapshot_row。
    这样工具模块负责 TDX 读取，业务脚本负责解释字段含义。
    """
    read_time = read_time or datetime.now()
    data = get_tdx_market_snapshot(tq, code)

    if print_raw:
        raw_keys = list(record_getter(data).keys()) if record_getter else list(data.keys())
        print_json({"raw_snapshot_sample": data, "raw_keys": raw_keys})

    return row_builder(code, data, read_time)
