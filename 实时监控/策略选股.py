import datetime
import json
import queue
import os
import re
import sys
import threading
import time
import uuid

from fastapi import Body, HTTPException
from fastapi.responses import StreamingResponse

项目根目录 = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if 项目根目录 not in sys.path:
    sys.path.append(项目根目录)

from loguru import logger

import config
from utils import db, driver_chrome


采集锁 = threading.RLock()
策略选股推送锁 = threading.Lock()
策略选股推送队列 = set()

策略选股接口路径前缀 = "/api/strategy-pick"
策略配置key = "策略选股:strategies"
全局事件前缀 = "策略选股:events"
最后事件IDkey = "策略选股:last_event_id"
默认策略ID = "eastmoney_default"
默认策略名称 = "东方财富策略选股"
策略ID自动调整提示 = set()

默认策略监控时间段 = (
    (datetime.time(9, 0), datetime.time(15, 0)),
)


def 注册接口(app):
    @app.get(f"{策略选股接口路径前缀}/strategies")
    def get_strategies():
        return 获取策略列表()

    @app.post(f"{策略选股接口路径前缀}/strategies")
    def post_strategy(payload: dict = Body(...)):
        return 新增策略(payload)

    @app.put(f"{策略选股接口路径前缀}/strategies/{{strategy_id}}")
    def put_strategy(strategy_id: str, payload: dict = Body(...)):
        return 更新策略(strategy_id, payload)

    @app.delete(f"{策略选股接口路径前缀}/strategies/{{strategy_id}}")
    def delete_strategy(strategy_id: str):
        return 删除策略(strategy_id)

    @app.get(f"{策略选股接口路径前缀}/strategies/{{strategy_id}}/latest")
    def get_strategy_latest(strategy_id: str):
        return 读取最新快照(strategy_id)

    @app.get(f"{策略选股接口路径前缀}/strategies/{{strategy_id}}/history/{{date}}")
    def get_strategy_history(strategy_id: str, date: str):
        return 读取快照历史(strategy_id, date)

    @app.get(f"{策略选股接口路径前缀}/strategies/{{strategy_id}}/events/{{date}}")
    def get_strategy_events(strategy_id: str, date: str):
        return 读取入选事件(strategy_id, date)

    @app.get(f"{策略选股接口路径前缀}/strategies/{{strategy_id}}/dates")
    def get_strategy_dates(strategy_id: str):
        return 获取策略选股日期列表(strategy_id)

    @app.post(f"{策略选股接口路径前缀}/strategies/{{strategy_id}}/refresh")
    def post_strategy_refresh(strategy_id: str):
        return 策略选股采集(strategy_id)

    @app.post(f"{策略选股接口路径前缀}/refresh-all")
    def post_refresh_all():
        return 采集全部启用策略()

    @app.get(f"{策略选股接口路径前缀}/stream")
    def get_strategy_stream():
        return StreamingResponse(
            策略选股事件流(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get(f"{策略选股接口路径前缀}/latest")
    def get_latest():
        return 读取最新快照(获取默认策略ID())

    @app.get(f"{策略选股接口路径前缀}/history/{{date}}")
    def get_history(date: str):
        return 读取快照历史(获取默认策略ID(), date)

    @app.get(f"{策略选股接口路径前缀}/events/{{date}}")
    def get_events(date: str):
        return 读取全局入选事件(date)

    @app.get(f"{策略选股接口路径前缀}/dates")
    def get_dates():
        return 获取策略选股日期列表()

    @app.post(f"{策略选股接口路径前缀}/refresh")
    def post_refresh():
        return 策略选股采集(获取默认策略ID())



def 策略选股事件流():
    event_queue = queue.Queue(maxsize=100)
    with 策略选股推送锁:
        策略选股推送队列.add(event_queue)

    try:
        yield "data: {\"类型\": \"ready\"}\n\n"
        while True:
            try:
                event = event_queue.get(timeout=15)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except queue.Empty:
                yield ": ping\n\n"
    finally:
        with 策略选股推送锁:
            策略选股推送队列.discard(event_queue)


def 推送策略更新(snapshot):
    event = {
        "类型": "snapshot",
        "策略ID": snapshot.get("策略ID", ""),
        "策略名称": snapshot.get("策略名称", ""),
        "采集日期": snapshot.get("采集日期", ""),
        "采集时间": snapshot.get("采集时间", ""),
        "状态": snapshot.get("状态", ""),
        "名单数量": len(snapshot.get("股票列表") or []),
        "新增数量": len(snapshot.get("新增股票") or []),
        "新增股票": snapshot.get("新增股票") or [],
        "移除数量": len(snapshot.get("移除股票") or []),
        "移除股票": snapshot.get("移除股票") or [],
    }

    with 策略选股推送锁:
        subscribers = list(策略选股推送队列)

    for event_queue in subscribers:
        try:
            if event_queue.full():
                event_queue.get_nowait()
            event_queue.put_nowait(event)
        except Exception:
            with 策略选股推送锁:
                策略选股推送队列.discard(event_queue)


def 当前是策略监控时间(strategy, now=None):
    now = now or datetime.datetime.now()
    current_time = now.time()
    return any(start <= current_time <= end for start, end in 获取策略监控时间段(strategy))


def 获取策略监控时间段(strategy):
    return 标准化监控时间段(strategy.get("监控时间段") or [])


def 获取策略监控频率秒(strategy):
    return 标准化监控频率秒(strategy.get("监控频率秒"))


def 策略执行槽(strategy, now=None):
    now = now or datetime.datetime.now()
    interval_seconds = 获取策略监控频率秒(strategy)
    seconds_since_midnight = now.hour * 3600 + now.minute * 60 + now.second
    slot = seconds_since_midnight // interval_seconds
    return f"{now.strftime('%Y%m%d')}:{slot}"


def 格式化策略时间段(strategy):
    periods = 获取策略监控时间段(strategy)
    if not periods:
        return "未配置"
    return ", ".join(f"{start.strftime('%H:%M')}~{end.strftime('%H:%M')}" for start, end in periods)


def start_monitor():
    strategies = 初始化策略配置()
    logger.info(f"策略选股监控线程已启动，已加载 {len(strategies)} 个策略，按每个策略自己的监控时间段和频率执行")
    for strategy in strategies:
        logger.info(
            f"策略配置：id={strategy.get('id')} 名称={strategy.get('名称')} "
            f"启用={strategy.get('启用', True)} 时间段={格式化策略时间段(strategy)} "
            f"频率={获取策略监控频率秒(strategy)}秒 页面={strategy.get('页面URL')}"
        )

    已执行槽 = {}
    状态日志槽 = {}

    while True:
        now = datetime.datetime.now()
        try:
            采集到期策略(now, 已执行槽, 状态日志槽)
        except Exception as e:
            logger.exception(f"策略选股监控主循环异常: {e}")
        time.sleep(1)


def 记录策略监控状态(strategy, now, reason, message, 状态日志槽):
    if 状态日志槽 is None:
        return

    slot = now.strftime("%Y%m%d%H%M")
    key = f"{strategy.get('id')}:{reason}"
    if 状态日志槽.get(key) == slot:
        return

    状态日志槽[key] = slot
    logger.info(message)


def 采集到期策略(now=None, 已执行槽=None, 状态日志槽=None):
    now = now or datetime.datetime.now()
    已执行槽 = 已执行槽 if 已执行槽 is not None else {}
    状态日志槽 = 状态日志槽 if 状态日志槽 is not None else {}
    results = []

    for strategy in 获取策略列表():
        strategy_id = strategy["id"]
        strategy_name = strategy.get("名称", strategy_id)
        if not strategy.get("启用", True):
            # 记录策略监控状态(
            #     strategy,
            #     now,
            #     "disabled",
            #     f"策略监控跳过：{strategy_name} id={strategy_id} 已停用",
            #     状态日志槽,
            # )
            continue
        if not 当前是策略监控时间(strategy, now):
            # 记录策略监控状态(
            #     strategy,
            #     now,
            #     "out_of_window",
            #     f"策略监控等待：{strategy_name} id={strategy_id} 当前={now.strftime('%Y-%m-%d %H:%M:%S')} "
            #     f"不在监控时间段 {格式化策略时间段(strategy)}",
            #     状态日志槽,
            # )
            continue

        current_slot = 策略执行槽(strategy, now)
        if 已执行槽.get(strategy_id) == current_slot:
            continue

        已执行槽[strategy_id] = current_slot
        logger.info(
            f"策略监控触发：{strategy_name} id={strategy_id} 当前={now.strftime('%Y-%m-%d %H:%M:%S')} "
            f"时间段={格式化策略时间段(strategy)} 频率={获取策略监控频率秒(strategy)}秒"
        )
        results.append(策略选股采集(strategy_id))
    return results


def 采集全部启用策略():
    results = []
    for strategy in 获取策略列表():
        if not strategy.get("启用", True):
            continue
        results.append(策略选股采集(strategy["id"]))
    return results


def 策略选股采集(strategy_id=None, 最大重试次数=None):
    strategy = 获取策略配置(strategy_id or 获取默认策略ID())
    最大重试次数 = 最大重试次数 or config.策略选股采集最大重试次数
    最后错误 = ""

    with 采集锁:
        for 当前次数 in range(1, 最大重试次数 + 1):
            try:
                return _单次策略选股采集(strategy)
            except Exception as e:
                最后错误 = str(e)
                if "浏览器未开启或已关闭" in 最后错误 or "与页面的连接已断开" in 最后错误:
                    logger.error(f"监测到策略选股浏览器页面异常，重新初始化页面。{e}")
                    try:
                        初始化策略页面(strategy)
                    except Exception as init_error:
                        最后错误 = f"{最后错误}; 重新初始化页面失败: {init_error}"
                else:
                    logger.error(f"{strategy.get('名称')} 采集异常，第 {当前次数}/{最大重试次数} 次: {e}")

                if 当前次数 < 最大重试次数:
                    time.sleep(0.5)

        return 写入失败快照(strategy, 最后错误 or "未获取到完整股票列表")


def _单次策略选股采集(strategy):
    current_time = datetime.datetime.now()
    current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
    timeout_seconds = config.策略选股采集超时秒

    logger.info(f"[{current_time_str}] 开始抓取策略选股：{strategy.get('名称')}...")

    page = 初始化策略页面(strategy)
    page.listen.start(strategy.get("监听目标") or ["/api/smart-tag/stock/v3/pw/search-code"])
    page.get(strategy["页面URL"], timeout=0)

    股票列表 = None
    for packet in page.listen.steps(timeout=timeout_seconds):
        try:
            response_body = packet.response.body
        except Exception:
            continue

        data = 解析响应体(response_body)
        if data is None:
            continue

        解析结果 = 解析策略选股接口响应(data)
        if 解析结果 is not None:
            股票列表 = 解析结果
            logger.info(f"{strategy.get('名称')} 接口命中: {packet.target}，股票数量 {len(股票列表)}")
            break

    if 股票列表 is None:
        raise TimeoutError(f"{timeout_seconds}秒内未获取到完整股票列表")

    return 写入成功快照(strategy, 股票列表)


def 初始化策略页面(strategy):
    return driver_chrome.初始化页面(
        f"策略选股:{strategy['id']}",
        strategy["页面URL"],
        background=True,
    )


def 写入成功快照(strategy, 股票列表):
    now = datetime.datetime.now()
    today = now.strftime("%Y%m%d")
    current_time_text = now.strftime("%H:%M:%S")
    current_datetime_text = now.strftime("%Y-%m-%d %H:%M:%S")
    strategy_id = strategy["id"]
    strategy_name = strategy.get("名称", strategy_id)

    previous_codes = set(db.redis_con_localhost.smembers(当前入选代码key(strategy_id)))
    selected_info = 读取json对象(当前入选信息key(strategy_id), {})

    股票列表 = 去重股票列表(股票列表)
    current_codes = {stock["代码"] for stock in 股票列表 if stock.get("代码")}
    stock_map = {stock["代码"]: stock for stock in 股票列表 if stock.get("代码")}

    new_codes = sorted(current_codes - previous_codes)
    removed_codes = sorted(previous_codes - current_codes)

    移除股票 = []
    for code in removed_codes:
        info = selected_info.pop(code, {}) if isinstance(selected_info, dict) else {}
        移除股票.append({
            "策略ID": strategy_id,
            "策略名称": strategy_name,
            "代码": code,
            "名称": info.get("名称", ""),
            "市场": info.get("市场", 推断市场(code, code)),
            "移除日期": today,
            "移除时间": current_time_text,
        })

    新增事件 = []
    for code in new_codes:
        stock = stock_map.get(code)
        if not stock:
            continue

        event = {
            "event_id": f"{today}-{current_time_text.replace(':', '')}-{strategy_id}-{code}",
            "策略ID": strategy_id,
            "策略名称": strategy_name,
            "入选日期": today,
            "入选时间": current_datetime_text,
            "入选时分秒": current_time_text,
            "代码": code,
            "名称": stock.get("名称", ""),
            "市场": stock.get("市场", 推断市场(code, code)),
            "字段": stock.get("字段", {}),
        }
        新增事件.append(event)
        selected_info[code] = {
            "event_id": event["event_id"],
            "入选日期": today,
            "入选时间": current_datetime_text,
            "入选时分秒": current_time_text,
            "代码": code,
            "名称": event["名称"],
            "市场": event["市场"],
        }

    for stock in 股票列表:
        info = selected_info.get(stock.get("代码"), {}) if isinstance(selected_info, dict) else {}
        stock["策略ID"] = strategy_id
        stock["策略名称"] = strategy_name
        stock["入选日期"] = info.get("入选日期", "")
        stock["入选时间"] = 格式化完整入选时间(info.get("入选日期", ""), info.get("入选时间", ""), info.get("入选时分秒", ""))
        stock["最新采集时间"] = current_datetime_text

    snapshot = {
        "策略ID": strategy_id,
        "策略名称": strategy_name,
        "采集日期": today,
        "采集时间": current_time_text,
        "状态": "success",
        "股票列表": 股票列表,
        "新增股票": 新增事件,
        "移除股票": 移除股票,
        "错误信息": "",
    }

    写入快照(strategy_id, snapshot, update_latest=True)
    写入入选事件(strategy_id, today, 新增事件)
    写入当前入选状态(strategy_id, current_codes, selected_info)

    logger.info(f"[{today} {current_time_text}] {strategy_name}采集成功，当前 {len(股票列表)} 只，新增 {len(新增事件)} 只，移除 {len(移除股票)} 只")
    推送策略更新(snapshot)
    return snapshot


def 写入失败快照(strategy, error_message):
    now = datetime.datetime.now()
    today = now.strftime("%Y%m%d")
    current_time_text = now.strftime("%H:%M:%S")
    current_datetime_text = now.strftime("%Y-%m-%d %H:%M:%S")
    strategy_id = strategy["id"]
    strategy_name = strategy.get("名称", strategy_id)
    snapshot = {
        "策略ID": strategy_id,
        "策略名称": strategy_name,
        "采集日期": today,
        "采集时间": current_time_text,
        "状态": "failed",
        "股票列表": [],
        "新增股票": [],
        "移除股票": [],
        "错误信息": error_message,
    }
    写入快照(strategy_id, snapshot, update_latest=False)
    logger.error(f"[{today} {current_time_text}] {strategy_name}采集失败: {error_message}")
    推送策略更新(snapshot)
    return snapshot


def 写入快照(strategy_id, snapshot, update_latest=False):
    today = snapshot.get("采集日期") or datetime.datetime.now().strftime("%Y%m%d")
    data = json.dumps(snapshot, ensure_ascii=False)
    db.redis_con_localhost.rpush(历史key(strategy_id, today), data)
    if update_latest:
        db.redis_con_localhost.set(最新快照key(strategy_id), data)


def 写入入选事件(strategy_id, today, events):
    if not events:
        return

    for event in events:
        data = json.dumps(event, ensure_ascii=False)
        db.redis_con_localhost.rpush(事件key(strategy_id, today), data)
        db.redis_con_localhost.rpush(f"{全局事件前缀}:{today}", data)
        db.redis_con_localhost.set(最后事件IDkey, event["event_id"])


def 写入当前入选状态(strategy_id, codes, selected_info):
    db.redis_con_localhost.delete(当前入选代码key(strategy_id))
    if codes:
        db.redis_con_localhost.sadd(当前入选代码key(strategy_id), *sorted(codes))
    db.redis_con_localhost.set(当前入选信息key(strategy_id), json.dumps(selected_info, ensure_ascii=False))


def 格式化完整入选时间(date_text, time_text, time_of_day_text=""):
    time_text = str(time_text or "").strip()
    time_of_day_text = str(time_of_day_text or "").strip()
    date_text = str(date_text or "").strip()
    if not time_text and time_of_day_text:
        time_text = time_of_day_text
    if not time_text:
        return ""

    if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$", time_text):
        return time_text
    if re.match(r"^\d{8}\s+\d{2}:\d{2}:\d{2}$", time_text):
        return f"{time_text[:4]}-{time_text[4:6]}-{time_text[6:8]} {time_text[9:]}"
    if re.match(r"^\d{2}:\d{2}:\d{2}$", time_text):
        if re.match(r"^\d{8}$", date_text):
            return f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:8]} {time_text}"
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_text):
            return f"{date_text} {time_text}"
    return time_text


