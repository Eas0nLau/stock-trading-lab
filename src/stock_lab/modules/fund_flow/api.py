from fastapi import FastAPI, Query

from .service import FundFlowService


def register_fund_flow_routes(app: FastAPI, *, repository=None):
    if repository is None:
        from utils import db
        from .repository import FundFlowRepository

        repository = FundFlowRepository(db.redis_con_localhost)
    service = FundFlowService(repository)

    @app.get("/api/v1/fund-flow/{flow_type}/dates")
    def get_dates(flow_type: str):
        if flow_type not in {"industry", "concept"}:
            return {"status": "error", "error_message": "Unsupported flow type"}
        return service.dates(flow_type)

    @app.get("/api/v1/fund-flow/{flow_type}/history/{trade_date}")
    def get_history(flow_type: str, trade_date: str, top_n: int | None = Query(default=None, ge=0)):
        del top_n
        if flow_type not in {"industry", "concept"}:
            return {"status": "error", "error_message": "Unsupported flow type"}
        return service.history(flow_type, trade_date)
