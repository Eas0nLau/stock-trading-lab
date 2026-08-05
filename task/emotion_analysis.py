import json

from sqlalchemy import text

from 实时监控 import 情绪周期
from utils import db, 热门板块情绪算法


class MissingEmotionSource(RuntimeError):
    """Required source rows are missing for an emotion calculation."""


def _number(value, default=None):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value, default=0):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return default


def _json(value):
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def 指数结果转数据库行(result):
    index = result.get("指数") or {}
    width = result.get("市场宽度") or {}
    scores = result.get("分项得分") or {}
    slopes = result.get("均线斜率") or {}
    averages = result.get("均线") or {}
    return {
        "日期": _int(result.get("交易日期")),
        "指数名称": result.get("指数名称", "上证指数"),
        "周期状态": result.get("周期状态"),
        "周期分数": _number(result.get("周期分数")),
        "摘要": result.get("摘要"),
        "开盘": _number(index.get("开盘")),
        "收盘": _number(index.get("收盘")),
        "最高": _number(index.get("最高")),
        "最低": _number(index.get("最低")),
        "涨跌幅": _number(index.get("涨跌幅")),
        "指数成交额": _number(index.get("成交额")),
        "指数成交额比例": _number(index.get("指数成交额比例")),
        "市场成交额比例": _number(width.get("成交额比例")),
        "MA5": _number(averages.get("MA5")),
        "MA10": _number(averages.get("MA10")),
        "MA20": _number(averages.get("MA20")),
        "MA60": _number(averages.get("MA60")),
        "MA5斜率": _number(slopes.get("MA5")),
        "MA10斜率": _number(slopes.get("MA10")),
        "MA20斜率": _number(slopes.get("MA20")),
        "趋势得分": _number(scores.get("趋势")),
        "市场宽度得分": _number(scores.get("市场宽度")),
        "涨跌停结构得分": _number(scores.get("涨跌停结构")),
        "量能得分": _number(scores.get("量能")),
        "风险偏好得分": _number(scores.get("风险偏好")),
        "市场宽度JSON": width,
        "信号JSON": result.get("信号") or [],
        "最近走势JSON": result.get("最近走势") or [],
        "波动图JSON": result.get("波动图") or [],
        "完整结果JSON": result,
    }