def 补全事件时间(event):
    if isinstance(event, dict):
        event["入选时间"] = 格式化完整入选时间(
            event.get("入选日期", ""),
            event.get("入选时间", ""),
            event.get("入选时分秒", ""),
        )
        event["字段"] = 清洗策略选股字段(event.get("字段", {}))
    return event


def 补全快照时间(snapshot):
    if not isinstance(snapshot, dict):
        return snapshot

    for stock in snapshot.get("股票列表") or []:
        if isinstance(stock, dict):
            stock["入选时间"] = 格式化完整入选时间(
                stock.get("入选日期", ""),
                stock.get("入选时间", ""),
                stock.get("入选时分秒", ""),
            )
            stock["字段"] = 清洗策略选股字段(stock.get("字段", {}))
    for event in snapshot.get("新增股票") or []:
        补全事件时间(event)
    return snapshot


def 读取最新快照(strategy_id):
    获取策略配置(strategy_id)
    return 补全快照时间(读取json对象(最新快照key(strategy_id), {}))


def 读取快照历史(strategy_id, date):
    获取策略配置(strategy_id)
    return [补全快照时间(item) for item in 读取json列表(历史key(strategy_id, date))]


def 读取入选事件(strategy_id, date):
    获取策略配置(strategy_id)
    return [补全事件时间(item) for item in 读取json列表(事件key(strategy_id, date))]


