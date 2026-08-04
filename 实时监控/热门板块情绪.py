import json

from utils import db, 热门板块情绪算法


接口路径前缀 = "/api/hot-board-emotion"
每日分析表名 = "t_热门板块情绪_每日分析"

整数值字段 = {
    "日期", "样本来源日期", "前日板块数量", "前日股票池数量", "当日板块数量", "当日股票明细数量",
    "有效样本数", "晋级家数", "新晋级家数", "红盘家数", "大涨家数", "大跌家数", "炸板家数", "同板块留存家数",
}
浮点值字段 = {
    "前日明细覆盖率", "行情覆盖率", "平均涨跌幅", "中位数涨跌幅", "平均振幅", "涨幅标准差",
    "晋级率", "新晋级率", "红盘率", "大涨率", "大跌率", "炸板率", "同板块留存率", "情绪分",
}


def 注册接口(app):
    @app.get(f"{接口路径前缀}/current")
    def get_current_hot_board_emotion(days: int = 30):
        return 读取热门板块情绪(days=days)


def 读取热门板块情绪(days=30):
    热门板块情绪算法.刷新运行配置()
    days = max(5, min(60, 热门板块情绪算法.取整数(days) or 30))
    if not 表存在():
        return {"状态": "empty", "错误信息": "暂无热门板块情绪分析表，请先执行每日更新"}

    日期列表 = 查询最近分析日期(days)
    if not 日期列表:
        return {"状态": "empty", "错误信息": "暂无热门板块情绪落库数据，请先执行每日更新"}

    rows = 查询分析结果(日期列表)
    if not rows:
        return {"状态": "empty", "错误信息": "最近交易日暂无热门板块情绪数据"}

    板块映射 = {}
    for raw in rows:
        item = 转换分析行(raw)
        if item["板块"] in 热门板块情绪算法.热门板块排除集合:
            continue
        板块映射.setdefault(item["板块"], []).append(item)

    最新交易日 = 日期列表[-1]
    板块列表 = []
    for 板块, trend in 板块映射.items():
        trend.sort(key=lambda item: item["日期"])
        峰值数量 = max((item.get("当日板块数量") or 0 for item in trend), default=0)
        if 峰值数量 < 热门板块情绪算法.热门板块入选数量阈值:
            continue
        高潮日期 = [item["日期"] for item in trend if (item.get("当日板块数量") or 0) >= 热门板块情绪算法.高潮数量阈值]
        最新记录 = next((item for item in reversed(trend) if item["日期"] == 最新交易日), trend[-1])
        近期强度 = 计算近期强度(trend)
        状态排名 = 热门板块情绪算法.状态强弱排序.get(最新记录.get("综合状态"), 0)
        板块列表.append({
            "板块": 板块,
            "近30日峰值数量": 峰值数量,
            "最近高潮日期": max(高潮日期) if 高潮日期 else None,
            "高潮次数": len(高潮日期),
            "最新状态": 最新记录.get("综合状态"),
            "最新情绪分": 最新记录.get("情绪分"),
            "近期强度": 近期强度,
            "最新记录": 最新记录,
            "近期走势": trend,
            "排序值": 状态排名 * 1000 + 取浮点数(最新记录.get("情绪分")) * 5 + 近期强度,
        })

    板块列表.sort(key=lambda item: (-item["排序值"], -item["近30日峰值数量"], item["板块"]))
    for item in 板块列表:
        item.pop("排序值", None)

    return {
        "状态": "success",
        "最新交易日": 最新交易日,
        "可选日期": 日期列表,
        "统计交易日数": len(日期列表),
        "热门板块数量": len(板块列表),
        "板块列表": 板块列表,
        "配置": {
            "热门板块入选数量阈值": 热门板块情绪算法.热门板块入选数量阈值,
            "高潮数量阈值": 热门板块情绪算法.高潮数量阈值,
            "强势延续晋级比例": 热门板块情绪算法.强势延续晋级比例,
            "排除板块": sorted(热门板块情绪算法.热门板块排除集合),
        },
        "数据口径": {
            "热门板块": f"近{len(日期列表)}个交易日内至少一天板块个股数量达到{热门板块情绪算法.热门板块入选数量阈值}只，排除板块：{'、'.join(sorted(热门板块情绪算法.热门板块排除集合))}",
            "高潮定义": f"仅当日板块数量达到{热门板块情绪算法.高潮数量阈值}只触发，与平均涨幅、晋级率和情绪分无关",
            "退潮定义": "上一交易日上榜而当日未上榜时，不受可跟踪样本数量限制，综合状态直接判定为退潮",
            "强势延续定义": f"旧池晋级家数或新增涨停家数达到上一日股票池的{热门板块情绪算法.强势延续晋级比例 * 100:.0f}%",
            "分化定义": f"旧池至少1只继续连板、但未达到{热门板块情绪算法.强势延续晋级比例 * 100:.0f}%强势延续门槛时判定为分化；当日未上榜仍按退潮处理",
            "正向承接门槛": f"强势延续或良性承接仅在板块达到{热门板块情绪算法.热门板块入选数量阈值}只入选阈值后生效；低热度小样本最多按活跃处理",
            "情绪分口径": f"当日板块数量贡献0至{热门板块情绪算法.高潮基础分:.0f}分，承接指标仅按样本置信度小幅修正；高潮固定为{热门板块情绪算法.高潮基础分:.0f}分",
            "承接情绪": "严格使用上一交易日实际落库股票池，统计本交易日平均涨幅、振幅、晋级率等指标",
            "晋级定义": f"当日涨幅达到{热门板块情绪算法.晋级涨幅阈值}%",
            "股票范围": "仅统计沪深主板股票，并剔除股票名称中含ST的股票",
        },
    }


