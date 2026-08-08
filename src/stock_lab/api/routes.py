from fastapi import FastAPI

from stock_lab.modules.emotion import register_emotion_routes
from stock_lab.modules.fund_flow.api import register_fund_flow_routes
from stock_lab.modules.strategy_pick.api import register_strategy_pick_routes
from stock_lab.modules.dragon_tiger.api import register_dragon_tiger_routes
from stock_lab.modules.dragon_tiger.runtime import create_collection_job_manager, analyze_premium_result


def register_routes(app: FastAPI, *, settings) -> None:
    register_emotion_routes(app, settings=settings)
    register_fund_flow_routes(app, settings=settings)
    register_strategy_pick_routes(app, settings=settings)
    manager = create_collection_job_manager(settings=settings)
    app.state.dragon_tiger_job_manager = manager
    register_dragon_tiger_routes(
        app,
        manager=manager,
        analysis=lambda start, latest: analyze_premium_result(
            start, latest, settings=settings, database=manager.database
        ),
    )