def _upsert(table, columns, rows, keys):
    if not rows:
        return 0
    names = [f"v{index}" for index in range(len(columns))]
    updates = ", ".join(
        f"`{column}` = VALUES(`{column}`)"
        for column in columns
        if column not in keys
    )
    statement = text(
        f"INSERT INTO `{table}` ({', '.join(f'`{column}`' for column in columns)}) "
        f"VALUES ({', '.join(f':{name}' for name in names)}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    parameters = [{name: row.get(column) for name, column in zip(names, columns)} for row in rows]
    with db.engine.begin() as connection:
        connection.execute(statement, parameters)
    return len(rows)


def _market_for_date(rows, date):
    matches = [row for row in rows if _int(row.get("trade_date")) <= int(date)]
    return matches[-1] if matches else None


def 落库指数周期(date):
    date = _int(date)
    index_rows = [row for row in 情绪周期.读取上证指数日线(160) if _int(row.get("日期")) <= date]
    market_rows = [row for row in 情绪周期.读取市场宽度数据(80) if _int(row.get("trade_date")) <= date]
    if not index_rows or not market_rows or _int(index_rows[-1].get("日期")) != date:
        raise MissingEmotionSource(f"{date} 缺少指数日线或市场宽度数据")

    result = 情绪周期.计算指数周期结果(index_rows, market_rows)
    row = 指数结果转数据库行(result)
    database_row = {
        key: _json(value) if key.endswith("JSON") else value
        for key, value in row.items()
    }
    width = _market_for_date(market_rows, date)
    if width is None:
        raise MissingEmotionSource(f"{date} 缺少市场宽度数据")

    width_row = {
        "日期": date,
        "股票总数": _int(width.get("total_count")),
        "上涨家数": _int(width.get("up_count")),
        "下跌家数": _int(width.get("down_count")),
        "涨超5家数": _int(width.get("up_gt5_count")),
        "跌超5家数": _int(width.get("down_lt5_count")),
        "涨停家数": _int(width.get("limit_up_count")),
        "跌停家数": _int(width.get("limit_down_count")),
        "成交额": _number(width.get("amount")),
        "平均涨跌幅": _number(width.get("avg_pct_chg")),
    }
    _upsert(
        "t_指数情绪周期_市场宽度",
        list(width_row),
        [width_row],
        ["日期"],
    )
    _upsert(
        "t_指数情绪周期_每日分析",
        list(row),
        [database_row],
        ["日期"],
    )
    return 1


def 读取板块股票池(date):
    return db.mysql_localhost(
        """
        SELECT `板块`, `板块个股数量`, `股票代码`, `股票名称`
        FROM `t_韭研公社异动解析`
        WHERE `date` = %s
        ORDER BY `板块`, `股票代码`
        """,
        params=(int(date),),
        fetch=True,
    ) or []


def _板块股票(rows):
    grouped = {}
    for row in rows:
        board = str(row.get("板块") or "").strip()
        code = _int(row.get("股票代码"))
        if board and code:
            grouped.setdefault(board, {})[code] = {
                "股票代码": code,
                "股票名称": row.get("股票名称"),
            }
    return {board: list(items.values()) for board, items in grouped.items()}


def _行情(codes, date):
    codes = sorted({_int(code) for code in codes if _int(code)})
    if not codes:
        return {}
    placeholders = ",".join(["%s"] * len(codes))
    rows = db.mysql_localhost(
        f"SELECT ts_code, pre_close, high, low, pct_chg FROM stock_daily "
        f"WHERE trade_date = %s AND ts_code IN ({placeholders})",
        params=(int(date), *codes),
        fetch=True,
    ) or []
    return {_int(row.get("ts_code")): row for row in rows}


def 落库热门板块情绪(date, source_date):
    date = _int(date)
    source_date = _int(source_date)
    current = _板块股票(读取板块股票池(date))
    previous = _板块股票(读取板块股票池(source_date))
    if not current or not previous:
        raise MissingEmotionSource(f"{date} 缺少 {source_date} 或当前交易日韭研板块数据")

    codes = {code for rows in previous.values() for code in [item["股票代码"] for item in rows]}
    quotes = _行情(codes, date)
    board_names = set(current) | set(previous)
    current_counts = {
        board: len(rows) for board, rows in current.items()
    }
    previous_counts = {
        board: len(rows) for board, rows in previous.items()
    }
    raw_rows = 读取板块股票池(date)
    for board in board_names:
        board_rows = [row for row in raw_rows if row.get("板块") == board]
        current_counts[board] = max(
            [_int(row.get("板块个股数量")) for row in board_rows] or [current_counts.get(board, 0)]
        )

    results = []
    for board in sorted(board_names):
        result = 热门板块情绪算法.生成每日分析(
            日期=date,
            板块=board,
            样本来源日期=source_date,
            前日股票=previous.get(board, []),
            当日股票=current.get(board, []),
            当日行情=quotes,
            前日板块数量=previous_counts.get(board, 0),
            当日板块数量=current_counts.get(board, 0),
            前日榜单数据完整=board in previous,
            当日榜单数据完整=board in current,
        )
        result["判定依据JSON"] = _json(result.pop("判定依据", {}))
        results.append(result)

    columns = [
        "日期", "板块", "样本来源日期", "前日榜单数据完整", "当日榜单数据完整", "前日板块数量",
        "前日股票池数量", "前日明细覆盖率", "当日板块数量", "当日股票明细数量", "有效样本数",
        "行情覆盖率", "平均涨跌幅", "中位数涨跌幅", "平均振幅", "涨幅标准差", "晋级家数", "晋级率",
        "新晋级家数", "新晋级率", "红盘家数", "红盘率", "大涨家数", "大涨率", "大跌家数", "大跌率",
        "炸板家数", "炸板率", "同板块留存家数", "同板块留存率", "热度阶段", "承接情绪", "综合状态",
        "情绪分", "判定摘要", "判定依据JSON",
    ]
    return _upsert("t_热门板块情绪_每日分析", columns, results, ["日期", "板块"])
