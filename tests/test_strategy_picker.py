from 实时监控 import 策略选股


def test_string_data_response_is_ignored_without_attribute_error():
    response = {"data": "captcha verification required"}

    assert 策略选股.解析策略选股接口响应(response) is None


def test_manual_verification_stops_retries(monkeypatch):
    attempts = []
    strategy = {"id": "gap", "名称": "跳空高开"}
    monkeypatch.setattr(策略选股, "获取策略配置", lambda strategy_id: strategy)

    def collect_once(_strategy):
        attempts.append(1)
        raise 策略选股.需要人工验证("东方财富需要人工滑块验证")

    monkeypatch.setattr(策略选股, "_单次策略选股采集", collect_once)
    monkeypatch.setattr(
        策略选股,
        "写入失败快照",
        lambda _strategy, error: {"状态": "failed", "错误信息": error},
    )

    result = 策略选股.策略选股采集("gap", 最大重试次数=3)

    assert len(attempts) == 1
    assert "人工" in result["错误信息"]


def test_page_verification_text_is_detected():
    class FakePage:
        def ele(self, selector, timeout=None):
            return object() if "拖动下方滑块完成拼图" in selector else None

    assert 策略选股.页面需要人工验证(FakePage()) is True


def test_page_verification_text_in_html_is_detected():
    class FakePage:
        html = "<div>拖动下方滑块完成拼图</div>"

        def ele(self, selector, timeout=None):
            return None

    assert 策略选股.页面需要人工验证(FakePage()) is True


def test_initializing_strategy_page_does_not_navigate(monkeypatch):
    calls = []
    monkeypatch.setattr(
        策略选股.driver_chrome,
        "初始化页面",
        lambda *args, **kwargs: calls.append((args, kwargs)) or object(),
    )

    策略选股.初始化策略页面({"id": "gap", "页面URL": "https://example.com"})

    assert calls == [(("策略选股:gap",), {"background": True})]