def 读取全局入选事件(date):
    return [补全事件时间(item) for item in 读取json列表(f"{全局事件前缀}:{date}")]


def 获取策略选股日期列表(strategy_id=None):
    dates = set()
    if strategy_id:
        获取策略配置(strategy_id)
        patterns = [f"策略选股:{strategy_id}:history:*", f"策略选股:{strategy_id}:events:*"]
    else:
        patterns = ["策略选股:*:history:*", "策略选股:*:events:*", f"{全局事件前缀}:*"]

    for pattern in patterns:
        for key in db.redis_con_localhost.keys(pattern):
            parts = key.split(":")
            if parts:
                dates.add(parts[-1])
    return sorted(dates, reverse=True)


def 初始化策略配置():
    strategies = 读取json对象(策略配置key, None)
    if isinstance(strategies, list) and strategies:
        default_map = {item["id"]: item for item in 获取默认策略列表()}
        normalized = []
        for item in strategies:
            if not isinstance(item, dict):
                continue
            base = default_map.get(item.get("id"), {})
            normalized_item = 标准化策略配置({**base, **item})
            if normalized_item:
                normalized.append(normalized_item)
        if normalized:
            normalized = 确保策略ID唯一(normalized)
            保存策略列表(normalized)
            return normalized

    default_strategies = 获取默认策略列表()
    保存策略列表(default_strategies)
    if default_strategies:
        迁移默认策略旧状态(default_strategies[0]["id"])
    return default_strategies


