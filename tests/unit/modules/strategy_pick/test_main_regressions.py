from stock_lab.modules.strategy_pick.source import (
    HumanVerificationRequired,
    StrategyPickSource,
    decode_response,
    page_requires_human_verification,
    parse_strategy_response,
)


def test_string_nested_response_is_ignored():
    payload = decode_response({"data": "captcha verification required"})
    assert parse_strategy_response(payload) is None


def test_page_verification_is_detected_from_element_or_html():
    class ElementPage:
        def ele(self, selector, timeout=None):
            return object() if "拖动下方滑块完成拼图" in selector else None

    class HtmlPage:
        html = "<div>拖动左边滑块完成上方拼图</div>"

        def ele(self, selector, timeout=None):
            return None

    assert page_requires_human_verification(ElementPage())
    assert page_requires_human_verification(HtmlPage())
    assert issubclass(HumanVerificationRequired, RuntimeError)


def test_strategy_source_retains_monitor_entrypoints():
    assert callable(StrategyPickSource.collect)
    assert callable(StrategyPickSource.run)
