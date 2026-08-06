import datetime
import hashlib
import heapq
import json
import re
import queue
import os
import sys
import threading
import time

项目根目录 = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if 项目根目录 not in sys.path:
    sys.path.append(项目根目录)

from fastapi.responses import StreamingResponse
from loguru import logger

import config
from utils import db, driver_chrome

driver_web = None
资金流向推送锁 = threading.Lock()
资金流向推送队列 = set()
资金流向历史缓存锁 = threading.Lock()
东方财富概念排除名单缓存 = None
资金流向redis前缀 = {
    "industry": "fund_flow",
    "concept": "fund_flow_概念",
}
资金流向类型映射 = {redis_key: flow_type for flow_type, redis_key in 资金流向redis前缀.items()}

资金流向采集时间段 = (
    (datetime.time(9, 27), datetime.time(11, 31)),
    (datetime.time(12, 58), datetime.time(15, 1)),
)

资金流向接口路径前缀 = "/api/zijin"


def 注册接口(app):
    @app.get(f"{资金流向接口路径前缀}/history/{{date}}")
    def get_history(date: str, top_n: int | None = None):
        """获取某一天行业资金流向历史数据"""
        return 获取资金流向历史数据("fund_flow", date, top_n)

    @app.get(f"{资金流向接口路径前缀}/dates")
    def get_dates():
        """获取所有有行业资金流向历史数据的日期"""
        return 获取资金流向日期列表("fund_flow")

    @app.get(f"{资金流向接口路径前缀}/stream")
    async def get_fund_flow_stream():
        return StreamingResponse(
            资金流向事件流(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get(f"{资金流向接口路径前缀}/{{flow_type}}/history/{{date}}")
    def get_fund_flow_history(flow_type: str, date: str, top_n: int | None = None):
        """按类型获取某一天资金流向历史数据"""
        return 获取资金流向历史数据(获取资金流向redis前缀(flow_type), date, top_n)

    @app.get(f"{资金流向接口路径前缀}/{{flow_type}}/dates")
    def get_fund_flow_dates(flow_type: str):
        """按类型获取所有有资金流向历史数据的日期"""
        return 获取资金流向日期列表(获取资金流向redis前缀(flow_type))


def 资金流向事件流():
    event_queue = queue.Queue(maxsize=100)
    with 资金流向推送锁:
        资金流向推送队列.add(event_queue)

    try:
        yield 'data: {"类型": "ready"}\n\n'
        while True:
            try:
                event = event_queue.get(timeout=15)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except queue.Empty:
                yield ": ping\n\n"
    finally:
        with 资金流向推送锁:
            资金流向推送队列.discard(event_queue)


def 推送资金流向更新(redis_key_prefix, 名称, today, current_time_text, records):
    event = {
        "类型": "snapshot",
        "flowType": 资金流向类型映射.get(redis_key_prefix, "industry"),
        "redisKey": redis_key_prefix,
        "名称": 名称,
        "采集日期": today,
        "采集时间": current_time_text,
        "记录数量": len(records or []),
    }

    with 资金流向推送锁:
        subscribers = list(资金流向推送队列)

    for event_queue in subscribers:
        try:
            if event_queue.full():
                event_queue.get_nowait()
            event_queue.put_nowait(event)
        except Exception:
            with 资金流向推送锁:
                资金流向推送队列.discard(event_queue)


def 获取资金流向采集间隔秒():
    return config.资金流向采集间隔秒


def 获取资金流向历史返回top数量(top_n=None):
    if top_n is None:
        top_n = config.资金流向历史返回Top数量
    return max(int(top_n), 0)


def 计算距离下次对齐执行秒数(interval_seconds=None):
    interval_seconds = interval_seconds or 获取资金流向采集间隔秒()
    now = datetime.datetime.now()
    seconds_since_midnight = (
            now.hour * 3600
            + now.minute * 60
            + now.second
            + now.microsecond / 1_000_000
    )
    remainder = seconds_since_midnight % interval_seconds
    if remainder == 0:
        return 0
    return interval_seconds - remainder


def 等待到下次对齐执行(interval_seconds=None):
    sleep_seconds = 计算距离下次对齐执行秒数(interval_seconds)
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)


def 当前是资金流向采集时间(now=None):
    now = now or datetime.datetime.now()
    if now.weekday() >= 5:
        return False

    current_time = now.time()
    return any(start <= current_time <= end for start, end in 资金流向采集时间段)


def 获取资金流向redis前缀(flow_type: str):
    return 资金流向redis前缀.get(flow_type, "fund_flow")


def 获取资金流向历史数据(redis_key_prefix: str, date: str, top_n=None):
    top_n = 获取资金流向历史返回top数量(top_n)
    if top_n <= 0:
        snapshots = 读取原始资金流向快照(redis_key_prefix, date)
        return 压缩资金流向历史数据(snapshots, top_n)

    # 图表接口只需要各时间点 Top N 的快照。首次访问旧数据时构建一次，之后直接读取轻量缓存。
    with 资金流向历史缓存锁:
        cache_key = 获取资金流向图表缓存key(redis_key_prefix, date, top_n)
        cached_data = db.redis_con_localhost.get(cache_key)
        if cached_data:
            try:
                return json.loads(cached_data)
            except Exception:
                db.redis_con_localhost.delete(cache_key)

        snapshots = 读取轻量资金流向快照(redis_key_prefix, date, top_n)
        response = 构建资金流向图表数据(snapshots, top_n)
        db.redis_con_localhost.set(
            cache_key,
            json.dumps(response, ensure_ascii=False, separators=(",", ":")),
        )
        db.redis_con_localhost.sadd(获取资金流向图表缓存索引key(redis_key_prefix, date), cache_key)
        return response


def 获取东方财富概念排除名单():
    global 东方财富概念排除名单缓存
    if 东方财富概念排除名单缓存 is None:
        东方财富概念排除名单缓存 = frozenset(
            标准化东方财富概念匹配值(item)
            for item in config.东方财富概念排除名单
            if 标准化东方财富概念匹配值(item)
        )
    return 东方财富概念排除名单缓存


def 获取东方财富概念排除版本():
    names = "|".join(sorted(获取东方财富概念排除名单()))
    return hashlib.sha1(names.encode("utf-8")).hexdigest()[:12]


def 标准化东方财富概念名称(value):
    return str(value or "").strip().strip("【】[]")


def 标准化东方财富概念匹配值(value):
    return re.sub(r"[\s_＿\-]+", "", 标准化东方财富概念名称(value)).upper()


def 东方财富概念已排除(value, excluded_names=None):
    name = 标准化东方财富概念匹配值(value)
    if not name:
        return False

    excluded = excluded_names if excluded_names is not None else 获取东方财富概念排除名单()
    if name in excluded:
        return True

    if re.match(r"^20\d{2}(年报|一季报|半年报|三季报)(预增|扭亏|预亏|预减|高增长)$", name):
        return True
    return False


def 过滤东方财富概念资金流向快照(snapshot):
    excluded_names = 获取东方财富概念排除名单()
    return [
        item for item in snapshot
        if not 东方财富概念已排除(item.get("板块名称"), excluded_names)
    ]

def 获取资金流向金额(item):
    try:
        return float(item.get("资金净流入(亿)", 0) or 0)
    except (TypeError, ValueError):
        return 0


def 过滤资金流向快照(snapshot, top_n):
    if top_n <= 0:
        return snapshot

    inflow = []
    outflow = []
    for item in snapshot:
        amount = 获取资金流向金额(item)
        if amount > 0:
            inflow.append((amount, item))
        elif amount < 0:
            outflow.append((amount, item))

    inflow = heapq.nlargest(top_n, inflow, key=lambda row: row[0])
    outflow = heapq.nsmallest(top_n, outflow, key=lambda row: row[0])
    return [item for _, item in inflow] + [item for _, item in outflow]


def 获取资金流向轻量快照key(redis_key_prefix, date, top_n):
    suffix = ""
    if redis_key_prefix == "fund_flow_概念":
        suffix = f":概念排除{获取东方财富概念排除版本()}"
    return f"{redis_key_prefix}:轻量快照:{date}:top{top_n}{suffix}"


def 获取资金流向轻量快照索引key(redis_key_prefix, date):
    return f"{redis_key_prefix}:轻量快照索引:{date}"


def 获取资金流向图表缓存key(redis_key_prefix, date, top_n):
    suffix = ""
    if redis_key_prefix == "fund_flow_概念":
        suffix = f":概念排除{获取东方财富概念排除版本()}"
    return f"{redis_key_prefix}:图表缓存:{date}:top{top_n}{suffix}"


def 获取资金流向图表缓存索引key(redis_key_prefix, date):
    return f"{redis_key_prefix}:图表缓存索引:{date}"


def 获取快照时间(snapshot):
    if not isinstance(snapshot, list):
        return ""
    return next((row.get("时间") for row in snapshot if row.get("时间")), "")


def 读取快照列表(redis_key_prefix, redis_key):
    snapshots = []
    for item in db.redis_con_localhost.lrange(redis_key, 0, -1):
        try:
            snapshot = json.loads(item)
        except Exception:
            continue
        if not isinstance(snapshot, list) or not snapshot:
            continue
        if redis_key_prefix == "fund_flow_概念":
            snapshot = 过滤东方财富概念资金流向快照(snapshot)
        if snapshot:
            snapshots.append(snapshot)
    return snapshots


def 读取原始资金流向快照(redis_key_prefix, date):
    return 读取快照列表(redis_key_prefix, f"{redis_key_prefix}:history:{date}")


def 读取轻量资金流向快照(redis_key_prefix, date, top_n):
    compact_key = 获取资金流向轻量快照key(redis_key_prefix, date, top_n)
    if db.redis_con_localhost.exists(compact_key):
        return 读取快照列表(redis_key_prefix, compact_key)

    raw_snapshots = 读取原始资金流向快照(redis_key_prefix, date)
    compact_snapshots = [
        过滤资金流向快照(snapshot, top_n)
        for snapshot in raw_snapshots
    ]
    compact_data = [
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
        for snapshot in compact_snapshots
    ]
    if compact_data:
        pipeline = db.redis_con_localhost.pipeline()
        pipeline.delete(compact_key)
        pipeline.rpush(compact_key, *compact_data)
        pipeline.sadd(获取资金流向轻量快照索引key(redis_key_prefix, date), str(top_n))
        pipeline.execute()
    return compact_snapshots


def 构建资金流向图表数据(snapshots, top_n):
    times = []
    snapshot_by_time = {}
    for snapshot in snapshots:
        snapshot_time = 获取快照时间(snapshot)
        if not snapshot_time:
            continue
        if snapshot_time not in snapshot_by_time:
            times.append(snapshot_time)
        snapshot_by_time[snapshot_time] = snapshot

    if not times:
        return {"format": "matrix-v2", "top_n": top_n, "times": [], "boards": []}

    board_map = {}
    for time_index, snapshot_time in enumerate(times):
        for item in snapshot_by_time[snapshot_time]:
            board_name = item.get("板块名称")
            if not board_name:
                continue
            board = board_map.get(board_name)
            if board is None:
                board = {
                    "code": item.get("板块代码", ""),
                    "name": board_name,
                    "points": [],
                }
                board_map[board_name] = board
            board["points"].append([
                time_index,
                item.get("资金净流入(亿)", 0),
                item.get("龙头", ""),
            ])

    return {
        "format": "matrix-v2",
        "top_n": top_n,
        "times": times,
        "boards": list(board_map.values()),
    }


def 清理资金流向图表缓存(redis_key_prefix, date):
    index_key = 获取资金流向图表缓存索引key(redis_key_prefix, date)
    cache_keys = db.redis_con_localhost.smembers(index_key)
    if not cache_keys:
        return
    pipeline = db.redis_con_localhost.pipeline()
    pipeline.delete(*cache_keys)
    pipeline.delete(index_key)
    pipeline.execute()


def 压缩资金流向历史数据(snapshots, top_n):
    times = []
    time_index_map = {}
    board_map = {}

    for snapshot in snapshots:
        snapshot_time = next((row.get("时间") for row in snapshot if row.get("时间")), None)
        if not snapshot_time:
            continue

        if snapshot_time not in time_index_map:
            time_index_map[snapshot_time] = len(times)
            times.append(snapshot_time)
            for board in board_map.values():
                board["values"].append(None)
                board["leaders"].append("")

        time_index = time_index_map[snapshot_time]
        for item in snapshot:
            board_name = item.get("板块名称")
            if not board_name:
                continue

            board = board_map.get(board_name)
            if board is None:
                board = {
                    "code": item.get("板块代码", ""),
                    "name": board_name,
                    "values": [None] * len(times),
                    "leaders": [""] * len(times),
                }
                board_map[board_name] = board

            board["values"][time_index] = item.get("资金净流入(亿)", 0)
            board["leaders"][time_index] = item.get("龙头", "")

    return {
        "format": "matrix-v1",
        "top_n": top_n,
        "times": times,
        "boards": list(board_map.values()),
    }


def 获取资金流向日期列表(redis_key_prefix: str):
    keys = db.redis_con_localhost.keys(f"{redis_key_prefix}:history:*")
    dates = [key.split(":")[-1] for key in keys]
    dates = sorted(set(dates), reverse=True)
    return dates


def 预热最新资金流向历史():
    top_n = 获取资金流向历史返回top数量()
    if top_n <= 0:
        return

    for redis_key_prefix, name in (("fund_flow", "行业资金流向"), ("fund_flow_概念", "概念资金流向")):
        dates = 获取资金流向日期列表(redis_key_prefix)
        if not dates:
            continue
        date = dates[0]
        try:
            logger.info(f"预热 {name} {date} Top {top_n} 图表缓存")
            获取资金流向历史数据(redis_key_prefix, date, top_n)
        except Exception as error:
            logger.warning(f"预热 {name} {date} 图表缓存失败: {error}")


def init_driver():
    global driver_web
    driver_web = driver_chrome.初始化页面(
        "无",
        "https://data.eastmoney.com/bkzj/hy.html",
        使用主标签页=True,
    )


def _写入资金流向redis(redis_key_prefix, today, current_time_text, records):
    history_data = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    history_key = f"{redis_key_prefix}:history:{today}"
    default_top_n = 获取资金流向历史返回top数量()

    with 资金流向历史缓存锁:
        last_history = db.redis_con_localhost.lindex(history_key, -1)
        try:
            last_snapshot = json.loads(last_history) if last_history else []
        except Exception:
            last_snapshot = []

        same_snapshot_time = 获取快照时间(last_snapshot) == current_time_text
        initialize_compact_history = last_history is None
        if default_top_n > 0 and last_history and not db.redis_con_localhost.exists(
            获取资金流向轻量快照key(redis_key_prefix, today, default_top_n)
        ):
            # 老历史只有原始快照时，在采集线程中预构建，避免用户首次打开页面等待大数据迁移。
            logger.info(f"开始预构建 {redis_key_prefix} {today} Top {default_top_n} 轻量历史快照")
            读取轻量资金流向快照(redis_key_prefix, today, default_top_n)

        compact_top_values = {default_top_n} if default_top_n > 0 else set()
        for value in db.redis_con_localhost.smembers(
            获取资金流向轻量快照索引key(redis_key_prefix, today)
        ):
            try:
                top_n = int(value)
            except (TypeError, ValueError):
                continue
            if top_n > 0:
                compact_top_values.add(top_n)

        pipeline = db.redis_con_localhost.pipeline()
        pipeline.set(f"{redis_key_prefix}:latest", history_data)
        if same_snapshot_time:
            pipeline.lset(history_key, -1, history_data)
        else:
            pipeline.rpush(history_key, history_data)

        for top_n in compact_top_values:
            compact_key = 获取资金流向轻量快照key(redis_key_prefix, today, top_n)
            has_compact_history = db.redis_con_localhost.exists(compact_key)
            if not has_compact_history and not initialize_compact_history:
                continue

            compact_snapshot = 过滤资金流向快照(records, top_n)
            compact_data = json.dumps(compact_snapshot, ensure_ascii=False, separators=(",", ":"))
            last_compact = db.redis_con_localhost.lindex(compact_key, -1)
            if same_snapshot_time and last_compact is not None:
                pipeline.lset(compact_key, -1, compact_data)
            else:
                pipeline.rpush(compact_key, compact_data)
            pipeline.sadd(获取资金流向轻量快照索引key(redis_key_prefix, today), str(top_n))

        pipeline.execute()
        # Keep the official V1 key in sync while the browser collector remains a legacy adapter.
        from stock_lab.modules.fund_flow.contracts import translate_legacy_fund_flow
        from stock_lab.modules.fund_flow.repository import FundFlowRepository

        flow_type = "concept" if redis_key_prefix == "fund_flow_概念" else "industry"
        FundFlowRepository(db.redis_con_localhost).save_history(
            flow_type,
            today,
            translate_legacy_fund_flow(records),
        )
        清理资金流向图表缓存(redis_key_prefix, today)


def _资金流向采集(名称, 页面地址, redis_key_prefix):
    if driver_web is None:
        init_driver()
    try:
        current_time = datetime.datetime.now()
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        current_time_text = current_time.strftime("%H:%M:%S")
        today = current_time.strftime("%Y%m%d")

        logger.info(f"[{current_time_str}] 开始抓取{名称}...")

        driver_web.listen.start(["/dataapi/bkzj/getbkzj", "/api/qt/clist/get"])
        driver_web.get(页面地址, timeout=0)

        data_response = None
        板块个股_dict = {}
        板块个股_response = None
        for packet in driver_web.listen.steps(timeout=5):
            logger.info(packet.target)
            if "/api/qt/clist/get" == packet.target:
                板块个股_response = json.loads("".join(packet.response.body.split("(")[1:])[0:-2:])
            if isinstance(packet.response.body, dict):
                data_response = packet.response.body
            if 板块个股_response and data_response:
                break
        if 板块个股_response is None or data_response is None:
            logger.error(f"网页数据加载超时。重新加载")
            return _资金流向采集(名称, 页面地址, redis_key_prefix)
        for row in 板块个股_response["data"]["diff"]:
            板块个股_dict[row["f12"]] = row["f204"]
        if not data_response or "data" not in data_response or "diff" not in data_response["data"]:
            logger.warning(f"[{current_time_str}] 未获取到有效数据")
            return

        records = []
        for item in data_response["data"]["diff"]:
            f62_yi = round(item.get("f62", 0) / 10000.0, 2)
            records.append({
                "时间": current_time_text,
                "板块代码": item.get("f12", ""),
                "板块名称": f"{item.get('f14', '')}",
                "龙头": f"{板块个股_dict.get(item.get('f12', ''), '')}",
                "资金净流入(亿)": f62_yi,
            })

        if redis_key_prefix == "fund_flow_概念":
            before_count = len(records)
            records = 过滤东方财富概念资金流向快照(records)
            filtered_count = before_count - len(records)
            if filtered_count:
                logger.info(f"[{current_time_str}] {名称}按东方财富概念排除名单过滤 {filtered_count} 条，保留 {len(records)} 条")

        _写入资金流向redis(redis_key_prefix, today, current_time_text, records)
        推送资金流向更新(redis_key_prefix, 名称, today, current_time_text, records)
        logger.info(f"[{current_time_str}] {名称}数据已存入 Redis {redis_key_prefix}（{len(records)} 条）")

    except Exception as e:
        if "浏览器未开启或已关闭。" in str(e) or "与页面的连接已断开" in str(e):
            logger.error(f"监测到浏览器已关闭，重新打开浏览器。{e}")
            init_driver()
            return _资金流向采集(名称, 页面地址, redis_key_prefix)
        logger.error(f"{名称}抓取异常: {e}")
        return _资金流向采集(名称, 页面地址, redis_key_prefix)


def 行业资金流向采集():
    return _资金流向采集(
        名称="行业资金流向",
        页面地址="https://data.eastmoney.com/bkzj/hy.html",
        redis_key_prefix="fund_flow",
    )


def 概念资金流向采集():
    return _资金流向采集(
        名称="概念资金流向",
        页面地址="https://data.eastmoney.com/bkzj/gn.html",
        redis_key_prefix="fund_flow_概念",
    )


def 采集全部资金流向():
    行业资金流向采集()
    概念资金流向采集()


if __name__ == "__main__":
    采集全部资金流向()