def 获取默认策略列表():
    strategies = []
    for item in config.默认策略选股列表:
        if not isinstance(item, dict):
            continue
        strategies.append(标准化策略配置(item))
    return 确保策略ID唯一(strategies)


def 确保策略ID唯一(strategies):
    used_ids = set()
    unique_strategies = []
    for index, strategy in enumerate(strategies, start=1):
        if not isinstance(strategy, dict):
            continue
        item = dict(strategy)
        old_id = str(item.get("id") or "").strip()
        base_id = 标准化策略ID(old_id) or 默认策略ID
        unique_id = 生成唯一策略ID(base_id, item, used_ids, index)
        if unique_id != old_id:
            warning_key = (item.get("名称", ""), old_id, unique_id)
            if warning_key not in 策略ID自动调整提示:
                策略ID自动调整提示.add(warning_key)
                logger.warning(f"策略ID重复或无效，已自动调整：{item.get('名称', '')} {old_id} -> {unique_id}")
        item["id"] = unique_id
        used_ids.add(unique_id)
        unique_strategies.append(item)
    return unique_strategies


def 生成唯一策略ID(base_id, strategy, used_ids, index):
    base_id = 标准化策略ID(base_id) or 默认策略ID
    if base_id not in used_ids:
        return base_id

    candidates = []
    page_strategy_id = 提取东方财富策略页面ID(strategy.get("页面URL", ""))
    if page_strategy_id:
        candidates.append(f"{base_id}_{page_strategy_id}")

    name_id = 标准化策略ID(strategy.get("名称", ""))
    if name_id:
        candidates.append(f"{base_id}_{name_id}")

    candidates.append(f"{base_id}_{index}")
    for candidate in candidates:
        strategy_id = 标准化策略ID(candidate)
        if strategy_id and strategy_id not in used_ids:
            return strategy_id

    counter = 2
    while True:
        suffix = f"_{counter}"
        strategy_id = f"{base_id[:64 - len(suffix)]}{suffix}"
        if strategy_id not in used_ids:
            return strategy_id
        counter += 1


