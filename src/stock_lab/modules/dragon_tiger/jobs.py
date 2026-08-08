import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from stock_lab.infrastructure.cache import RedisJobLock


JOB_PREFIX = "stock_lab:dragon_tiger:job:"
ACTIVE_KEY = "stock_lab:dragon_tiger:active"
SOURCE_TABLES = ["dragon_tiger", "broker_listing_history", "daily_quotes"]


class DragonTigerCollectionJobManager:
    def __init__(
        self,
        redis,
        *,
        run_listings,
        run_broker_directory,
        run_broker_history,
        run_analysis,
        executor=None,
        expiry_seconds=86400,
    ):
        self.redis = redis
        self.run_listings = run_listings
        self.run_broker_directory = run_broker_directory
        self.run_broker_history = run_broker_history
        self.run_analysis = run_analysis
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="dragon-tiger")
        self.expiry_seconds = expiry_seconds

    def start(self, start_date, latest_date):
        start_date = int(start_date)
        latest_date = int(latest_date)
        if start_date > latest_date:
            raise ValueError("start_date must be less than or equal to latest_date")

        job_id = str(uuid.uuid4())
        lock = RedisJobLock(self.redis, ACTIVE_KEY, self.expiry_seconds)
        if not lock.acquire():
            raise RuntimeError("dragon tiger collection job is active")

        state = {
            "jobId": job_id,
            "status": "queued",
            "stage": "queued",
            "startDate": start_date,
            "latestDate": latest_date,
            "selectedCount": 0,
            "selectedCodes": [],
            "sourceTables": SOURCE_TABLES,
            "error": None,
        }
        try:
            self._save(state)
            self.executor.submit(self._run, state, lock)
        except Exception:
            lock.release()
            raise
        return state

    def get(self, job_id):
        value = self.redis.get(f"{JOB_PREFIX}{job_id}")
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value)

    def _run(self, state, lock):
        stages = (
            ("listings", self.run_listings),
            ("broker_directory", self.run_broker_directory),
            ("broker_history", self.run_broker_history),
            ("analysis", self.run_analysis),
        )
        try:
            state["status"] = "running"
            for stage, function in stages:
                state["stage"] = stage
                self._save(state)
                result = function(state["startDate"], state["latestDate"])
                if stage == "analysis" and result:
                    state["selectedCodes"] = list(result.get("selectedCodes", []))
                    state["selectedCount"] = len(state["selectedCodes"])
            state["status"] = "succeeded"
            state["stage"] = "complete"
            self._save(state)
        except Exception as error:
            state["status"] = "failed"
            state["error"] = str(error)[:500]
            self._save(state)
        finally:
            lock.release()

    def shutdown(self):
        self.executor.shutdown(wait=True, cancel_futures=True)

    def _save(self, state):
        self.redis.set(
            f"{JOB_PREFIX}{state['jobId']}",
            json.dumps(state, ensure_ascii=False),
            ex=self.expiry_seconds,
        )
