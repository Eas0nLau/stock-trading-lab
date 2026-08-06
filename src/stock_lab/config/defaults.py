DEFAULT_REDIS_HOST = "127.0.0.1"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DATABASE = 0
DEFAULT_TDX_CACHE_REFRESH_INTERVAL_SECONDS = 20
DEFAULT_INIT_URL = "http://localhost:8990"
DEFAULT_BROWSER_CLOSE_OLD_TABS = True
DEFAULT_FUND_FLOW_INTERVAL_SECONDS = 60
DEFAULT_FUND_FLOW_HISTORY_TOP_N = 10
DEFAULT_STRATEGY_PICK_TIMEOUT_SECONDS = 30
DEFAULT_STRATEGY_PICK_MAX_RETRIES = 3
DEFAULT_HOT_BOARD_EMOTION_SELECTION_THRESHOLD = 8
DEFAULT_HOT_BOARD_EMOTION_CLIMAX_THRESHOLD = 20
DEFAULT_HOT_BOARD_EMOTION_STRONG_CONTINUATION_RATIO = 0.5
DEFAULT_HOT_BOARD_EMOTION_EXCLUDED_BOARDS = ("ST板块", "公告", "其他")

DEFAULT_CONCEPT_EXCLUSIONS = (
    "AB股", "AH股", "A股", "B股", "H股", "创投",
    "HS300_", "沪股通", "深股通", "融资融券", "转融券标的",
    "大盘股", "中盘股", "小盘股", "周期股", "题材股", "趋势股",
    "大盘成长", "大盘价值", "中盘成长", "中盘价值", "小盘成长", "小盘价值",
    "权重股", "百元股", "基金重仓", "QFII重仓", "养老金", "社保重仓", "股权激励",
    "央国企改革", "国企改革", "富时罗素", "标准普尔", "MSCI中国",
    "深成500", "深证100R", "中证500", "中证1000", "中证2000",
    "上证180_", "上证50_", "上证380", "创业板综", "深证成指", "长期破净", "中特估", "国产芯片",
    "昨日高振幅", "昨日高换手", "昨日涨停", "昨日涨停_含一字", "昨日首板", "昨日连板", "参股银行",
    "最近多板", "近期强势", "近期新高", "百日新高", "历史新高", "IPO受益",
    "东方财富热股", "热门股", "行业龙头", "科技风格", "专精特新", "一带一路", "中俄贸易概念",
    "小米概念", "显示技术", "虚拟现实", "苹果概念", "智能穿戴", "荣耀概念", "混合现实",
    "华为概念", "智慧城市", "人工智能", "2025年报预增", "创业成份", "物联网",
    "基金重仓", "车联网(车路云)", "超清视频", "2026一季报预增", "湖北自贸", "行业龙头", "并购重组概念",
    "红利股", "独角兽", "央视50_", "机构重仓", "长江三角", "破净股", "金融地产风格",
)