def 提取东方财富策略页面ID(url):
    match = re.search(r"[?&]id=([^&#]+)", str(url or ""))
    if not match:
        return ""
    return 标准化策略ID(match.group(1))


def 获取策略列表():
    return 初始化策略配置()


def 保存策略列表(strategies):
    db.redis_con_localhost.set(策略配置key, json.dumps(strategies, ensure_ascii=False))


def 获取默认策略ID():
    strategies = 获取策略列表()
    enabled = [item for item in strategies if item.get("启用", True)]
    return (enabled or strategies)[0]["id"]


def 获取策略配置(strategy_id):
    for strategy in 获取策略列表():
        if strategy.get("id") == strategy_id:
            return strategy
    raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_id}")


def 新增策略(payload):
    strategies = 获取策略列表()
    strategy = 标准化策略配置(payload, allow_new_id=True)
    if any(item["id"] == strategy["id"] for item in strategies):
        raise HTTPException(status_code=400, detail=f"策略ID已存在: {strategy['id']}")
    now_text = 当前时间文本()
    strategy["创建时间"] = now_text
    strategy["更新时间"] = now_text
    strategies.append(strategy)
    保存策略列表(strategies)
    return strategy


def 更新策略(strategy_id, payload):
    strategies = 获取策略列表()
    updated = None
    for index, strategy in enumerate(strategies):
        if strategy["id"] != strategy_id:
            continue
        merged = {**strategy, **payload, "id": strategy_id}
        updated = 标准化策略配置(merged)
        updated["创建时间"] = strategy.get("创建时间", "")
        updated["更新时间"] = 当前时间文本()
        strategies[index] = updated
        break
    if updated is None:
        raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_id}")
    保存策略列表(strategies)
    return updated


