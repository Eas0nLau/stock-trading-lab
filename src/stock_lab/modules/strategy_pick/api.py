from fastapi import Body, FastAPI
from fastapi.responses import StreamingResponse

from .repository import StrategyPickRepository
from .service import StrategyPickService


def register_strategy_pick_routes(app: FastAPI, *, settings=None, repository=None, collector=None, default_strategies=None):
    if repository is None:
        from stock_lab.config import get_settings
        from stock_lab.infrastructure.cache.redis_client import create_redis_client
        repository = StrategyPickRepository(create_redis_client(settings or get_settings()))
    if default_strategies is None:
        from stock_lab.config.defaults import DEFAULT_STRATEGY_PICK_STRATEGIES
        default_strategies = DEFAULT_STRATEGY_PICK_STRATEGIES
    if collector is None:
        from .collector import StrategyPickCollector
        collector = StrategyPickCollector(repository, settings=settings)
    service = StrategyPickService(repository, collector=collector, default_strategies=default_strategies)

    @app.get("/api/v1/strategy-pick/strategies")
    def get_strategies(): return service.strategies()
    @app.post("/api/v1/strategy-pick/strategies")
    def post_strategy(payload: dict = Body(...)): return service.create_strategy(payload)
    @app.get("/api/v1/strategy-pick/strategies/{strategy_id}")
    def get_strategy(strategy_id: str): return service.get_strategy(strategy_id)
    @app.put("/api/v1/strategy-pick/strategies/{strategy_id}")
    def put_strategy(strategy_id: str, payload: dict = Body(...)): return service.update_strategy(strategy_id, payload)
    @app.delete("/api/v1/strategy-pick/strategies/{strategy_id}")
    def delete_strategy(strategy_id: str): return service.delete_strategy(strategy_id)
    @app.get("/api/v1/strategy-pick/strategies/{strategy_id}/latest")
    def get_latest_for_strategy(strategy_id: str): return service.latest(strategy_id)
    @app.get("/api/v1/strategy-pick/strategies/{strategy_id}/history/{date}")
    def get_history_for_strategy(strategy_id: str, date: str): return service.history(strategy_id, date)
    @app.get("/api/v1/strategy-pick/strategies/{strategy_id}/events/{date}")
    def get_events_for_strategy(strategy_id: str, date: str): return service.events(strategy_id, date)
    @app.get("/api/v1/strategy-pick/strategies/{strategy_id}/dates")
    def get_dates_for_strategy(strategy_id: str): return service.dates(strategy_id)
    @app.post("/api/v1/strategy-pick/strategies/{strategy_id}/refresh")
    def refresh_strategy(strategy_id: str): return service.refresh(strategy_id)
    @app.post("/api/v1/strategy-pick/refresh-all")
    def refresh_all(): return service.refresh_all()
    @app.get("/api/v1/strategy-pick/stream")
    def stream(): return StreamingResponse(service.stream_events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/v1/strategy-pick/latest")
    def get_latest(): return service.latest(service.default_strategy_id())
    @app.get("/api/v1/strategy-pick/history/{date}")
    def get_history(date: str): return service.history(service.default_strategy_id(), date)
    @app.get("/api/v1/strategy-pick/events/{date}")
    def get_events(date: str): return service.global_events(date)
    @app.get("/api/v1/strategy-pick/dates")
    def get_dates(): return service.dates()
    @app.post("/api/v1/strategy-pick/refresh")
    def refresh(): return service.refresh(service.default_strategy_id())
