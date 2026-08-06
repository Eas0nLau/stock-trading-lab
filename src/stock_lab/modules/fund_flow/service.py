import heapq

from .contracts import translate_legacy_fund_flow


class FundFlowService:
    def __init__(self, repository, *, default_top_n=0):
        self.repository = repository
        self.default_top_n = max(int(default_top_n or 0), 0)

    def dates(self, flow_type):
        return {"status": "success", "flow_type": flow_type, "dates": self.repository.dates(flow_type)}

    def history(self, flow_type, trade_date, top_n=None):
        payload = self.repository.history(flow_type, trade_date)
        if payload is None:
            return {"status": "empty", "error_message": "No fund-flow history is available"}
        payload = translate_legacy_fund_flow(payload)
        if not isinstance(payload, list):
            return payload
        top_n = self.default_top_n if top_n is None else max(int(top_n), 0)
        if top_n <= 0:
            return build_matrix_v1(payload, top_n)
        cached = self.repository.cached_chart(flow_type, trade_date, top_n)
        if cached is not None:
            return cached
        compact = [filter_snapshot(snapshot, top_n) for snapshot in payload]
        result = build_matrix(compact, top_n)
        self.repository.save_chart(flow_type, trade_date, top_n, result)
        return result

    def stream_events(self):
        return self.repository.stream_events()


def filter_snapshot(snapshot, top_n):
    if top_n <= 0:
        return list(snapshot)
    inflow = []
    outflow = []
    for item in snapshot:
        try:
            amount = float(item.get("net_inflow_100m", 0) or 0)
        except (TypeError, ValueError):
            amount = 0
        if amount > 0:
            inflow.append((amount, item))
        elif amount < 0:
            outflow.append((amount, item))
    return [item for _amount, item in heapq.nlargest(top_n, inflow, key=lambda row: row[0])] + [
        item for _amount, item in heapq.nsmallest(top_n, outflow, key=lambda row: row[0])
    ]


def build_matrix(snapshots, top_n=0):
    times = []
    snapshots_by_time = {}
    for snapshot in snapshots:
        time = _snapshot_time(snapshot)
        if not time:
            continue
        if time not in snapshots_by_time:
            times.append(time)
        snapshots_by_time[time] = snapshot
    boards = {}
    for time_index, time in enumerate(times):
        for item in snapshots_by_time[time]:
            name = item.get("board_name")
            if not name:
                continue
            board = boards.setdefault(name, {"code": item.get("board_code", ""), "name": name, "points": []})
            board["points"].append([time_index, item.get("net_inflow_100m", 0), item.get("leader", "")])
    return {"format": "matrix-v2", "top_n": top_n, "times": times, "boards": list(boards.values())}


def build_matrix_v1(snapshots, top_n=0):
    times = []
    time_indexes = {}
    boards = {}
    for snapshot in snapshots:
        time = _snapshot_time(snapshot)
        if not time:
            continue
        if time not in time_indexes:
            time_indexes[time] = len(times)
            times.append(time)
            for board in boards.values():
                board["values"].append(None)
                board["leaders"].append("")
        time_index = time_indexes[time]
        for item in snapshot:
            name = item.get("board_name")
            if not name:
                continue
            board = boards.setdefault(name, {
                "code": item.get("board_code", ""),
                "name": name,
                "values": [None] * len(times),
                "leaders": [""] * len(times),
            })
            board["values"][time_index] = item.get("net_inflow_100m", 0)
            board["leaders"][time_index] = item.get("leader", "")
    return {"format": "matrix-v1", "top_n": top_n, "times": times, "boards": list(boards.values())}


def _snapshot_time(snapshot):
    if not isinstance(snapshot, list):
        return ""
    return next((item.get("time") for item in snapshot if item.get("time")), "")