def 删除策略(strategy_id):
    strategies = 获取策略列表()
    filtered = [item for item in strategies if item["id"] != strategy_id]
    if len(filtered) == len(strategies):
        raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_id}")
    if not filtered:
        raise HTTPException(status_code=400, detail="至少保留一个策略")
    保存策略列表(filtered)
    return {"deleted": strategy_id}


def 标准化策略配置(payload, allow_new_id=False):
    raw_id = str(payload.get("id") or "").strip()
    strategy_id = 标准化策略ID(raw_id) if raw_id else ""
    if not strategy_id and allow_new_id:
        strategy_id = f"strategy_{uuid.uuid4().hex[:8]}"
    if not strategy_id:
        strategy_id = 默认策略ID

    name = str(payload.get("名称") or payload.get("name") or "").strip()
    if not name:
        name = 默认策略名称 if strategy_id == 默认策略ID else strategy_id

    url = str(payload.get("页面URL") or payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="页面URL不能为空")

    targets = payload.get("监听目标", payload.get("targets", []))
    monitor_periods = payload.get("监控时间段", payload.get("monitorPeriods", []))
    monitor_interval = payload.get("监控频率秒", payload.get("monitorIntervalSeconds", 60))
    normalized = {
        "id": strategy_id,
        "名称": name,
        "页面URL": url,
        "监听目标": 标准化监听目标(targets),
        "监控时间段": 标准化监控时间段配置(monitor_periods),
        "监控频率秒": 标准化监控频率秒(monitor_interval),
        "启用": bool(payload.get("启用", payload.get("enabled", True))),
        "创建时间": payload.get("创建时间", ""),
        "更新时间": payload.get("更新时间", ""),
    }
    return normalized


def 标准化策略ID(value):
    value = re.sub(r"[^0-9A-Za-z_-]", "_", str(value or "").strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:64]


def 标准化监听目标(targets):
    if isinstance(targets, str):
        targets = [line.strip() for line in re.split(r"[\r\n,]", targets) if line.strip()]
    elif isinstance(targets, (list, tuple)):
        targets = [str(item).strip() for item in targets if str(item).strip()]
    else:
        targets = []
    return targets or ["/api/smart-tag/stock/v3/pw/search-code"]


def 标准化监控频率秒(value):
    try:
        interval = int(value)
        if interval > 0:
            return interval
    except (TypeError, ValueError):
        pass
    return 60


