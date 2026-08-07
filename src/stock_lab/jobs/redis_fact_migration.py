import hashlib
import json
import re
from datetime import date
from pathlib import Path

from stock_lab.modules.strategy_pick.contracts import translate_legacy_strategy_pick


LEGACY_STRATEGY_PREFIX = "策略选股:"
V1_STRATEGY_PREFIX = "strategy_pick:v1:"
_HISTORY_RE = re.compile(r"^(策略选股|strategy_pick:v1):(?P<strategy>[^:]+):history:(?P<date>\d{8})$")
_EVENTS_RE = re.compile(r"^(策略选股|strategy_pick:v1):(?P<strategy>[^:]+):events:(?P<date>\d{8})$")
_LATEST_RE = re.compile(r"^(策略选股|strategy_pick:v1):(?P<strategy>[^:]+):latest$")
_GLOBAL_EVENTS_RE = re.compile(r"^(策略选股|strategy_pick:v1):events:(?P<date>\d{8})$")


def run_migration(
    redis,
    mysql_repository,
    *,
    fund_flow_mysql_repository=None,
    cleanup=False,
    backup_paths=(),
    confirmation="",
    today=None,
):
    if cleanup and confirmation != "REDIS_CACHE_ONLY":
        raise RuntimeError("live cleanup confirmation must be REDIS_CACHE_ONLY")
    missing_backups = [str(path) for path in backup_paths if not Path(path).is_file()]
    if cleanup and (len(backup_paths) < 2 or missing_backups):
        raise RuntimeError(f"live cleanup requires existing MySQL and Redis backup files: {missing_backups}")
    if cleanup and fund_flow_mysql_repository is None:
        raise RuntimeError("live cleanup requires a fund-flow MySQL repository")
    before = inventory(redis)
    migrated = migrate_strategy_pick(redis, mysql_repository)
    mysql_inventory = mysql_repository.inventory()
    shortfalls = {
        name: {"mysql": mysql_inventory.get(name, 0), "migrated": migrated[name]}
        for name in ("strategies", "snapshots", "stocks", "events")
        if mysql_inventory.get(name, 0) < migrated[name]
    }
    if shortfalls:
        raise RuntimeError(f"strategy MySQL parity validation failed: {shortfalls}")
    cleanup_result = None
    if cleanup:
        cleanup_result = cleanup_redis(redis, fund_flow_mysql_repository, today=today)
    return {
        "before": before,
        "migrated": migrated,
        "mysql": mysql_inventory,
        "cleanup": cleanup_result,
        "after": inventory(redis),
    }


