from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse

from stock_lab.config import get_settings

from .service import FundFlowService


def register_fund_flow_routes(app: FastAPI, *, settings=None, repository=None, mysql_repository=None):
    settings = get_settings() if settings is None else settings
    repository_was_injected = repository is not None
    if repository is None:
        from stock_lab.infrastructure.cache.redis_client import create_redis_client
        from .repository import FundFlowRepository

        repository = FundFlowRepository(create_redis_client(settings))
    if mysql_repository is None:
        if getattr(repository, "mysql_repository", None) is not None:
            mysql_repository = repository.mysql_repository
        elif not repository_was_injected and hasattr(settings, "mysql"):
            from stock_lab.infrastructure.database import create_database_client
            from .mysql_repository import FundFlowMySQLRepository

            database = create_database_client(settings)
            mysql_repository = FundFlowMySQLRepository(lambda: database.resources.get_pool().get_connection())
    service = FundFlowService(repository, mysql_repository, default_top_n=settings.fund_flow_history_top_n)

    @app.get("/api/v1/fund-flow/{flow_type}/dates")
    def get_dates(flow_type: str):
        if flow_type not in {"industry", "concept"}:
            return {"status": "error", "error_message": "Unsupported flow type"}
        return service.dates(flow_type)

    @app.get("/api/v1/fund-flow/{flow_type}/history/{trade_date}")
    def get_history(flow_type: str, trade_date: str, top_n: int | None = Query(default=None, ge=0)):
        if flow_type not in {"industry", "concept"}:
            return {"status": "error", "error_message": "Unsupported flow type"}
        return service.history(flow_type, trade_date, top_n=top_n)

    @app.get("/api/v1/fund-flow/stream")
    def stream():
        return StreamingResponse(
            service.stream_events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