def 标准化监控时间段配置(periods):
    normalized = []
    for start, end in 标准化监控时间段(periods):
        normalized.append([start.strftime("%H:%M"), end.strftime("%H:%M")])
    return normalized or [[start.strftime("%H:%M"), end.strftime("%H:%M")] for start, end in 默认策略监控时间段]


def 标准化监控时间段(periods):
    if not periods:
        return list(默认策略监控时间段)

    if isinstance(periods, str):
        raw_items = [item.strip() for item in re.split(r"[\r\n,;]", periods) if item.strip()]
    elif isinstance(periods, (list, tuple)):
        raw_items = list(periods)
    else:
        raw_items = []

    result = []
    for item in raw_items:
        start_text = ""
        end_text = ""
        if isinstance(item, str):
            parts = [part.strip() for part in re.split(r"~|-", item, maxsplit=1) if part.strip()]
            if len(parts) == 2:
                start_text, end_text = parts
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            start_text, end_text = str(item[0]).strip(), str(item[1]).strip()
        elif isinstance(item, dict):
            start_text = str(item.get("start") or item.get("开始") or item.get("开始时间") or "").strip()
            end_text = str(item.get("end") or item.get("结束") or item.get("结束时间") or "").strip()

        start_time = 解析监控时间(start_text)
        end_time = 解析监控时间(end_text)
        if start_time and end_time and start_time <= end_time:
            result.append((start_time, end_time))

    return result or list(默认策略监控时间段)


