from fastapi import FastAPI

from stock_lab.modules.emotion import register_emotion_routes
from stock_lab.modules.fund_flow.api import register_fund_flow_routes


def register_routes(app: FastAPI) -> None:
    from 实时监控 import 策略选股, 资金流向

    资金流向.注册接口(app)
    策略选股.注册接口(app)
    register_emotion_routes(app)
    register_fund_flow_routes(app)