def 表存在():
    try:
        rows = db.mysql_localhost(f"SHOW TABLES LIKE '{每日分析表名}'", fetch=True)
        return bool(rows)
    except Exception:
        return False


def 查询最近分析日期(limit):
    rows = db.mysql_localhost(
        f"""
        SELECT DISTINCT `日期`
        FROM `{每日分析表名}`
        ORDER BY `日期` DESC
        LIMIT {int(limit)}
        """,
        fetch=True,
    ) or []
    return sorted(热门板块情绪算法.取整数(row.get("日期")) for row in rows)


def 查询分析结果(日期列表):
    placeholders = ",".join(["%s"] * len(日期列表))
    return db.mysql_localhost(
        f"""
        SELECT
            `日期`, `板块`, `样本来源日期`, `前日榜单数据完整`, `当日榜单数据完整`,
            `前日板块数量`, `前日股票池数量`, `前日明细覆盖率`, `当日板块数量`, `当日股票明细数量`,
            `有效样本数`, `行情覆盖率`, `平均涨跌幅`, `中位数涨跌幅`, `平均振幅`, `涨幅标准差`,
            `晋级家数`, `晋级率`, `新晋级家数`, `新晋级率`, `红盘家数`, `红盘率`, `大涨家数`, `大涨率`, `大跌家数`, `大跌率`,
            `炸板家数`, `炸板率`, `同板块留存家数`, `同板块留存率`,
            `热度阶段`, `承接情绪`, `综合状态`, `情绪分`, `判定摘要`, `判定依据JSON`
        FROM `{每日分析表名}`
        WHERE `日期` IN ({placeholders})
        ORDER BY `板块` ASC, `日期` ASC
        """,
        params=tuple(日期列表),
        fetch=True,
    ) or []


def 转换分析行(row):
    result = {}
    for key, value in row.items():
        if key in 整数值字段:
            result[key] = 取可选整数(value)
        elif key in 浮点值字段:
            result[key] = 取可选浮点数(value)
        elif key in {"前日榜单数据完整", "当日榜单数据完整"}:
            result[key] = bool(value)
        elif key == "判定依据JSON":
            result["判定依据"] = 解析JSON(value)
        else:
            result[key] = value
    return result


def 计算近期强度(trend):
    scores = [取浮点数(item.get("情绪分")) for item in trend[-3:]]
    if not scores:
        return 0.0
    weights = [0.2, 0.3, 0.5][-len(scores):]
    weight_sum = sum(weights)
    return round(sum(score * weight for score, weight in zip(scores, weights)) / weight_sum, 1)


def 解析JSON(value):
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def 取可选整数(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def 取可选浮点数(value):
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def 取浮点数(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