def 解析监控时间(value):
    value = str(value or "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def 当前时间文本():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def 迁移默认策略旧状态(strategy_id):
    try:
        old_codes = set(db.redis_con_localhost.smembers("策略选股:selected_codes"))
        new_codes = set(db.redis_con_localhost.smembers(当前入选代码key(strategy_id)))
        if old_codes and not new_codes:
            db.redis_con_localhost.sadd(当前入选代码key(strategy_id), *sorted(old_codes))

        old_info = db.redis_con_localhost.get("策略选股:selected_info")
        new_info = db.redis_con_localhost.get(当前入选信息key(strategy_id))
        if old_info and not new_info:
            db.redis_con_localhost.set(当前入选信息key(strategy_id), old_info)

        old_latest = db.redis_con_localhost.get("策略选股:latest")
        new_latest = db.redis_con_localhost.get(最新快照key(strategy_id))
        if old_latest and not new_latest:
            db.redis_con_localhost.set(最新快照key(strategy_id), old_latest)
    except Exception as e:
        logger.warning(f"迁移默认策略旧状态失败: {e}")


def 策略redis前缀(strategy_id):
    return f"策略选股:{strategy_id}"


def 最新快照key(strategy_id):
    return f"{策略redis前缀(strategy_id)}:latest"


def 历史key(strategy_id, date):
    return f"{策略redis前缀(strategy_id)}:history:{date}"


def 事件key(strategy_id, date):
    return f"{策略redis前缀(strategy_id)}:events:{date}"


def 当前入选代码key(strategy_id):
    return f"{策略redis前缀(strategy_id)}:selected_codes"


def 当前入选信息key(strategy_id):
    return f"{策略redis前缀(strategy_id)}:selected_info"


def 读取json对象(key, default):
    value = db.redis_con_localhost.get(key)
    if not value:
        return default
    try:
        parsed = json.loads(value)
        if default is None:
            return parsed
        return parsed if isinstance(parsed, type(default)) else default
    except Exception:
        return default


def 读取json列表(key):
    result = []
    for item in db.redis_con_localhost.lrange(key, 0, -1):
        try:
            result.append(json.loads(item))
        except Exception:
            continue
    return result


def 解析响应体(body):
    if isinstance(body, (dict, list)):
        return body
    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8")
        except Exception:
            return None
    if not isinstance(body, str):
        return None

    text = body.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    left = text.find("(")
    right = text.rfind(")")
    if left >= 0 and right > left:
        json_text = text[left + 1:right]
        try:
            return json.loads(json_text)
        except Exception:
            return None
    return None


def 解析策略选股接口响应(data):
    if not isinstance(data, dict):
        return None

    result = data.get("data", {}).get("result", {})
    if not isinstance(result, dict) or "dataList" not in result:
        return None

    rows = result.get("dataList")
    if not isinstance(rows, list):
        return None

    columns = result.get("columns") or []
    column_map = 构建列定义映射(columns)
    stocks = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        stock = 标准化策略选股行(row, column_map)
        if stock:
            stocks.append(stock)
    return 去重股票列表(stocks)


def 构建列定义映射(columns):
    column_map = {}
    if not isinstance(columns, list):
        return column_map

    for column in columns:
        if not isinstance(column, dict):
            continue
        key = column.get("key")
        if key:
            column_map[key] = column
    return column_map


def 标准化策略选股行(row, column_map):
    code = 规范股票代码(row.get("SECURITY_CODE", ""))
    name = str(row.get("SECURITY_SHORT_NAME", "") or "").strip()
    if not code or not name:
        return None

    raw_market = row.get("MARKET_SHORT_NAME") or row.get("TRADEMARKET") or row.get("MARKET_NUM") or code
    return {
        "代码": code,
        "名称": name,
        "市场": 取策略选股市场(raw_market, code),
        "字段": 构建策略选股展示字段(row, column_map),
    }


def 取策略选股市场(raw_market, code):
    text = str(raw_market or "").upper()
    if "SH" in text or "上交" in text or text == "1":
        return "SH"
    if "SZ" in text or "深交" in text or text == "0":
        return "SZ"
    if "BJ" in text or "北交" in text or text == "2":
        return "BJ"
    return 推断市场(raw_market or code, code)


def 清洗策略选股字段(fields):
    if not isinstance(fields, dict):
        return {}

    cleaned = {}
    for key, value in fields.items():
        if 是东方财富概念字段(key):
            value = 格式化东方财富概念(value)
            if not value:
                continue
        cleaned[key] = value
    return cleaned


def 是东方财富概念字段(key):
    text = str(key or "").replace(" ", "").upper()
    return "概念" in text or "CONCEPT" in text

def 格式化东方财富概念(value):
    concepts = []
    for item in 拆分东方财富概念(value):
        name = 标准化东方财富概念名称(item)
        if not name or name == "概念" or 东方财富概念已排除(name):
            continue
        if name not in concepts:
            concepts.append(name)
    return "、".join(concepts)


def 拆分东方财富概念(value):
    if isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        text = str(value or "").strip()
        if not text:
            return []
        bracket_matches = re.findall(r"【([^】]+)】", text)
        raw_items = bracket_matches if bracket_matches else re.split(r"[、,，;；\s]+", text)
    return [item for item in raw_items if str(item or "").strip()]


def 获取东方财富概念排除名单():
    return {
        标准化东方财富概念匹配值(item)
        for item in getattr(config, "东方财富概念排除名单", [])
        if 标准化东方财富概念匹配值(item)
    }


def 标准化东方财富概念名称(value):
    return str(value or "").strip().strip("【】[]")


def 标准化东方财富概念匹配值(value):
    return re.sub(r"[\s_＿\-]+", "", 标准化东方财富概念名称(value)).upper()


def 东方财富概念已排除(value):
    name = 标准化东方财富概念匹配值(value)
    if not name:
        return False

    excluded = 获取东方财富概念排除名单()
    if name in excluded:
        return True

    if re.match(r"^20\d{2}(年报|一季报|半年报|三季报)(预增|扭亏|预亏|预减|高增长)$", name):
        return True
    return False

def 构建策略选股展示字段(row, column_map):
    ignored_keys = {"SERIAL", "SECURITY_CODE", "SECURITY_SHORT_NAME", "MARKET_SHORT_NAME", "MARKET_NUM"}
    fields = {}
    used_labels = set()

    for key, column in column_map.items():
        if key in ignored_keys or key not in row:
            continue
        value = row.get(key)
        if value in (None, ""):
            continue

        label = column.get("title") or key
        if label in used_labels:
            label = f"{label}({key})"
        used_labels.add(label)
        fields[label] = value

    for key, value in row.items():
        if key in ignored_keys or key in column_map or value in (None, ""):
            continue
        fields[str(key)] = value

    return 清洗策略选股字段(fields)


def 推断市场(raw_code, code):
    raw_text = str(raw_code).upper()
    if "SH" in raw_text or raw_text.startswith("1.") or code.startswith("6"):
        return "SH"
    if "BJ" in raw_text or raw_text.startswith("2.") or code.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def 规范股票代码(raw_code):
    match = re.search(r"\d{6}", str(raw_code))
    return match.group(0) if match else ""


def 去重股票列表(records):
    seen = set()
    result = []
    for record in records:
        code = record.get("代码")
        if not code or code in seen:
            continue
        seen.add(code)
        result.append(record)
    return result


if __name__ == "__main__":
    采集全部启用策略()
