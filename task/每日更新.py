import argparse
import datetime as dt
import time

from loguru import logger

from task.data_sources import (
    更新指数日线,
    更新股票基础信息,
    更新股票日线,
    交易日期列表,
)
from utils import db


运行锁 = "run_check:每日更新.py"
完成键模板 = "每日更新.py:{}"
锁过期秒 = 21600


def 韭研公社异动采集(date):
    from task._5_韭研公社异动 import 韭研公社异动采集 as collect

    return collect(date)


def 落库热门板块情绪(date, source_date):
    from task.emotion_analysis import 落库热门板块情绪 as write_hot_board

    return write_hot_board(date, source_date)


def 落库指数周期(date):
    from task.emotion_analysis import 落库指数周期 as write_index

    return write_index(date)


def _date_int(value):
    text = str(value or "").replace("-", "")[:8]
    return int(text)


def _previous_date(date, dates):
    prior = [item for item in dates if int(item) < int(date)]
    if not prior:
        raise RuntimeError(f"{date} 没有上一交易日")
    return prior[-1]


def _lock():
    token = f"{time.time_ns()}"
    acquired = db.redis_con_localhost.set(运行锁, token, nx=True, ex=锁过期秒)
    return token if acquired else None


def _unlock(token):
    if token is None:
        return
    current = db.redis_con_localhost.get(运行锁)
    if current == token:
        db.redis_con_localhost.delete(运行锁)


def tasks(date):
    date = _date_int(date)
    completion_key = 完成键模板.format(date)
    if db.redis_con_localhost.exists(completion_key):
        return {"状态": "skipped", "交易日期": date, "原因": "该日期已完成"}

    token = _lock()
    if token is None:
        raise RuntimeError("每日更新任务正在运行")

    try:
        dates = 交易日期列表(160)
        if date not in dates:
            更新指数日线(max(1, date - 10000), date)
            dates = 交易日期列表(160)
        if date not in dates:
            raise RuntimeError(f"{date} 不是可用交易日或指数日线未更新")
        source_date = _previous_date(date, dates)
        date_index = dates.index(date) if date in dates else len(dates) - 1
        start_date = dates[max(0, date_index - 159)]

        counts = {
            "股票基础": 更新股票基础信息(),
            "股票日线": 更新股票日线(start_date, date),
            "指数日线": 更新指数日线(start_date, date),
            "韭研异动": 韭研公社异动采集(date),
            "热门板块情绪": 落库热门板块情绪(date, source_date),
            "指数周期": 落库指数周期(date),
        }
        db.redis_con_localhost.set(completion_key, str(int(time.time())), ex=7 * 86400)
        return {"状态": "success", "交易日期": date, "来源日期": source_date, "数量": counts}
    finally:
        _unlock(token)


def backfill(days=60):
    dates = 交易日期列表(max(int(days), 1))
    results = []
    for date in dates:
        try:
            results.append(tasks(date))
        except Exception as error:
            logger.error(f"{date} 每日更新失败：{error}")
            results.append({"状态": "failed", "交易日期": date, "错误信息": str(error)})
    return {"状态": "success" if all(item["状态"] in {"success", "skipped"} for item in results) else "failed", "结果": results}


def main():
    parser = argparse.ArgumentParser(description="更新指数周期和热门板块情绪数据")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--date", type=int, help="更新单个交易日，格式 YYYYMMDD")
    group.add_argument("--backfill", type=int, help="回补最近 N 个交易日")
    args = parser.parse_args()
    result = tasks(args.date) if args.date else backfill(args.backfill)
    print(result)
    return 0 if result.get("状态") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
