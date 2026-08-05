import datetime
import json
import os
import sys

项目根目录 = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if 项目根目录 not in sys.path:
    sys.path.append(项目根目录)

from utils import db
from 实时监控 import 资金流向


情绪周期接口路径前缀 = "/api/emotion"
普通主板股票SQL = """
(
    (
        (ts_code BETWEEN 1 AND 3999)
        OR (ts_code BETWEEN 600000 AND 609999)
    )
    AND (stock_name IS NULL OR stock_name NOT LIKE '%ST%')
)
"""
涨跌停幅度SQL = """
0.10
"""


def 注册接口(app):
    @app.get(f"{情绪周期接口路径前缀}/current")
    def get_current_emotion_cycle():
        return 计算当前情绪周期()

    @app.get(f"{情绪周期接口路径前缀}/index/current")
    def get_current_index_cycle():
        return 计算当前指数周期()

    @app.get(f"{情绪周期接口路径前缀}/topic/current")
    def get_current_topic_cycle():
        return 计算主力题材周期()


def 计算当前情绪周期():
    指数周期 = 计算当前指数周期()
    if 指数周期.get("状态") != "success":
        return {
            "状态": 指数周期.get("状态", "empty"),
            "错误信息": 指数周期.get("错误信息", "暂无指数情绪周期落库数据"),
            "指数周期": 指数周期,
        }
    return {
        "状态": "success",
        "指数周期": 指数周期,
    }


def 计算当前指数周期():
    result = 读取最新指数周期落库结果()
    if result:
        return result
    return {"状态": "empty", "错误信息": "暂无指数情绪周期落库数据，请先执行每日更新"}


def 读取最新指数周期落库结果():
    try:
        exists = db.mysql_localhost(
            "SHOW TABLES LIKE 't_指数情绪周期_每日分析'",
            fetch=True,
        )
        if not exists:
            return None

        rows = db.mysql_localhost(
            """
            SELECT
                `日期`, `指数名称`, `周期状态`, `周期分数`, `摘要`,
                `开盘`, `收盘`, `最高`, `最低`, `涨跌幅`, `指数成交额`, `指数成交额比例`, `市场成交额比例`,
                `MA5`, `MA10`, `MA20`, `MA60`, `MA5斜率`, `MA10斜率`, `MA20斜率`,
                `趋势得分`, `市场宽度得分`, `涨跌停结构得分`, `量能得分`, `风险偏好得分`,
                `市场宽度JSON`, `信号JSON`, `最近走势JSON`, `波动图JSON`, `完整结果JSON`
            FROM `t_指数情绪周期_每日分析`
            ORDER BY `日期` DESC
            LIMIT 1
            """,
            fetch=True,
        )
    except Exception:
        return None

    if not rows:
        return None
    return 转换指数周期落库行(rows[0])


def 转换指数周期落库行(row):
    raw = 解析JSON字段(row.get("完整结果JSON"), {})
    if isinstance(raw, dict) and raw:
        raw["状态"] = raw.get("状态") or "success"
        return raw

    最近走势 = 补充最近走势市场宽度(row.get("日期"), 解析JSON字段(row.get("最近走势JSON"), []))
    市场宽度 = 解析JSON字段(row.get("市场宽度JSON"), {})
    if 最近走势:
        最新市场 = 最近走势[-1]
        市场宽度.update({
            "股票总数": 最新市场.get("股票总数"),
            "上涨家数": 最新市场.get("上涨家数"),
            "下跌家数": 最新市场.get("下跌家数"),
            "上涨占比": 最新市场.get("上涨占比"),
            "涨停家数": 最新市场.get("涨停家数", 最新市场.get("涨停")),
            "跌停家数": 最新市场.get("跌停家数", 最新市场.get("跌停")),
        })

    return {
        "状态": "success",
        "指数名称": row.get("指数名称", "上证指数"),
        "交易日期": 取整数(row.get("日期")),
        "周期状态": row.get("周期状态", ""),
        "周期分数": 保留小数(row.get("周期分数"), 1),
        "摘要": row.get("摘要", ""),
        "指数": {
            "开盘": 保留小数(row.get("开盘"), 2),
            "收盘": 保留小数(row.get("收盘"), 2),
            "最高": 保留小数(row.get("最高"), 2),
            "最低": 保留小数(row.get("最低"), 2),
            "涨跌幅": 保留小数(row.get("涨跌幅"), 2),
            "成交额": 保留小数(row.get("指数成交额"), 2),
            "指数成交额比例": 保留小数(row.get("指数成交额比例"), 2),
        },
        "均线": {
            "MA5": 保留小数(row.get("MA5"), 2),
            "MA10": 保留小数(row.get("MA10"), 2),
            "MA20": 保留小数(row.get("MA20"), 2),
            "MA60": 保留小数(row.get("MA60"), 2),
        },
        "均线斜率": {
            "MA5": 保留小数(row.get("MA5斜率"), 2),
            "MA10": 保留小数(row.get("MA10斜率"), 2),
            "MA20": 保留小数(row.get("MA20斜率"), 2),
        },
        "市场宽度": 市场宽度,
        "分项得分": {
            "趋势": 保留小数(row.get("趋势得分"), 1),
            "市场宽度": 保留小数(row.get("市场宽度得分"), 1),
            "涨跌停结构": 保留小数(row.get("涨跌停结构得分"), 1),
            "量能": 保留小数(row.get("量能得分"), 1),
            "风险偏好": 保留小数(row.get("风险偏好得分"), 1),
        },
        "信号": 解析JSON字段(row.get("信号JSON"), []),
        "最近走势": 最近走势,
        "波动图": 解析JSON字段(row.get("波动图JSON"), []),
    }



