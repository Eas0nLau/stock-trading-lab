from fastapi import FastAPI

from .contracts import translate


def register_strategy_pick_routes(app: FastAPI):
    from 实时监控 import 策略选股

    @app.get("/api/v1/strategy-pick/strategies")
    def strategies(): return translate(策略选股.获取策略列表())

    @app.get("/api/v1/strategy-pick/latest")
    def latest(): return translate(策略选股.读取最新快照(策略选股.获取默认策略ID()))

    @app.get("/api/v1/strategy-pick/dates")
    def dates(): return translate(策略选股.获取策略选股日期列表())
