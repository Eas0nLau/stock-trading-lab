from stock_lab.modules.market_data import jiuyan


def test_jiuyan_request_interval_uses_randomized_window(monkeypatch):
    monkeypatch.setattr(jiuyan.random, "uniform", lambda low, high: 90.0)
    assert jiuyan.random.uniform(60, 105) == 90.0


def test_jiuyan_page_verification_detected_from_html():
    class Page:
        html = "<div>拖动下方滑块完成拼图</div>"

        def ele(self, selector, timeout=None):
            return None

    assert jiuyan.page_requires_human_verification(Page())
    assert issubclass(jiuyan.HumanVerificationRequired, jiuyan.IncompleteJiuyanResponse)
