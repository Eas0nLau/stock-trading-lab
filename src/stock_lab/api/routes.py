from fastapi import FastAPI

from stock_lab.modules.emotion import register_emotion_routes
from stock_lab.modules.fund_flow.api import register_fund_flow_routes
from stock_lab.modules.strategy_pick.api import register_strategy_pick_routes


def register_routes(app: FastAPI) -> None:
    register_emotion_routes(app)
    register_fund_flow_routes(app)
    register_strategy_pick_routes(app)
