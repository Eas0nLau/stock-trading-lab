import importlib


def test_hot_board_algorithm_wrapper_reads_refreshed_official_config(monkeypatch):
    wrapper = importlib.import_module("utils.热门板块情绪算法")
    monkeypatch.setattr(wrapper, "legacy_config_value", lambda name: {"热门板块入选数量阈值": 13}[name])
    monkeypatch.setattr(wrapper, "refresh_legacy_config", lambda: {"热门板块入选数量阈值": 13})

    assert wrapper.热门板块入选数量阈值 == 13
    assert wrapper.刷新运行配置() == {"热门板块入选数量阈值": 13}
