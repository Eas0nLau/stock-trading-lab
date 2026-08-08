from fastapi import Body, FastAPI, HTTPException, Query


def register_dragon_tiger_routes(app: FastAPI, *, manager, analysis):
    @app.post("/api/v1/dragon-tiger/collection-jobs", status_code=202)
    def create_collection_job(payload: dict = Body(...)):
        try:
            start_date = int(payload["startDate"])
            latest_date = int(payload["latestDate"])
            if start_date > latest_date:
                raise ValueError("start_date must be less than or equal to latest_date")
            return manager.start(start_date, latest_date)
        except KeyError as error:
            raise HTTPException(status_code=422, detail=f"missing field: {error.args[0]}") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/dragon-tiger/collection-jobs/{job_id}")
    def get_collection_job(job_id: str):
        state = manager.get(job_id)
        if state is None:
            raise HTTPException(status_code=404, detail="collection job not found")
        return state

    @app.get("/api/v1/dragon-tiger/premium")
    def get_premium(
        start_date: int = Query(...),
        latest_date: int = Query(...),
    ):
        if start_date > latest_date:
            raise HTTPException(status_code=422, detail="start_date must be less than or equal to latest_date")
        return analysis(start_date, latest_date)