def 补充最近走势市场宽度(latest_date, recent_rows, limit=20):
    if not latest_date:
        return recent_rows or []

    try:
        rows = db.mysql_localhost(
            f"""
            SELECT
                trade_date AS `日期`,
                COUNT(*) AS `股票总数`,
                SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) AS `上涨家数`,
                SUM(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) AS `下跌家数`,
                SUM(CASE WHEN ({普通主板股票SQL}) AND pre_close > 0 AND close >= ROUND(pre_close * (1 + ({涨跌停幅度SQL})), 2) THEN 1 ELSE 0 END) AS `涨停家数`,
                SUM(CASE WHEN ({普通主板股票SQL}) AND pre_close > 0 AND close <= ROUND(pre_close * (1 - ({涨跌停幅度SQL})), 2) THEN 1 ELSE 0 END) AS `跌停家数`
            FROM stock_daily
            WHERE trade_date IN (
                SELECT trade_date FROM (
                    SELECT DISTINCT trade_date
                    FROM stock_daily
                    WHERE trade_date <= %s
                    ORDER BY trade_date DESC
                    LIMIT {int(limit)}
                ) recent_dates
            )
            GROUP BY trade_date
            ORDER BY trade_date ASC
            """,
            params=(取整数(latest_date),),
            fetch=True,
        )
    except Exception:
        return recent_rows or []

    if not rows:
        return recent_rows or []

    recent_map = {取整数(row.get("日期")): dict(row) for row in recent_rows or [] if row.get("日期")}
    for row in rows:
        date = 取整数(row.get("日期"))
        total = max(取整数(row.get("股票总数")), 1)
        item = recent_map.get(date, {"日期": date})
        item.update({
            "股票总数": 取整数(row.get("股票总数")),
            "上涨家数": 取整数(row.get("上涨家数")),
            "下跌家数": 取整数(row.get("下跌家数")),
            "上涨占比": 保留小数(取整数(row.get("上涨家数")) / total * 100, 1),
            "涨停": 取整数(row.get("涨停家数")),
            "跌停": 取整数(row.get("跌停家数")),
            "涨停家数": 取整数(row.get("涨停家数")),
            "跌停家数": 取整数(row.get("跌停家数")),
        })
        recent_map[date] = item

    return [recent_map[date] for date in sorted(recent_map.keys())][-int(limit):]

