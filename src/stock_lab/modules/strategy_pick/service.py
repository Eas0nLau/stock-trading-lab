import datetime
import re
import uuid

from fastapi import HTTPException


class StrategyPickService:
    def __init__(self, repository, collector=None, default_strategies=None):
        self.repository = repository
        self.collector = collector
        self.default_strategies = default_strategies or []

    def strategies(self):
        current = self.repository.strategies()
        if current: return current
        normalized = [normalize_strategy(item) for item in self.default_strategies]
        normalized = [item for item in normalized if item]
        if normalized: self.repository.save_strategies(normalized)
        return normalized

    def get_strategy(self, strategy_id):
        strategy = next((item for item in self.strategies() if item.get("id") == strategy_id), None)
        if strategy is None: raise HTTPException(status_code=404, detail=f"Strategy does not exist: {strategy_id}")
        return strategy

    def create_strategy(self, payload):
        strategy = normalize_strategy(payload, allow_new_id=True)
        current = self.strategies()
        if any(item.get("id") == strategy["id"] for item in current):
            raise HTTPException(status_code=400, detail=f"Strategy ID already exists: {strategy['id']}")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        strategy["createdAt"] = now; strategy["updatedAt"] = now
        self.repository.save_strategies([*current, strategy])
        return strategy

    def update_strategy(self, strategy_id, payload):
        current = self.strategies()
        old = self.get_strategy(strategy_id)
        updated = normalize_strategy({**old, **payload, "id": strategy_id})
        updated["createdAt"] = old.get("createdAt", "")
        updated["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.repository.save_strategies([updated if item["id"] == strategy_id else item for item in current])
        return updated

    def delete_strategy(self, strategy_id):
        current = self.strategies()
        self.get_strategy(strategy_id)
        if len(current) == 1: raise HTTPException(status_code=400, detail="At least one strategy must remain")
        self.repository.save_strategies([item for item in current if item["id"] != strategy_id])
        return {"deleted": strategy_id}

    def default_strategy_id(self):
        current = self.strategies()
        return next((item["id"] for item in current if item.get("enabled", True)), current[0]["id"])

    def latest(self, strategy_id): self.get_strategy(strategy_id); return self.repository.latest(strategy_id)
    def history(self, strategy_id, date): self.get_strategy(strategy_id); return self.repository.history(strategy_id, date)
    def events(self, strategy_id, date): self.get_strategy(strategy_id); return self.repository.events(strategy_id, date)
    def global_events(self, date): return self.repository.global_events(date)
    def dates(self, strategy_id=None): return self.repository.dates(strategy_id)
    def refresh(self, strategy_id):
        self.get_strategy(strategy_id)
        if self.collector is None: raise HTTPException(status_code=503, detail="Strategy collector is unavailable")
        return self.collector.refresh(strategy_id)
    def refresh_all(self):
        if self.collector is None: raise HTTPException(status_code=503, detail="Strategy collector is unavailable")
        return self.collector.refresh_all()
    def stream_events(self): return self.repository.stream_events()


def normalize_strategy(payload, allow_new_id=False):
    payload = payload or {}
    strategy_id = _strategy_id(payload.get("id"))
    if not strategy_id and allow_new_id: strategy_id = f"strategy_{uuid.uuid4().hex[:8]}"
    if not strategy_id: strategy_id = "eastmoney_default"
    name = str(payload.get("name") or strategy_id).strip()
    page_url = str(payload.get("pageUrl") or "").strip()
    if not page_url: raise HTTPException(status_code=400, detail="pageUrl is required")
    return {
        "id": strategy_id, "name": name, "pageUrl": page_url,
        "listenTargets": _targets(payload.get("listenTargets")),
        "monitorPeriods": _periods(payload.get("monitorPeriods")),
        "monitorIntervalSeconds": _interval(payload.get("monitorIntervalSeconds")),
        "enabled": payload.get("enabled", True) is not False,
        "createdAt": payload.get("createdAt", ""), "updatedAt": payload.get("updatedAt", ""),
    }


def _strategy_id(value): return re.sub(r"[^0-9A-Za-z_-]", "_", str(value or "").strip()).strip("_")[:64]
def _interval(value):
    try: return max(1, int(value or 60))
    except (TypeError, ValueError): return 60
def _targets(value):
    if isinstance(value, str): value = re.split(r"[\r\n,]", value)
    return [str(item).strip() for item in (value or []) if str(item).strip()] or ["/api/smart-tag/stock/v3/pw/search-code"]
def _periods(value):
    if isinstance(value, str): value = re.split(r"[\r\n,;]", value)
    result = []
    for item in value or []:
        parts = re.split(r"~|-", item, maxsplit=1) if isinstance(item, str) else item
        if isinstance(parts, (list, tuple)) and len(parts) >= 2 and str(parts[0]).strip() and str(parts[1]).strip(): result.append([str(parts[0]).strip(), str(parts[1]).strip()])
    return result or [["09:00", "15:00"]]
