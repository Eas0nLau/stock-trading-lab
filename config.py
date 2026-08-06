"""Legacy configuration exports.

New code must import ``stock_lab.config.get_settings`` instead.
"""

from stock_lab.config import get_settings


get_settings.cache_clear()
_settings = get_settings()

project_root = _settings.project_root
project_path = str(project_root)

mysql_localhost_host = _settings.mysql.host
mysql_localhost_port = _settings.mysql.port
mysql_localhost_user = _settings.mysql.user
mysql_localhost_password = _settings.mysql.password
mysql_localhost_database = _settings.mysql.database

ts_token_list = list(_settings.tushare_tokens)
ts_token = ts_token_list[0] if ts_token_list else ""
deepseek_api_key = _settings.deepseek_api_key
tdx_root = _settings.tdx_root

tdx_cache_refresh_interval_seconds = _settings.tdx_cache_refresh_interval_seconds
init_url = _settings.init_url
启动时关闭旧浏览器页面 = _settings.browser_close_old_tabs
资金流向采集间隔秒 = _settings.fund_flow_interval_seconds
资金流向历史返回Top数量 = _settings.fund_flow_history_top_n
东方财富概念排除名单 = list(_settings.concept_exclusions)
策略选股采集超时秒 = _settings.strategy_pick_timeout_seconds
策略选股采集最大重试次数 = _settings.strategy_pick_max_retries
热门板块情绪入选数量阈值 = _settings.hot_board_emotion_selection_threshold
热门板块情绪高潮数量阈值 = _settings.hot_board_emotion_climax_threshold
热门板块情绪强势延续晋级比例 = _settings.hot_board_emotion_strong_continuation_ratio
热门板块情绪排除板块 = list(_settings.hot_board_emotion_excluded_boards)

默认策略选股列表 = [
    {
        "id": "eastmoney_1",
        "名称": "新高监控",
        "页面URL": "https://xuangu.eastmoney.com/Result?id=xc1253a53b79c1004575&a=edit_way",
        "监听目标": ["/api/smart-tag/stock/v3/pw/search-code"],
        "监控时间段": [["09:20", "11:31"], ["13:00", "15:01"]],
        "监控频率秒": 30,
        "启用": True,
    },
    {
        "id": "eastmoney_2",
        "名称": "跳空高开",
        "页面URL": "https://xuangu.eastmoney.com/Result?id=xc130976a8770800ef4c&a=edit_way",
        "监听目标": ["/api/smart-tag/stock/v3/pw/search-code"],
        "监控时间段": [["09:20", "11:31"], ["13:00", "15:01"]],
        "监控频率秒": 30,
        "启用": True,
    },
]