def migrate_strategy_pick(redis, mysql_repository):
    strategies = {}
    snapshots = {}
    events = {}
    for key in _keys(redis):
        text = _text(key)
        if text in {"策略选股:strategies", "strategy_pick:v1:strategies"}:
            payload = _json(redis.get(key), [])
            for item in payload if isinstance(payload, list) else []:
                item = translate_legacy_strategy_pick(item) if text.startswith(LEGACY_STRATEGY_PREFIX) else item
                if isinstance(item, dict) and item.get("id"):
                    _choose(strategies, str(item["id"]), item, text.startswith(V1_STRATEGY_PREFIX))
            continue
        history = _HISTORY_RE.match(text)
        latest = _LATEST_RE.match(text)
        event_list = _EVENTS_RE.match(text)
        global_events = _GLOBAL_EVENTS_RE.match(text)
        if history:
            values = redis.lrange(key, 0, -1)
            for value in values:
                for snapshot in _flatten(_json(value, None)):
                    snapshot = _normalize(snapshot, history.group("strategy"), history.group("date"), legacy=not text.startswith(V1_STRATEGY_PREFIX))
                    if snapshot:
                        _choose(snapshots, _snapshot_key(snapshot), snapshot, text.startswith(V1_STRATEGY_PREFIX))
        elif latest:
            snapshot = _json(redis.get(key), None)
            snapshot = _normalize(snapshot, "eastmoney_default" if text == "策略选股:latest" else latest.group("strategy"), None, legacy=text.startswith(LEGACY_STRATEGY_PREFIX))
            if snapshot:
                _choose(snapshots, _snapshot_key(snapshot), snapshot, text.startswith(V1_STRATEGY_PREFIX))
        elif event_list:
            for value in redis.lrange(key, 0, -1):
                event = _json(value, None)
                event = translate_legacy_strategy_pick(event) if text.startswith(LEGACY_STRATEGY_PREFIX) else event
                if isinstance(event, dict):
                    strategy_id = str(event.get("strategyId") or event.get("strategy_id") or event_list.group("strategy"))
                    event_date = str(event.get("collectedDate") or event_list.group("date"))
                    _choose(events, _event_key(event, strategy_id, event_date), (strategy_id, event_date, event), text.startswith(V1_STRATEGY_PREFIX), payload=event)
        elif global_events:
            for value in redis.lrange(key, 0, -1):
                event = _json(value, None)
                event = translate_legacy_strategy_pick(event) if text.startswith(LEGACY_STRATEGY_PREFIX) else event
                if isinstance(event, dict) and event.get("strategyId"):
                    strategy_id = str(event["strategyId"])
                    event_date = str(event.get("collectedDate") or global_events.group("date"))
                    _choose(events, _event_key(event, strategy_id, event_date), (strategy_id, event_date, event), text.startswith(V1_STRATEGY_PREFIX), payload=event)

    strategies = {key: value for key, (_rank, value) in strategies.items()}
    snapshots = {key: value for key, (_rank, value) in snapshots.items()}
    events = {key: value for key, (_rank, value) in events.items()}
    for strategy_id, snapshot in snapshots.items():
        strategy = snapshot.get("strategyId")
        strategies.setdefault(strategy, {"id": strategy, "name": snapshot.get("strategyName") or strategy, "pageUrl": "", "enabled": True})
    definitions = list(strategies.values())
    if definitions:
        try:
            mysql_repository.save_strategies(definitions, replace=False)
        except TypeError:
            mysql_repository.save_strategies(definitions)

    events_by_snapshot = {}
    for strategy_id, event_date, event in events.values():
        events_by_snapshot.setdefault((strategy_id, event_date), []).append(event)
    latest = {}
    for snapshot in sorted(snapshots.values(), key=_snapshot_order):
        key = (snapshot["strategyId"], snapshot["collectedDate"])
        selected_events = events_by_snapshot.get(key, []) if key not in latest else []
        mysql_repository.save_collection(snapshot, selected_events)
        current = latest.get(snapshot["strategyId"])
        if current is None or _snapshot_order(snapshot) > _snapshot_order(current):
            latest[snapshot["strategyId"]] = snapshot
    return {
        "strategies": len(definitions),
        "snapshots": len(snapshots),
        "stocks": sum(len({stock.get("code") for stock in snapshot.get("stocks") or [] if stock.get("code")}) for snapshot in snapshots.values()),
        "events": len(events),
        "latest": latest,
    }


def verify_fund_flow_parity(redis, mysql_repository, *, today=None, flow_types=("industry", "concept")):
    today = str(today or date.today().strftime("%Y%m%d"))
    for key in _keys(redis):
        text = _text(key)
        match = re.match(r"^fund_flow:v1:(industry|concept):history:(\d{8})$", text)
        legacy_match = re.match(r"^fund_flow:(industry|concept):history:(\d{8})$", text)
        concept_match = re.match(r"^fund_flow_概念:(\d{8})$", text)
        if match:
            flow_type, trade_date = match.groups()
        elif legacy_match:
            flow_type, trade_date = legacy_match.groups()
        elif concept_match:
            flow_type, trade_date = "concept", concept_match.group(1)
        else:
            continue
        redis_history = _json(redis.get(key), None)
        if _canonical(redis_history) != _canonical(mysql_repository.history(flow_type, trade_date)):
            return False
    return True