def 解析JSON字段(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def 实时计算当前指数周期():
    index_rows = 读取上证指数日线()
    if not index_rows:
        return {"状态": "empty", "错误信息": "akshare_sh000001 暂无指数数据"}

    market_rows = 读取市场宽度数据()
    return 计算指数周期结果(index_rows, market_rows)


def 计算指数周期结果(index_rows, market_rows):
    if not index_rows:
        return {"状态": "empty", "错误信息": "akshare_sh000001 暂无指数数据"}

    closes = [取浮点数(row.get("收盘")) for row in index_rows]
    amounts = [取浮点数(row.get("成交额")) for row in index_rows]
    latest_index = index_rows[-1]
    latest_date = int(latest_index.get("日期") or 0)
    latest_market = 匹配市场宽度(market_rows, latest_date)

    ma = {
        "MA5": 均线(closes, 5),
        "MA10": 均线(closes, 10),
        "MA20": 均线(closes, 20),
        "MA60": 均线(closes, 60),
    }
    ma_slope = {
        "MA5": 均线斜率(closes, 5, 3),
        "MA10": 均线斜率(closes, 10, 5),
        "MA20": 均线斜率(closes, 20, 5),
    }

    close = 取浮点数(latest_index.get("收盘"))
    index_amount_ratio = 比值(取浮点数(latest_index.get("成交额")), 平均值(amounts[-20:]))
    market_amount_ratio = 计算市场成交额比例(market_rows, latest_market)

    score_parts = 计算指数情绪分项(close, ma, ma_slope, latest_market, index_amount_ratio, market_amount_ratio)
    total_score = round(sum(score_parts.values()), 1)
    cycle_state = 判断指数周期(total_score, close, ma, ma_slope, latest_market)

    return {
        "状态": "success",
        "指数名称": "上证指数",
        "交易日期": latest_date,
        "周期状态": cycle_state,
        "周期分数": total_score,
        "摘要": 生成摘要(cycle_state, total_score, close, ma, latest_market),
        "指数": {
            "开盘": 保留小数(latest_index.get("开盘"), 2),
            "收盘": 保留小数(latest_index.get("收盘"), 2),
            "最高": 保留小数(latest_index.get("最高"), 2),
            "最低": 保留小数(latest_index.get("最低"), 2),
            "涨跌幅": 保留小数(latest_index.get("涨跌幅"), 2),
            "成交额": 保留小数(latest_index.get("成交额"), 2),
            "指数成交额比例": 保留小数(index_amount_ratio, 2),
        },
        "均线": {key: 保留小数(value, 2) for key, value in ma.items()},
        "均线斜率": {key: 保留小数(value, 2) for key, value in ma_slope.items()},
        "市场宽度": 格式化市场宽度(latest_market, market_amount_ratio),
        "分项得分": {key: 保留小数(value, 1) for key, value in score_parts.items()},
        "信号": 生成信号(close, ma, ma_slope, latest_market, index_amount_ratio, market_amount_ratio),
        "最近走势": 生成最近走势(index_rows, market_rows),
        "波动图": 生成指数周期波动图(index_rows, market_rows),
    }


def 计算主力题材周期(limit=8):
    date = 获取最新板块资金流向日期()
    if not date:
        return {"状态": "empty", "错误信息": "暂无板块资金流向数据", "题材列表": []}

    history = 读取最近板块资金流向矩阵(date)
    times = history.get("times") or []
    boards = history.get("boards") or []
    if not times or not boards:
        return {"状态": "empty", "交易日期": date, "错误信息": "板块资金流向暂无有效快照", "题材列表": []}

    candidate_board_info = 获取近一月日内强流入板块信息()
    candidate_boards = set(candidate_board_info.keys())
    boards = [board for board in boards if board.get("name") in candidate_boards]
    latest_values = [最近有效值([规范题材资金净流入值(value) for value in (board.get("values") or [])]) for board in boards]
    max_positive = max([value for value in latest_values if value and value > 0] or [1])

    topic_cycles = []
    for board in boards:
        topic = 计算单个题材周期(board, times, max_positive)
        if topic and topic.get("最新净流入", 0) > 0:
            topic_cycles.append(topic)

    topic_cycles.sort(key=lambda item: (item.get("周期分数", 0), item.get("最新净流入", 0)), reverse=True)
    topic_cycles = topic_cycles[:limit]
    strongest = topic_cycles[0] if topic_cycles else {}
    board_state = 计算板块每日情绪周期状态(candidate_boards=candidate_boards, candidate_board_info=candidate_board_info)

    return {
        "状态": "success",
        "交易日期": date,
        "最新时间": times[-1] if times else "",
        "题材数量": len(topic_cycles),
        "最强题材": strongest.get("题材名称", ""),
        "摘要": 生成题材周期摘要(topic_cycles, date, times[-1] if times else ""),
        "题材列表": topic_cycles,
        "板块周期状态日期列表": board_state.get("日期列表", []),
        "板块周期状态列表": board_state.get("板块列表", []),
    }


def 计算单个题材周期(board, times, max_positive):
    values = [规范题材资金净流入值(value) for value in (board.get("values") or [])]
    leaders = board.get("leaders") or []
    if not values:
        return None

    latest_value = 最近有效值(values)
    if latest_value is None:
        return None

    recent_values = [value for value in values[-30:] if value is not None]
    if not recent_values:
        return None

    first_value = recent_values[0]
    positive_count = sum(1 for value in recent_values if value > 0)
    valid_count = len(recent_values)
    latest_leader = 最近有效值(leaders) or ""
    slope = latest_value - first_value

    flow_score = 限制(max(latest_value, 0) / max(max_positive, 1) * 35, 0, 35)
    persistence_score = 限制(positive_count / max(valid_count, 1) * 25, 0, 25)
    slope_score = 限制(10 + slope / max(abs(first_value), max_positive, 1) * 25, 0, 20)
    activity_score = 限制(valid_count / 30 * 20, 0, 20)
    total_score = round(flow_score + persistence_score + slope_score + activity_score, 1)
    cycle_state = 判断题材周期(total_score, latest_value, slope, positive_count / max(valid_count, 1))

    return {
        "题材代码": board.get("code", ""),
        "题材名称": board.get("name", ""),
        "周期状态": cycle_state,
        "周期分数": total_score,
        "最新净流入": 保留小数(latest_value, 2),
        "资金斜率": 保留小数(slope, 2),
        "持续性": 保留小数(positive_count / max(valid_count, 1) * 100, 1),
        "活跃度": 保留小数(valid_count / 30 * 100, 1),
        "龙头": latest_leader,
        "分项得分": {
            "资金强度": 保留小数(flow_score, 1),
            "持续性": 保留小数(persistence_score, 1),
            "斜率": 保留小数(slope_score, 1),
            "活跃度": 保留小数(activity_score, 1),
        },
        "波动图": 生成题材波动图(times, values, max_positive),
    }


def 读取最近板块资金流向矩阵(date, snapshot_limit=120):
    key = f"fund_flow:history:{date}"
    items = db.redis_con_localhost.lrange(key, -int(snapshot_limit), -1)
    snapshots = []
    for item in items:
        try:
            snapshot = json.loads(item)
        except Exception:
            continue
        if not isinstance(snapshot, list) or not snapshot:
            continue
        if snapshot:
            snapshots.append(snapshot)
    return 资金流向.压缩资金流向历史数据(snapshots, top_n=0)


def 获取最新板块资金流向日期():
    dates = 资金流向.获取资金流向日期列表("fund_flow")
    return dates[0] if dates else ""

def 获取最近板块资金流向日期列表(limit=20):
    limit = max(int(limit), 1)
    dates = 资金流向.获取资金流向日期列表("fund_flow")
    latest_fund_date = dates[0] if dates else ""
    today = datetime.datetime.now().strftime("%Y%m%d")
    include_live_date = latest_fund_date == today and 当前日期是工作日(today)
    trade_dates = 获取指数交易日期集合(max(limit * 3, 80))
    if trade_dates:
        dates = [
            date for date in dates
            if date in trade_dates or (include_live_date and date == latest_fund_date)
        ]
    dates = dates[:limit]
    return list(reversed(dates))


def 当前日期是工作日(date):
    try:
        return datetime.datetime.strptime(str(date), "%Y%m%d").weekday() < 5
    except ValueError:
        return False


def 获取指数交易日期集合(limit=120):
    rows = db.mysql_localhost(
        f"""
        SELECT 日期
        FROM akshare_sh000001
        ORDER BY 日期 DESC
        LIMIT {int(limit)}
        """,
        fetch=True,
    )
    return {str(row.get("日期")) for row in rows or [] if row.get("日期")}


def 获取近一月日内强流入板块集合(threshold=50, days=31):
    return set(获取近一月日内强流入板块信息(threshold, days).keys())


def 获取近一月日内强流入板块信息(threshold=50, days=31):
    dates = 资金流向.获取资金流向日期列表("fund_flow")
    if not dates:
        return {}

    latest_date = dates[0]
    try:
        start_date = (
            datetime.datetime.strptime(latest_date, "%Y%m%d")
            - datetime.timedelta(days=int(days))
        ).strftime("%Y%m%d")
    except ValueError:
        return {}

    cache_key = f"emotion:board_filter:strong_inflow:v3:{latest_date}:{int(threshold)}:{int(days)}"
    try:
        cached = db.redis_con_localhost.get(cache_key)
        if cached:
            data = json.loads(cached)
            return data if isinstance(data, dict) else {}
    except Exception:
        pass

    candidates = {}
    target_dates = [date for date in dates if start_date <= date <= latest_date]
    for date in target_dates:
        snapshot = 读取板块资金流向收盘快照(date)
        for row in snapshot:
            name = row.get("板块名称")
            if not name:
                continue
            value = 规范题材资金净流入值(row.get("资金净流入(亿)"))
            if value is None or value <= threshold:
                continue

            current_time = row.get("时间", "")
            info = candidates.get(name)
            if info is None:
                info = {
                    "最近触发日期": date,
                    "最近触发时间": current_time,
                    "最近触发净流入": 保留小数(value, 2),
                    "近一月最大净流入": 保留小数(value, 2),
                    "近一月最大日期": date,
                    "近一月最大时间": current_time,
                }
                candidates[name] = info
                continue

            if date >= info.get("最近触发日期", ""):
                info["最近触发日期"] = date
                info["最近触发时间"] = current_time
                info["最近触发净流入"] = 保留小数(value, 2)

            if value > 取浮点数(info.get("近一月最大净流入")):
                info["近一月最大净流入"] = 保留小数(value, 2)
                info["近一月最大日期"] = date
                info["近一月最大时间"] = current_time

    try:
        db.redis_con_localhost.setex(cache_key, 60, json.dumps(candidates, ensure_ascii=False))
    except Exception:
        pass
    return candidates


def 读取板块资金流向收盘快照(date):
    key = f"fund_flow:history:{date}"
    items = db.redis_con_localhost.lrange(key, -10, -1)
    for item in reversed(items or []):
        try:
            snapshot = json.loads(item)
        except Exception:
            continue
        if isinstance(snapshot, list) and snapshot:
            return snapshot
    return []


def 计算板块每日情绪周期状态(date_limit=20, candidate_boards=None, candidate_board_info=None):
    if candidate_board_info is None:
        candidate_board_info = 获取近一月日内强流入板块信息()
    if candidate_boards is None:
        candidate_boards = set(candidate_board_info.keys())
    date_snapshots = []
    for date in 获取最近板块资金流向日期列表(date_limit):
        snapshot = 读取板块资金流向收盘快照(date)
        if snapshot:
            date_snapshots.append((date, snapshot))

    if not date_snapshots:
        return {"日期列表": [], "板块列表": []}

    dates = [date for date, _snapshot in date_snapshots]
    latest_date = dates[-1]
    daily_rows = []
    daily_max_positive = {}
    for date, snapshot in date_snapshots:
        row_map = {}
        positive_values = []
        for row in snapshot:
            name = row.get("板块名称")
            if not name:
                continue
            value = 规范题材资金净流入值(row.get("资金净流入(亿)"))
            row_map[name] = {
                "代码": row.get("板块代码", ""),
                "名称": name,
                "龙头": row.get("龙头", ""),
                "资金净流入": value,
            }
            if value is not None and value > 0:
                positive_values.append(value)
        daily_rows.append((date, row_map))
        daily_max_positive[date] = max(positive_values or [1])

    latest_rows = daily_rows[-1][1]
    result = []
    for board_name, latest_row in latest_rows.items():
        if board_name not in candidate_boards:
            continue
        values = []
        history = []
        for date, row_map in daily_rows:
            row = row_map.get(board_name)
            value = row.get("资金净流入") if row else None
            values.append(value)
            if value is None:
                history.append({
                    "日期": date,
                    "周期状态": "",
                    "周期分数": None,
                    "资金净流入": None,
                })
                continue

            score_info = 计算题材周期分数(values, daily_max_positive.get(date, 1))
            history.append({
                "日期": date,
                "周期状态": score_info.get("周期状态", ""),
                "周期分数": score_info.get("周期分数"),
                "资金净流入": 保留小数(value, 2),
            })

        latest_status = history[-1].get("周期状态", "") if history else ""
        if not latest_status:
            continue

        streak_days = 0
        for item in reversed(history):
            if item.get("周期状态") != latest_status:
                break
            streak_days += 1

        latest_score = history[-1].get("周期分数")
        latest_value = history[-1].get("资金净流入")
        trigger_info = candidate_board_info.get(board_name, {})
        result.append({
            "板块代码": latest_row.get("代码", ""),
            "板块名称": board_name,
            "交易日期": latest_date,
            "当前周期": latest_status,
            "连续天数": streak_days,
            "连续描述": f"连续{streak_days}日{latest_status}" if streak_days > 1 else f"今日{latest_status}",
            "周期分数": latest_score,
            "最新净流入": latest_value,
            "最近触发日期": trigger_info.get("最近触发日期", ""),
            "最近触发时间": trigger_info.get("最近触发时间", ""),
            "最近触发净流入": trigger_info.get("最近触发净流入"),
            "近一月最大净流入": trigger_info.get("近一月最大净流入"),
            "近一月最大日期": trigger_info.get("近一月最大日期", ""),
            "近一月最大时间": trigger_info.get("近一月最大时间", ""),
            "龙头": latest_row.get("龙头", ""),
            "最近周期": history[-10:],
        })

    result.sort(key=板块周期状态排序键)
    return {
        "日期列表": dates,
        "板块列表": result,
    }


def 板块周期状态排序键(item):
    state_order = {
        "冰点": 0,
        "退潮": 1,
        "弱修复": 2,
        "震荡": 3,
        "发酵": 4,
        "高潮": 5,
        "高潮分歧": 6,
    }
    trigger_date = 取整数(item.get("最近触发日期"))
    trigger_time = 取整数(str(item.get("最近触发时间", "")).replace(":", ""))
    return (
        -trigger_date,
        -trigger_time,
        -取浮点数(item.get("最近触发净流入")),
        state_order.get(item.get("当前周期"), 9),
        -取整数(item.get("连续天数")),
        item.get("板块名称", ""),
    )


def 生成题材周期摘要(topic_cycles, date, latest_time):
    if not topic_cycles:
        return f"{date} {latest_time} 暂无净流入为正的主力板块。"
    strongest = topic_cycles[0]
    return (
        f"{date} {latest_time} 主力板块为{strongest.get('题材名称')}，"
        f"周期状态{strongest.get('周期状态')}，情绪分 {strongest.get('周期分数')}，"
        f"最新净流入 {strongest.get('最新净流入')} 亿。"
    )


def 判断题材周期(score, latest_value, slope, positive_ratio):
    if latest_value < 0:
        if score < 45 or positive_ratio <= 0.25:
            return "冰点"
        return "退潮"
    if score >= 78 and slope < 0:
        return "高潮分歧"
    if score >= 82:
        return "高潮"
    if score >= 65:
        return "发酵"
    if score >= 45:
        return "震荡"
    if score >= 30 or positive_ratio >= 0.5:
        return "弱修复"
    return "退潮"


def 规范题材资金净流入值(value):
    if value is None:
        return None
    number = 取浮点数(value)
    while abs(number) >= 1000:
        number = number / 10000
    return number

def 生成题材波动图(times, values, max_positive, limit=80):
    start = max(0, len(times) - limit)
    normalized_values = [None if value is None else 取浮点数(value) for value in values]
    result = []
    for index in range(start, len(times)):
        current_values = normalized_values[:index + 1]
        latest_value = 最近有效值(current_values)
        score_info = 计算题材周期分数(current_values, max_positive)
        result.append({
            "时间": times[index],
            "资金净流入": 保留小数(latest_value, 2) if latest_value is not None else None,
            "周期分数": score_info.get("周期分数"),
            "周期状态": score_info.get("周期状态"),
        })
    return result


def 计算题材周期分数(values, max_positive):
    latest_value = 最近有效值(values)
    recent_values = [value for value in (values or [])[-30:] if value is not None]
    if latest_value is None or not recent_values:
        return {"周期分数": None, "周期状态": ""}

    first_value = recent_values[0]
    positive_count = sum(1 for value in recent_values if value > 0)
    valid_count = len(recent_values)
    slope = latest_value - first_value

    flow_score = 限制(max(latest_value, 0) / max(max_positive, 1) * 35, 0, 35)
    persistence_score = 限制(positive_count / max(valid_count, 1) * 25, 0, 25)
    slope_score = 限制(10 + slope / max(abs(first_value), max_positive, 1) * 25, 0, 20)
    activity_score = 限制(valid_count / 30 * 20, 0, 20)
    total_score = round(flow_score + persistence_score + slope_score + activity_score, 1)
    cycle_state = 判断题材周期(total_score, latest_value, slope, positive_count / max(valid_count, 1))

    return {
        "周期分数": total_score,
        "周期状态": cycle_state,
    }


def 读取上证指数日线(limit=160):
    rows = db.mysql_localhost(
        f"""
        SELECT 日期, 开盘, 收盘, 最高, 最低, 成交额, 涨跌幅
        FROM akshare_sh000001
        ORDER BY 日期 DESC
        LIMIT {int(limit)}
        """,
        fetch=True,
    )
    return list(reversed(rows or []))


def 读取市场宽度数据(limit=80):
    rows = db.mysql_localhost(
        f"""
        SELECT
            trade_date,
            COUNT(*) AS total_count,
            SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) AS up_count,
            SUM(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) AS down_count,
            SUM(CASE WHEN pct_chg >= 5 THEN 1 ELSE 0 END) AS up_gt5_count,
            SUM(CASE WHEN pct_chg <= -5 THEN 1 ELSE 0 END) AS down_lt5_count,
            SUM(CASE WHEN ({普通主板股票SQL}) AND pre_close > 0 AND close >= ROUND(pre_close * (1 + ({涨跌停幅度SQL})), 2) THEN 1 ELSE 0 END) AS limit_up_count,
            SUM(CASE WHEN ({普通主板股票SQL}) AND pre_close > 0 AND close <= ROUND(pre_close * (1 - ({涨跌停幅度SQL})), 2) THEN 1 ELSE 0 END) AS limit_down_count,
            SUM(amount) AS amount,
            AVG(pct_chg) AS avg_pct_chg
        FROM stock_daily
        WHERE trade_date IN (
            SELECT trade_date FROM (
                SELECT DISTINCT trade_date
                FROM stock_daily
                ORDER BY trade_date DESC
                LIMIT {int(limit)}
            ) recent_dates
        )
        GROUP BY trade_date
        ORDER BY trade_date ASC
        """,
        fetch=True,
    )
    return rows or []


def 匹配市场宽度(market_rows, latest_date):
    candidates = [row for row in market_rows if int(row.get("trade_date") or 0) <= latest_date]
    if candidates:
        return candidates[-1]
    return market_rows[-1] if market_rows else {}


def 计算指数情绪分项(close, ma, ma_slope, market, index_amount_ratio, market_amount_ratio):
    trend_score = 0
    if close > ma.get("MA5", 0):
        trend_score += 5
    if close > ma.get("MA10", 0):
        trend_score += 6
    if close > ma.get("MA20", 0):
        trend_score += 8
    if close > ma.get("MA60", 0):
        trend_score += 8
    if ma_slope.get("MA5", 0) > 0:
        trend_score += 4
    if ma_slope.get("MA10", 0) > 0:
        trend_score += 4

    total = max(取整数(market.get("total_count")), 1)
    up_ratio = 取整数(market.get("up_count")) / total
    strong_balance = (取整数(market.get("up_gt5_count")) - 取整数(market.get("down_lt5_count"))) / total
    avg_pct = 取浮点数(market.get("avg_pct_chg"))
    breadth_score = 限制(up_ratio * 18 + ((strong_balance + 0.05) / 0.1) * 5 + ((avg_pct + 1) / 2) * 2, 0, 25)

    limit_up = 取整数(market.get("limit_up_count"))
    limit_down = 取整数(market.get("limit_down_count"))
    limit_score = 限制(10 + limit_up * 0.35 - limit_down * 1.1, 0, 20)

    amount_ratio = max(index_amount_ratio, market_amount_ratio)
    if amount_ratio >= 1.4:
        volume_score = 10
    elif amount_ratio >= 1.15:
        volume_score = 9
    elif amount_ratio >= 0.95:
        volume_score = 7
    elif amount_ratio >= 0.75:
        volume_score = 5
    else:
        volume_score = 2

    risk_score = 限制(5 + 取整数(market.get("up_gt5_count")) * 0.08 - 取整数(market.get("down_lt5_count")) * 0.12 + avg_pct, 0, 10)

    return {
        "趋势": 限制(trend_score, 0, 35),
        "市场宽度": breadth_score,
        "涨跌停结构": limit_score,
        "量能": volume_score,
        "风险偏好": risk_score,
    }


def 判断指数周期(score, close, ma, ma_slope, market):
    total = max(取整数(market.get("total_count")), 1)
    up_ratio = 取整数(market.get("up_count")) / total
    limit_up = 取整数(market.get("limit_up_count"))
    limit_down = 取整数(market.get("limit_down_count"))
    trend_down = close < ma.get("MA20", 0) and ma_slope.get("MA5", 0) < 0

    if trend_down and (up_ratio < 0.42 or limit_down > limit_up):
        return "退潮"
    if score < 25:
        return "冰点"
    if score < 40:
        return "弱修复"
    if score < 60:
        return "震荡"
    if score < 75:
        return "发酵"
    if score < 88:
        return "高潮"
    return "过热高潮"


def 生成指数周期波动图(index_rows, market_rows, limit=30):
    market_map = {int(row.get("trade_date") or 0): row for row in market_rows}
    closes = [取浮点数(row.get("收盘")) for row in index_rows]
    amounts = [取浮点数(row.get("成交额")) for row in index_rows]
    result = []

    start = max(0, len(index_rows) - limit)
    for index in range(start, len(index_rows)):
        row = index_rows[index]
        date = int(row.get("日期") or 0)
        market = market_map.get(date, {})
        current_closes = closes[:index + 1]
        current_amounts = amounts[:index + 1]
        close = 取浮点数(row.get("收盘"))
        ma = {
            "MA5": 均线(current_closes, 5),
            "MA10": 均线(current_closes, 10),
            "MA20": 均线(current_closes, 20),
            "MA60": 均线(current_closes, 60),
        }
        ma_slope = {
            "MA5": 均线斜率(current_closes, 5, 3),
            "MA10": 均线斜率(current_closes, 10, 5),
            "MA20": 均线斜率(current_closes, 20, 5),
        }
        index_amount_ratio = 比值(取浮点数(row.get("成交额")), 平均值(current_amounts[-20:]))
        market_amount_ratio = 计算市场成交额比例(market_rows, market)
        score_parts = 计算指数情绪分项(close, ma, ma_slope, market, index_amount_ratio, market_amount_ratio)
        score = round(sum(score_parts.values()), 1)
        total = max(取整数(market.get("total_count")), 1)
        result.append({
            "日期": date,
            "情绪分": score,
            "周期状态": 判断指数周期(score, close, ma, ma_slope, market),
            "收盘": 保留小数(close, 2),
            "涨跌幅": 保留小数(row.get("涨跌幅"), 2),
            "上涨占比": 保留小数(取整数(market.get("up_count")) / total * 100, 1) if market else None,
        })
    return result


def 生成摘要(cycle_state, score, close, ma, market):
    total = max(取整数(market.get("total_count")), 1)
    up_ratio = 取整数(market.get("up_count")) / total * 100
    ma20_state = "上方" if close >= ma.get("MA20", 0) else "下方"
    return f"当前指数周期为{cycle_state}，情绪分 {score:.1f}。上证收盘位于 MA20 {ma20_state}，全市场上涨占比 {up_ratio:.1f}%。"


def 生成信号(close, ma, ma_slope, market, index_amount_ratio, market_amount_ratio):
    total = max(取整数(market.get("total_count")), 1)
    up_ratio = 取整数(market.get("up_count")) / total * 100
    signals = []

    signals.append({
        "名称": "趋势位置",
        "状态": "强" if close > ma.get("MA20", 0) else "弱",
        "数值": f"收盘 {close:.2f} / MA20 {ma.get('MA20', 0):.2f}",
        "说明": "站上 MA20 代表中短期环境偏暖，跌破则指数周期承压。",
    })
    signals.append({
        "名称": "均线斜率",
        "状态": "向上" if ma_slope.get("MA5", 0) > 0 and ma_slope.get("MA10", 0) > 0 else "分歧",
        "数值": f"MA5 {ma_slope.get('MA5', 0):.2f} / MA10 {ma_slope.get('MA10', 0):.2f}",
        "说明": "短均线斜率反映指数修复或退潮速度。",
    })
    signals.append({
        "名称": "市场宽度",
        "状态": "强" if up_ratio >= 60 else "弱" if up_ratio < 40 else "中性",
        "数值": f"上涨占比 {up_ratio:.1f}%",
        "说明": "上涨家数越多，指数上涨越有扩散基础。",
    })
    signals.append({
        "名称": "涨跌停结构",
        "状态": "强" if 取整数(market.get("limit_up_count")) > 取整数(market.get("limit_down_count")) else "弱",
        "数值": f"涨停 {取整数(market.get('limit_up_count'))} / 跌停 {取整数(market.get('limit_down_count'))}",
        "说明": "跌停数量扩大会压制风险偏好。",
    })
    signals.append({
        "名称": "量能",
        "状态": "放量" if max(index_amount_ratio, market_amount_ratio) >= 1.15 else "缩量" if max(index_amount_ratio, market_amount_ratio) < 0.85 else "正常",
        "数值": f"指数 {index_amount_ratio:.2f}x / 全市场 {market_amount_ratio:.2f}x",
        "说明": "量能相对 20 日均量放大，修复和发酵更容易延续。",
    })
    return signals


def 生成最近走势(index_rows, market_rows, limit=20):
    market_map = {int(row.get("trade_date") or 0): row for row in market_rows}
    result = []
    for row in index_rows[-limit:]:
        date = int(row.get("日期") or 0)
        market = market_map.get(date, {})
        total = max(取整数(market.get("total_count")), 1)
        result.append({
            "日期": date,
            "收盘": 保留小数(row.get("收盘"), 2),
            "涨跌幅": 保留小数(row.get("涨跌幅"), 2),
            "股票总数": 取整数(market.get("total_count")) if market else None,
            "上涨家数": 取整数(market.get("up_count")) if market else None,
            "下跌家数": 取整数(market.get("down_count")) if market else None,
            "上涨占比": 保留小数(取整数(market.get("up_count")) / total * 100, 1) if market else None,
            "涨停": 取整数(market.get("limit_up_count")) if market else None,
            "跌停": 取整数(market.get("limit_down_count")) if market else None,
            "涨停家数": 取整数(market.get("limit_up_count")) if market else None,
            "跌停家数": 取整数(market.get("limit_down_count")) if market else None,
        })
    return result


def 格式化市场宽度(market, market_amount_ratio):
    total = max(取整数(market.get("total_count")), 1)
    return {
        "交易日期": 取整数(market.get("trade_date")),
        "股票总数": total,
        "上涨家数": 取整数(market.get("up_count")),
        "下跌家数": 取整数(market.get("down_count")),
        "上涨占比": 保留小数(取整数(market.get("up_count")) / total * 100, 1),
        "涨超5家数": 取整数(market.get("up_gt5_count")),
        "跌超5家数": 取整数(market.get("down_lt5_count")),
        "涨停家数": 取整数(market.get("limit_up_count")),
        "跌停家数": 取整数(market.get("limit_down_count")),
        "平均涨跌幅": 保留小数(market.get("avg_pct_chg"), 2),
        "成交额比例": 保留小数(market_amount_ratio, 2),
    }


def 计算市场成交额比例(market_rows, latest_market):
    if not latest_market:
        return 0
    latest_date = int(latest_market.get("trade_date") or 0)
    previous = [取浮点数(row.get("amount")) for row in market_rows if int(row.get("trade_date") or 0) <= latest_date]
    return 比值(取浮点数(latest_market.get("amount")), 平均值(previous[-20:]))


def 均线(values, period):
    if len(values) < period:
        return 0
    return 平均值(values[-period:])


def 均线斜率(values, period, offset):
    if len(values) < period + offset:
        return 0
    current = 平均值(values[-period:])
    previous = 平均值(values[-period - offset:-offset])
    return current - previous


def 最近有效值(values):
    for value in reversed(values or []):
        if value not in (None, ""):
            return value
    return None


def 平均值(values):
    valid = [取浮点数(value) for value in values if value is not None]
    return sum(valid) / len(valid) if valid else 0


def 比值(value, base):
    base = 取浮点数(base)
    if base == 0:
        return 0
    return 取浮点数(value) / base


def 限制(value, min_value, max_value):
    return max(min_value, min(max_value, 取浮点数(value)))


def 取浮点数(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def 取整数(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def 保留小数(value, digits):
    return round(取浮点数(value), digits)
