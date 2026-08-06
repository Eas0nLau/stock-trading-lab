from .contracts import translate_legacy_fund_flow


class FundFlowService:
    def __init__(self, repository):
        self.repository = repository

    def dates(self, flow_type):
        return {"status": "success", "flow_type": flow_type, "dates": self.repository.dates(flow_type)}

    def history(self, flow_type, trade_date):
        payload = self.repository.history(flow_type, trade_date)
        if payload is None:
            return {"status": "empty", "error_message": "No fund-flow history is available"}
        payload = translate_legacy_fund_flow(payload)
        if isinstance(payload, list):
            return build_matrix(payload)
        return payload

    def stream_events(self):
        return self.repository.stream_events()


def build_matrix(snapshots):
    times = []
    boards = {}
    for snapshot in snapshots:
        if not snapshot:
            continue
        time = snapshot[0].get("time")
        if not time:
            continue
        if time not in times:
            times.append(time)
        index = times.index(time)
        for item in snapshot:
            name = item.get("board_name")
            if not name:
                continue
            board = boards.setdefault(name, {"code": item.get("board_code", ""), "name": name, "points": []})
            board["points"].append([index, item.get("net_inflow_100m", 0), item.get("leader", "")])
    return {"format": "matrix-v2", "top_n": 0, "times": times, "boards": list(boards.values())}
