from stock_lab.modules.tdx.universe import load_mainboard_non_st_codes, mainboard_non_st_codes


def test_mainboard_universe_filters_status_name_exchange_and_limit():
    rows = [
        {"ts_code": "600000.SH", "symbol": "600000", "name": "Good", "market": "主板", "list_status": "L"},
        {"ts_code": "000001.SZ", "symbol": "000001", "name": "ST Bad", "market": "主板", "list_status": "L"},
        {"ts_code": "300001.SZ", "symbol": "300001", "name": "Growth", "market": "创业板", "list_status": "L"},
        {"ts_code": "601000.SH", "symbol": "601000", "name": "Unlisted", "market": "主板", "list_status": "D"},
    ]

    assert mainboard_non_st_codes(rows, limit=1) == ["600000.SH"]


def test_repository_adapter_queries_canonical_securities_once():
    class Repository:
        def __init__(self):
            self.calls = []

        def securities(self, market=None):
            self.calls.append(market)
            return [{"ts_code": "600000.SH", "symbol": "600000", "name": "Good", "market": market, "list_status": "L"}]

    repository = Repository()

    assert load_mainboard_non_st_codes(repository) == ["600000.SH"]
    assert repository.calls == ["主板"]
