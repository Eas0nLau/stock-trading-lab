from task import 每日更新 as daily


class RedisState:
    def __init__(self):
        self.values = {}

    def exists(self, key):
        return key in self.values

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def delete(self, key):
        self.values.pop(key, None)

    def eval(self, _script, _key_count, key, token):
        if self.values.get(key) != token:
            return 0
        self.delete(key)
        return 1


class Collector:
    def trading_dates(self, _limit):
        return [20260804, 20260805]

    def update_securities(self):
        return 1

    def update_daily_quotes(self, _start_date, _end_date):
        return 1

    def update_index_daily(self, _start_date, _end_date):
        return 1

    def collect_board_actions(self, _trade_date):
        return 1

    def update_market_cap(self, _trade_date):
        return {"status": "success", "updated": 1}

    def update_dde(self, _trade_date):
        return {"status": "success", "updated": 1, "failed": []}

    def update_kdj(self, _trade_date):
        return 1


def test_repeating_one_day_pipeline_is_idempotent():
    redis = RedisState()
    calls = []
    options = {
        "collector": Collector(),
        "state": redis,
        "run_hot_board": lambda *_args: calls.append("hot_board") or 1,
        "run_index": lambda *_args: calls.append("index_emotion") or 1,
    }

    first = daily.tasks(20260805, **options)
    second = daily.tasks(20260805, **options)

    assert first["status"] == "success"
    assert second["status"] == "skipped"
    assert calls.count("index_emotion") == 1
