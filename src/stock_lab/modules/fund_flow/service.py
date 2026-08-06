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
        return translate_legacy_fund_flow(payload)
