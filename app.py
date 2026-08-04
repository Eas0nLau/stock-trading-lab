from threading import Timer
import datetime
from contextlib import asynccontextmanager
import front_run
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import threading

from utils import db, driver_chrome
from task import 每日更新, 盘前纪要
from 实时监控 import 资金流向, 策略选股, 情绪周期, 热门板块情绪
from loguru import logger
import uvicorn


@asynccontextmanager
async def lifespan(_app):
    启动后台监控线程()
    yield


# ====================== FastAPI 服务 ======================
app = FastAPI(title="stock_trading_lab_api", lifespan=lifespan)

# 允许前端跨域（支持 file:// 和 http://localhost）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


资金流向.注册接口(app)
策略选股.注册接口(app)
情绪周期.注册接口(app)
热门板块情绪.注册接口(app)


def start_scraper():
    logger.info(f"定时调度任务已启动，资金流向采集间隔 {资金流向.获取资金流向采集间隔秒()} 秒")
    资金流向.init_driver()
    资金流向.预热最新资金流向历史()

    while True:
        资金流向.等待到下次对齐执行()
        now = datetime.datetime.now()
        if 资金流向.当前是资金流向采集时间(now):
            资金流向.采集全部资金流向()
        else:
            # 非交易时间每5分钟打一次日志
            if now.minute % 1 == 0:
                pass
                # logger.info(f"非交易时段，跳过抓取 | 当前时间 {now.strftime('%H:%M:%S')}")

        if now.weekday() < 5 and (datetime.time(17, 35) <= now.time()):
            if not db.redis_con_localhost.exists(f"每日更新.py:{now.strftime('%Y%m%d')}") and \
                    not db.redis_con_localhost.exists(f"run_check:每日更新.py"):
                Timer(0, 每日更新.tasks, args=[now.strftime('%Y%m%d')]).start()
            pass

        if now.weekday() < 5 and (datetime.time(8, 00) <= now.time()):
            if not db.redis_con_localhost.exists(f"盘前纪要.py:{now.strftime('%Y%m%d')}") and \
                    not db.redis_con_localhost.exists(f"run_check:盘前纪要.py"):
                Timer(0, 盘前纪要.韭研公社盘前纪要采集, args=[now.strftime('%Y%m%d')]).start()
            pass


后台线程锁 = threading.Lock()
后台线程 = {}


def 启动后台线程(name, target):
    thread = 后台线程.get(name)
    if thread and thread.is_alive():
        return

    thread = threading.Thread(target=target, daemon=True, name=name)
    thread.start()
    后台线程[name] = thread
    logger.info(f"{name}线程已启动")


def 启动后台监控线程():
    with 后台线程锁:
        启动后台线程("资金流向采集", start_scraper)
        启动后台线程("策略选股监控", 策略选股.start_monitor)

# ====================== 启动服务 ======================
if __name__ == "__main__":
    db.redis_con_localhost.delete(f"run_check:每日更新.py")
    db.redis_con_localhost.delete(f"run_check:盘前纪要.py")
    # driver_chrome.initTab()
    Timer(0, front_run.run, args=[]).start()
    uvicorn.run(app, host="0.0.0.0", port=8051, reload=False)