def cleanup_redis(redis, mysql_repository, *, today=None, parity=None, cache_ttl_seconds=86400):
    if parity is None:
        parity = lambda: verify_fund_flow_parity(redis, mysql_repository, today=today)
    if not parity():
        raise RuntimeError("fund-flow parity validation failed; refusing Redis cleanup")
    today = str(today or date.today().strftime("%Y%m%d"))
    deleted = []
    for key in _keys(redis):
        text = _text(key)
        if _current_cache(redis, key, text, today):
            redis.expire(key, cache_ttl_seconds)
            continue
        if _retain(text, today, redis):
            continue
        if text.startswith(LEGACY_STRATEGY_PREFIX) or text.startswith("fund_flow:") and not text.startswith("fund_flow:v1:") or text.startswith("fund_flow_概念"):
            deleted.append(key)
            continue
        if text.startswith(V1_STRATEGY_PREFIX) and not _is_current_cache(text, today):
            deleted.append(key)
        elif text.startswith("fund_flow:v1:") and not _is_current_cache(text, today):
            deleted.append(key)
    if deleted:
        redis.delete(*deleted)
    return {"deleted": len(deleted), "remaining": inventory(redis)}


def inventory(redis):
    keys = [_text(key) for key in _keys(redis)]
    return {
        "total": len(keys),
        "legacy_strategy": sum(key.startswith(LEGACY_STRATEGY_PREFIX) for key in keys),
        "v1_strategy": sum(key.startswith(V1_STRATEGY_PREFIX) for key in keys),
        "legacy_fund_flow": sum(key.startswith("fund_flow:") and not key.startswith("fund_flow:v1:") or key.startswith("fund_flow_概念") for key in keys),
        "keys": sorted(keys),
    }


def _keys(redis):
    scan = getattr(redis, "scan_iter", None)
    return list(scan(match="*")) if callable(scan) else list(redis.keys("*"))


def _json(value, default):
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _flatten(value):
    if isinstance(value, list):
        return [item for nested in value for item in _flatten(nested)]
    return [value]


def _normalize(value, strategy_id, event_date, *, legacy):
    if not isinstance(value, dict):
        return None
    value = translate_legacy_strategy_pick(value) if legacy else dict(value)
    value.setdefault("strategyId", strategy_id)
    value.setdefault("collectedDate", event_date)
    value.setdefault("collectedTime", value.get("time") or "00:00:00")
    value.setdefault("stocks", [])
    value["stocks"] = [translate_legacy_strategy_pick(stock) if legacy else stock for stock in value["stocks"] if isinstance(stock, dict) and (stock.get("code") or stock.get("代码"))]
    for stock in value["stocks"]:
        stock.setdefault("code", stock.pop("代码", ""))
    value["strategyId"] = str(value.get("strategyId") or strategy_id)
    value["collectedDate"] = str(value.get("collectedDate") or event_date or "")
    return value if value["collectedDate"] else None


def _snapshot_key(snapshot):
    return (snapshot["strategyId"], snapshot["collectedDate"], snapshot.get("collectedTime") or "00:00:00")


def _snapshot_order(snapshot):
    return (snapshot.get("collectedDate", ""), snapshot.get("collectedTime", ""), len(json.dumps(snapshot, ensure_ascii=False, sort_keys=True)))


def _event_key(event, strategy_id, event_date):
    explicit = str(event.get("eventId") or "").strip()
    if explicit:
        return explicit
    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return "fallback:" + hashlib.sha256(f"{strategy_id}|{event_date}|{payload}".encode()).hexdigest()


def _choose(mapping, key, value, is_v1, *, payload=None):
    payload = value if payload is None else payload
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    rank = (1 if is_v1 else 0, len(canonical), canonical)
    if key not in mapping or rank > mapping[key][0]:
        mapping[key] = (rank, value)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _is_current_cache(key, today):
    return today in key and (":history:" in key or ":events:" in key or ":chart:" in key)


def _current_cache(redis, key, text, today):
    if not (text.startswith(V1_STRATEGY_PREFIX) or text.startswith("fund_flow:v1:")):
        return False
    if _is_current_cache(text, today):
        return True
    if not text.endswith(":latest"):
        return False
    payload = _json(redis.get(key), {})
    return isinstance(payload, dict) and str(payload.get("collectedDate") or payload.get("trade_date") or "") == today


def _retain(key, today, redis):
    marker = any(token in key.lower() for token in ("lock", "completion", "completed", "migration", "normalized"))
    return marker and redis.ttl(key) > 0


def _text(value):
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)
