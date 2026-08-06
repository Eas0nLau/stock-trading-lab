import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

项目根目录 = Path(__file__).resolve().parents[1]
sys.path.append(str(项目根目录))

from utils import account, common, db


策略名称 = '20260630_全场景能力策略Demo'
开始日期 = 20260601
结束日期 = int(datetime.now().strftime('%Y%m%d'))

# ===== 回测和选股参数 =====
回看交易日数 = 280
候选返回数量 = 20
成交额下限 = 500000  # daily_quotes.amount 单位通常为千元，500000 约等于 5 亿成交额
最新流通市值下限 = 1000000  # circ_mv 单位万元，1000000 约等于 100 亿
近几日不允许跌停 = 5
近几日涨停次数上限 = 2
新高周期 = 60
回踩周期 = 20

# ===== 买入参数 =====
最大仓位数 = 5
单日最多买入数 = 2
允许重复买入 = False
买入执行时间列表 = ['开盘', '收盘']  # 可选：['开盘']、['收盘']、['开盘', '收盘']
买入执行时间 = 买入执行时间列表  # 兼容旧写法：也支持直接写 '开盘' 或 '收盘'
买入方式 = '开盘价'  # 买入执行时间为“开盘”时可选：开盘价、计划价；“收盘”时固定按收盘价
开盘涨幅下限 = -2
开盘涨幅上限 = 5
开盘距离MA10上限 = 10
收盘涨幅下限 = -3
收盘涨幅上限 = 7
收盘距离MA10上限 = 12
一字板不买 = True
涨停开盘不买阈值 = 9.5
涨停收盘不买阈值 = 9.5

# ===== 卖出和减仓参数 =====
卖出执行时间列表 = ['开盘', '收盘']  # 可选：['开盘']、['收盘']、['开盘', '收盘']
卖出执行时间 = 卖出执行时间列表  # 兼容旧写法：也支持直接写 '开盘' 或 '收盘'
卖出均线天数 = 10
买入时设置止损位 = True
止损位模式 = '更严格'  # 可选：固定比例、信号防守价、更严格、更宽松
止损比例 = -7
强制止盈比例 = 35
减半仓盈利阈值 = 20
盈利回撤阈值 = -8
最大持仓天数 = 10


def _sql_in(值列表):
    值列表 = [int(i) for i in 值列表]
    return str(tuple(值列表)).replace(',)', ')')


def _提取整数代码(代码列表):
    if 代码列表 is None:
        return set()
    if isinstance(代码列表, pd.DataFrame):
        if 'ts_code' in 代码列表.columns:
            代码列表 = 代码列表['ts_code']
        elif 'symbol' in 代码列表.columns:
            代码列表 = 代码列表['symbol']
        else:
            return set()
    代码序列 = pd.Series(list(代码列表)).astype(str).str.extract(r'(\d+)')[0].dropna()
    if 代码序列.empty:
        return set()
    return set(代码序列.astype(int).tolist())


def _最近交易日(结束日期参数, 天数):
    查询结果 = db.mysql_localhost(
        sql=f"""
            SELECT DISTINCT trade_date
            FROM daily_quotes
            WHERE trade_date <= {int(结束日期参数)}
            ORDER BY trade_date DESC
            LIMIT {int(天数)}
        """,
        fetch=True,
    )
    交易日列表 = sorted([int(row['trade_date']) for row in 查询结果])
    if len(交易日列表) < 天数:
        raise ValueError(f'交易日不足 {天数} 天，当前只有 {len(交易日列表)} 天')
    return 交易日列表


def _加载日线数据(filtered_codes, 交易日列表):
    股票代码列表 = sorted(_提取整数代码(filtered_codes))
    代码过滤条件 = ''
    if 股票代码列表:
        代码过滤条件 = f"AND sd.ts_code IN {_sql_in(股票代码列表)}"

    查询语句 = f"""
        SELECT
            sd.ts_code,
            sd.stock_name,
            sd.trade_date,
            sd.open_price AS open,
            sd.high_price AS high,
            sd.low_price AS low,
            sd.close_price AS close,
            sd.previous_close AS pre_close,
            sd.change_amount AS change,
            sd.change_pct AS pct_chg,
            sd.volume AS vol,
            sd.turnover AS amount,
            mv.最新流通市值,
            sb.market,
            sb.list_status
        FROM daily_quotes sd
        LEFT JOIN securities sb ON sd.ts_code = sb.symbol
        LEFT JOIN (
            SELECT latest_sd.ts_code, latest_sd.circulating_market_value AS 最新流通市值
            FROM daily_quotes latest_sd
            INNER JOIN (
                SELECT MAX(trade_date) AS 最新市值日期
                FROM daily_quotes
                WHERE circulating_market_value IS NOT NULL
            ) latest_date ON latest_sd.trade_date = latest_date.最新市值日期
        ) mv ON sd.ts_code = mv.ts_code
        WHERE sd.trade_date IN {_sql_in(交易日列表)}
          {代码过滤条件}
          AND sb.market = '主板'
          AND sb.list_status = 'L'
          AND sd.stock_name NOT REGEXP 'ST|退'
          AND sd.previous_close > 0
          AND sd.open_price IS NOT NULL
          AND sd.high_price IS NOT NULL
          AND sd.low_price IS NOT NULL
          AND sd.close_price IS NOT NULL
          AND sd.turnover IS NOT NULL
          AND sd.change_pct IS NOT NULL
        ORDER BY sd.ts_code, sd.trade_date
    """
    return pd.read_sql(查询语句, db.engine)


def _计算指标(日线数据):
    日线数据 = 日线数据.copy()
    日线数据['ts_code'] = 日线数据['ts_code'].astype(int)
    日线数据 = 日线数据.sort_values(['ts_code', 'trade_date'])
    分组 = 日线数据.groupby('ts_code', group_keys=False)

    for 均线天数 in [5, 10, 20, 60]:
        日线数据[f'ma{均线天数}'] = 分组['close'].transform(
            lambda s, n=均线天数: s.rolling(n, min_periods=n).mean()
        )

    日线数据['成交额MA5'] = 分组['amount'].transform(lambda s: s.rolling(5, min_periods=5).mean())
    日线数据['近60日最高收盘'] = 分组['close'].transform(
        lambda s: s.rolling(新高周期, min_periods=新高周期).max()
    )
    日线数据['近20日最低价'] = 分组['low'].transform(
        lambda s: s.rolling(回踩周期, min_periods=回踩周期).min()
    )
    日线数据['近5日涨跌幅'] = 分组['close'].transform(lambda s: (s / s.shift(5) - 1) * 100)
    日线数据['近10日涨跌幅'] = 分组['close'].transform(lambda s: (s / s.shift(10) - 1) * 100)
    日线数据['MA5连续3日抬高'] = 分组['ma5'].transform(
        lambda s: (s > s.shift(1)) & (s.shift(1) > s.shift(2))
    )
    日线数据['MA10连续3日抬高'] = 分组['ma10'].transform(
        lambda s: (s > s.shift(1)) & (s.shift(1) > s.shift(2))
    )
    日线数据['是否涨停'] = 日线数据['pct_chg'] >= 9.5
    日线数据['是否跌停'] = 日线数据['pct_chg'] <= -9.5
    日线数据['是否一字'] = (
        (日线数据['open'] == 日线数据['high'])
        & (日线数据['open'] == 日线数据['low'])
        & (日线数据['open'] == 日线数据['close'])
    )
    日线数据['近5日涨停次数'] = 分组['是否涨停'].transform(
        lambda s: s.rolling(5, min_periods=1).sum()
    )
    日线数据['近5日跌停次数'] = 分组['是否跌停'].transform(
        lambda s: s.rolling(近几日不允许跌停, min_periods=1).sum()
    )
    return 日线数据


def _打信号类型(当日数据):
    强趋势突破 = (
        (当日数据['close'] > 当日数据['ma5'])
        & (当日数据['ma5'] > 当日数据['ma10'])
        & (当日数据['ma10'] > 当日数据['ma20'])
        & (当日数据['close'] >= 当日数据['近60日最高收盘'])
        & (当日数据['pct_chg'].between(2, 9.3))
        & (当日数据['近5日涨跌幅'] <= 25)
        & (当日数据['MA5连续3日抬高'])
        & (当日数据['MA10连续3日抬高'])
    )
    爆量回踩 = (
        (当日数据['close'] > 当日数据['ma10'])
        & (当日数据['ma10'] > 当日数据['ma20'])
        & (当日数据['amount'] >= 当日数据['成交额MA5'] * 1.2)
        & (当日数据['low'] <= 当日数据['ma10'] * 1.03)
        & (当日数据['close'] >= 当日数据['ma10'])
        & (当日数据['pct_chg'].between(-2, 5))
    )
    止跌反转 = (
        (当日数据['近5日涨跌幅'] <= -5)
        & (当日数据['close'] > 当日数据['open'])
        & (当日数据['close'] > 当日数据['ma5'])
        & (当日数据['pct_chg'].between(0, 5))
        & (当日数据['近5日跌停次数'] == 0)
    )

    当日数据 = 当日数据.copy()
    当日数据['信号类型'] = ''
    当日数据.loc[强趋势突破, '信号类型'] = '强趋势突破'
    当日数据.loc[爆量回踩 & (当日数据['信号类型'] == ''), '信号类型'] = '爆量回踩'
    当日数据.loc[止跌反转 & (当日数据['信号类型'] == ''), '信号类型'] = '止跌反转'
    当日数据['是否有信号'] = 当日数据['信号类型'] != ''
    return 当日数据


def strategy(filtered_codes, target_date):
    """
    Demo选股层：覆盖趋势突破、爆量回踩、止跌反转三类典型信号。
    这个文件用于展示能力模板，不代表这些参数已经优化。
    """
    target_date = int(target_date)
    logger.warning(f"【{策略名称}】开始筛选 {target_date} ...")
    logger.info(
        f"参数 | 成交额下限:{成交额下限} 最新流通市值下限:{最新流通市值下限} "
        f"候选:{候选返回数量} 仓位:{最大仓位数} 单日买入:{单日最多买入数} "
        f"买入执行:{买入执行时间} 卖出执行:{卖出执行时间}"
    )

    try:
        交易日列表 = _最近交易日(target_date, 回看交易日数)
    except ValueError as 异常:
        logger.warning(f"{target_date} 数据不足：{异常}")
        return pd.DataFrame([])

    日线数据 = _加载日线数据(filtered_codes, 交易日列表)
    if 日线数据.empty:
        logger.warning(f"{target_date} 无足够日线数据")
        return pd.DataFrame([])

    日线数据 = _计算指标(日线数据)
    当日数据 = 日线数据[日线数据['trade_date'] == target_date].copy()
    if 当日数据.empty:
        logger.warning(f"{target_date} 当日日线为空")
        return pd.DataFrame([])

    当日数据 = _打信号类型(当日数据)
    基础过滤 = (
        (当日数据['amount'] >= 成交额下限)
        & (当日数据['最新流通市值'] >= 最新流通市值下限)
        & (当日数据['近5日跌停次数'] == 0)
        & (当日数据['近5日涨停次数'] <= 近几日涨停次数上限)
        & (~当日数据['是否涨停'])
        & (~当日数据['是否跌停'])
        & (~当日数据['是否一字'])
        & 当日数据[['ma5', 'ma10', 'ma20', '成交额MA5']].notna().all(axis=1)
    )

    选中数据 = 当日数据[基础过滤 & 当日数据['是否有信号']].copy()
    if 选中数据.empty:
        logger.error(f"{target_date} 未筛选到符合 demo 策略的股票")
        return pd.DataFrame([])

    选中数据['计划买入价'] = 选中数据['ma10']
    选中数据['防守价'] = 选中数据[['low', 'ma20']].min(axis=1)
    选中数据['目标价'] = 选中数据['close'] * (1 + 减半仓盈利阈值 / 100)
    选中数据['综合评分'] = (
        选中数据['amount'].rank(ascending=True, pct=True) * 40
        + 选中数据['最新流通市值'].rank(ascending=True, pct=True) * 30
        + 选中数据['pct_chg'].rank(ascending=True, pct=True) * 20
        - 选中数据['近5日涨跌幅'].clip(lower=0) * 0.2
    )
    选中数据 = 选中数据.sort_values(
        ['综合评分', 'amount', '最新流通市值'],
        ascending=False,
        kind='mergesort',
    ).head(候选返回数量).reset_index(drop=True)
    选中数据['排序'] = 选中数据.index + 1

    logger.warning(f"{target_date} 【{策略名称}】最终选中 {len(选中数据)} 只股票")
    logger.warning(f"入选股票：{' '.join(选中数据['stock_name'].astype(str).tolist())}")
    for _, 行 in 选中数据.iterrows():
        logger.info(
            f"   → 候选 {行['stock_name']} {int(行['ts_code'])} | "
            f"排序:{int(行['排序'])} | 信号:{行['信号类型']} | "
            f"成交额:{行['amount']:.2f} | 市值:{行['最新流通市值']:.2f} | "
            f"涨幅:{行['pct_chg']:.2f}% | close:{行['close']:.2f} | "
            f"MA5:{行['ma5']:.2f} MA10:{行['ma10']:.2f} MA20:{行['ma20']:.2f} | "
            f"计划买入价:{行['计划买入价']:.2f} 防守价:{行['防守价']:.2f} 目标价:{行['目标价']:.2f}"
        )

    return 选中数据[[
        'ts_code', 'stock_name', 'trade_date', '信号类型',
        'open', 'high', 'low', 'close', 'pre_close',
        'pct_chg', 'amount', '最新流通市值',
        'ma5', 'ma10', 'ma20', 'ma60',
        '近5日涨跌幅', '近10日涨跌幅', '近5日涨停次数', '近5日跌停次数',
        '计划买入价', '防守价', '目标价', '综合评分', '排序',
    ]]


def _当前持仓数量():
    return sum(1 for 持仓 in account.holding_stocks.values() if 持仓.get('lots', 0) > 0)


def _减半仓股数(lots):
    return (int(lots) // 200) * 100


def _标准化执行时间列表(执行时间配置, 参数名):
    if isinstance(执行时间配置, str):
        执行时间列表 = [执行时间配置]
    else:
        执行时间列表 = list(执行时间配置)

    if not 执行时间列表:
        raise ValueError(f"{参数名}不能为空")
    for 执行时间 in 执行时间列表:
        if 执行时间 not in ('开盘', '收盘'):
            raise ValueError(f"{参数名}只能包含 开盘/收盘，当前为：{执行时间配置}")
    return 执行时间列表


def _校验执行时间配置():
    _标准化执行时间列表(买入执行时间, '买入执行时间')
    _标准化执行时间列表(卖出执行时间, '卖出执行时间')
    if 止损位模式 not in ('固定比例', '信号防守价', '更严格', '更宽松'):
        raise ValueError(f"止损位模式只能是 固定比例/信号防守价/更严格/更宽松，当前为：{止损位模式}")


def _当日已买入数量(now_date):
    return sum(
        1
        for 持仓 in account.holding_stocks.values()
        if 持仓.get('lots', 0) > 0 and int(持仓.get('买入日期', 0)) == int(now_date)
    )


def _计算买入止损价(买入价, 信号防守价):
    固定比例止损价 = 买入价 * (1 + 止损比例 / 100)
    if not 买入时设置止损位:
        return None, 固定比例止损价, 信号防守价
    if 止损位模式 == '固定比例':
        return 固定比例止损价, 固定比例止损价, 信号防守价
    if 止损位模式 == '信号防守价':
        return 信号防守价, 固定比例止损价, 信号防守价
    if 止损位模式 == '更严格':
        return max(固定比例止损价, 信号防守价), 固定比例止损价, 信号防守价
    if 止损位模式 == '更宽松':
        return min(固定比例止损价, 信号防守价), 固定比例止损价, 信号防守价
    raise ValueError(f"不支持的止损位模式：{止损位模式}")


def buy(name, code, price, buy_date, close_price, signal_row):
    code = int(code)
    if not 允许重复买入 and code in account.holding_stocks:
        logger.error(f"{name} {code} 已经买过，本 demo 不允许重复买，不买了。")
        return False
    if code in account.holding_stocks and account.holding_stocks[code].get('lots', 0) > 0:
        logger.error(f"{name} {code} 当前仍有持仓，不买了。")
        return False
    if _当前持仓数量() >= 最大仓位数:
        logger.error(f"{name} {code} 当前持仓已达到 {最大仓位数} 仓，不买了。")
        return False

    最大买入金额 = (account.available_amount + account.market_value) / 最大仓位数
    if 最大买入金额 > account.available_amount:
        最大买入金额 = account.available_amount
    logger.info(
        f"可用金额：{account.available_amount} 目前市值：{account.market_value} "
        f"最大买入金额：{最大买入金额}"
    )
    lots = account.计算最大可买手数(price=price, price_max=最大买入金额)
    if lots == 0:
        logger.error(f"{name} {code} 最大可买手数为:{lots}，不买了。")
        return False

    buy_price = round(price * lots, 3)
    logger.warning(
        f"{name} {code} 股价：{price} 买入：{lots}股 买入金额：{buy_price} 尝试买入，"
        f"买入前 市值：{account.market_value} 可用金额：{account.available_amount} "
    )
    if buy_price > account.available_amount:
        logger.error(f"买入失败，可用金额不足：{account.available_amount}")
        return False

    account.available_amount = account.available_amount - buy_price
    account.market_value += buy_price
    if account.min_available_amount >= account.available_amount:
        account.min_available_amount = account.available_amount
    logger.warning(
        f"{name} {code} 股价：{price} 买入：{lots}股 买入金额：{buy_price} 买入成功，"
        f"买入后 市值：{account.market_value} 可用金额：{account.available_amount}"
    )

    信号防守价 = float(signal_row['防守价'])
    止损价, 固定比例止损价, 信号防守价 = _计算买入止损价(price, 信号防守价)

    account.holding_stocks[code] = {
        'name': name,
        'code': code,
        'lots': lots,
        'market_value': buy_price,
        '持股天数': 1,
        '成本价': buy_price,
        '盈亏比': 0,
        '盈亏': 0,
        '买入日期': int(buy_date),
        '卖出日期': None,
        '持仓最高市值': buy_price,
        '持仓最高回撤': 0,
        '是否发生除权': "否",
        'close_price': close_price,
        '买入价': price,
        '信号日期': int(signal_row['trade_date']),
        '信号类型': signal_row['信号类型'],
        '信号MA5': float(signal_row['ma5']),
        '信号MA10': float(signal_row['ma10']),
        '信号MA20': float(signal_row['ma20']),
        '防守价': 信号防守价,
        '信号防守价': 信号防守价,
        '固定比例止损价': 固定比例止损价,
        '止损价': 止损价,
        '止损位模式': 止损位模式,
        '目标价': float(signal_row['目标价']),
        '是否已减半仓': False,
        '卖出原因': None,
    }
    logger.warning(
        f"{name} {code} 买入后设置止损位 | 模式:{止损位模式} "
        f"固定比例止损价:{固定比例止损价:.2f} 信号防守价:{信号防守价:.2f} "
        f"最终止损价:{止损价 if 止损价 is not None else '未启用'}"
    )
    return True


def simulated_buy(now_date=None, 执行时间=None, 是否清空预选池=True):
    执行时间 = 执行时间 or _标准化执行时间列表(买入执行时间, '买入执行时间')[0]
    selected_stocks = account.next_date_pre_selection_stocks['selected_stocks']
    target_date = account.next_date_pre_selection_stocks['target_date']
    if selected_stocks is None or target_date is None:
        logger.error("下一日预选买入池 为空")
        return

    target_date = int(target_date)
    buy_date = common.get_next_date(target_date)
    if buy_date is None:
        logger.warning(f"{target_date} 无下一交易日，不买")
        account.next_date_pre_selection_stocks = {'selected_stocks': None, 'target_date': None}
        return
    if now_date is not None and int(now_date) != int(buy_date):
        logger.warning(f"当前日期 {now_date} 不是预选池买入日 {buy_date}，暂不处理买入池")
        return

    查询语句 = f"""
        SELECT ts_code, trade_date, close_price AS close, stock_name, open_price AS open, previous_close AS pre_close, high_price AS high, low_price AS low
        FROM daily_quotes
        WHERE ts_code IN {_sql_in(selected_stocks['ts_code'].tolist())}
          AND trade_date = {int(buy_date)}
    """
    买入日数据 = pd.read_sql(查询语句, db.engine)
    买入数量 = _当日已买入数量(buy_date)
    selected_stocks = selected_stocks.sort_values('综合评分', ascending=False, kind='mergesort')

    for _, 候选 in selected_stocks.iterrows():
        if 买入数量 >= 单日最多买入数:
            break
        if _当前持仓数量() >= 最大仓位数:
            logger.warning(f"当前持仓已达到 {最大仓位数} 仓，停止买入")
            break

        ts_code = int(候选['ts_code'])
        stock_name = str(候选['stock_name'])
        if not 允许重复买入 and ts_code in account.holding_stocks:
            logger.error(f"{stock_name} {ts_code} 已经买过，本 demo 不允许重复买，跳过")
            continue

        个股买入日数据 = 买入日数据[买入日数据['ts_code'] == ts_code]
        if 个股买入日数据.empty:
            logger.error(f"{stock_name} {buy_date} 买入日日线为空")
            continue
        买入日 = 个股买入日数据.iloc[0]

        open_price = float(买入日['open'])
        high_price = float(买入日['high'])
        low_price = float(买入日['low'])
        close_price = float(买入日['close'])
        pre_close = float(买入日['pre_close'])
        开盘涨幅 = (open_price / pre_close - 1) * 100
        收盘涨幅 = (close_price / pre_close - 1) * 100

        if 一字板不买 and open_price == high_price == low_price == close_price:
            logger.error(f"{stock_name} {buy_date} 一字板，不买")
            continue

        信号MA10 = float(候选['ma10'])
        开盘距离MA10 = abs(open_price / 信号MA10 - 1) * 100
        收盘距离MA10 = abs(close_price / 信号MA10 - 1) * 100

        if 执行时间 == '开盘':
            if 开盘涨幅 >= 涨停开盘不买阈值:
                logger.error(f"{stock_name} {buy_date} 开盘涨幅 {开盘涨幅:.2f}% 接近涨停，不买")
                continue
            if not (开盘涨幅下限 <= 开盘涨幅 <= 开盘涨幅上限):
                logger.error(
                    f"{stock_name} {buy_date} 开盘涨幅 {开盘涨幅:.2f}% 不在 "
                    f"{开盘涨幅下限}%~{开盘涨幅上限}% 之间，不买"
                )
                continue
            if 开盘距离MA10 > 开盘距离MA10上限:
                logger.error(
                    f"{stock_name} {buy_date} 开盘价 {open_price:.2f} 距离信号MA10 "
                    f"{信号MA10:.2f} 为 {开盘距离MA10:.2f}%，超过 {开盘距离MA10上限}%，不买"
                )
                continue
        elif 执行时间 == '收盘':
            if 收盘涨幅 >= 涨停收盘不买阈值:
                logger.error(f"{stock_name} {buy_date} 收盘涨幅 {收盘涨幅:.2f}% 接近涨停，不买")
                continue
            if not (收盘涨幅下限 <= 收盘涨幅 <= 收盘涨幅上限):
                logger.error(
                    f"{stock_name} {buy_date} 收盘涨幅 {收盘涨幅:.2f}% 不在 "
                    f"{收盘涨幅下限}%~{收盘涨幅上限}% 之间，不买"
                )
                continue
            if 收盘距离MA10 > 收盘距离MA10上限:
                logger.error(
                    f"{stock_name} {buy_date} 收盘价 {close_price:.2f} 距离信号MA10 "
                    f"{信号MA10:.2f} 为 {收盘距离MA10:.2f}%，超过 {收盘距离MA10上限}%，不买"
                )
                continue
        else:
            raise ValueError(f"不支持的买入执行时间：{执行时间}")

        if 执行时间 == '开盘' and 买入方式 == '计划价':
            计划买入价 = float(候选['计划买入价'])
            if low_price > 计划买入价 or high_price < 计划买入价:
                logger.error(
                    f"{stock_name} {buy_date} 未触及计划买入价 {计划买入价:.2f}，"
                    f"当日低:{low_price:.2f} 高:{high_price:.2f}，不买"
                )
                continue
            buy_price = open_price if open_price <= 计划买入价 else 计划买入价
        elif 执行时间 == '收盘':
            buy_price = close_price
        else:
            buy_price = open_price

        当天收盘收益率 = (close_price / buy_price - 1) * 100
        buy_status = buy(
            stock_name,
            ts_code,
            price=buy_price,
            buy_date=int(buy_date),
            close_price=close_price,
            signal_row=候选,
        )
        if buy_status:
            买入数量 += 1
            logger.warning(
                f"{stock_name} {buy_date} 信号:{候选['信号类型']} 买入时间:{执行时间} 买入方式:{买入方式} "
                f"买入价:{buy_price:.2f} 开盘涨幅:{开盘涨幅:.2f}% "
                f"收盘涨幅:{收盘涨幅:.2f}% 开盘距MA10:{开盘距离MA10:.2f}% "
                f"收盘距MA10:{收盘距离MA10:.2f}% 当天收盘收益率:{当天收盘收益率:.2f}%"
            )
        else:
            logger.error(f"{stock_name} {buy_date} 买入失败")

    if 是否清空预选池:
        account.next_date_pre_selection_stocks = {
            'selected_stocks': None,
            'target_date': None,
        }


def _清仓(持仓信息, ts_code, price, now_date, 原因):
    持仓信息['卖出原因'] = 原因
    logger.error(
        f"{ts_code} {持仓信息['name']} 清仓 | 原因:{原因} 价格:{price:.2f} "
        f"盈亏比:{持仓信息['盈亏比']:.2f}%"
    )
    account.sell(持仓信息['name'], ts_code, price, 持仓信息['lots'], int(now_date))


def _减半仓(持仓信息, ts_code, price, now_date, 原因):
    减仓股数 = _减半仓股数(持仓信息['lots'])
    if 减仓股数 <= 0:
        logger.error(f"{ts_code} {持仓信息['name']} 触发减半仓但持仓不足 200 股，无法减")
        return False
    持仓信息['卖出原因'] = 原因
    logger.warning(
        f"{ts_code} {持仓信息['name']} 减半仓 | 原因:{原因} 价格:{price:.2f} "
        f"卖出股数:{减仓股数} 盈亏比:{持仓信息['盈亏比']:.2f}%"
    )
    account.sell(持仓信息['name'], ts_code, price, 减仓股数, int(now_date))
    account.holding_stocks[ts_code]['是否已减半仓'] = True
    return True


def simulated_sell(now_date=None, 执行时间=None):
    执行时间 = 执行时间 or _标准化执行时间列表(卖出执行时间, '卖出执行时间')[0]
    logger.warning(f"检查持仓卖出/减仓逻辑 开始 | 执行时间:{执行时间}")
    持仓代码列表 = [int(code) for code, 持仓 in account.holding_stocks.items() if 持仓.get('lots', 0) > 0]
    if not 持仓代码列表:
        logger.warning("检查持仓卖出/减仓逻辑 完成")
        return

    try:
        交易日列表 = _最近交易日(now_date, max(80, 卖出均线天数 + 5))
    except ValueError as 异常:
        logger.warning(f"{now_date} 卖出检查数据不足：{异常}")
        return

    日线数据 = _加载日线数据(持仓代码列表, 交易日列表)
    if 日线数据.empty:
        logger.warning(f"{now_date} 持仓日线为空")
        return

    日线数据 = _计算指标(日线数据)
    当日数据 = 日线数据[日线数据['trade_date'] == int(now_date)].copy()

    for ts_code in 持仓代码列表:
        持仓信息 = account.holding_stocks[ts_code]
        if 持仓信息['lots'] == 0:
            continue
        if 持仓信息['买入日期'] == int(now_date):
            logger.error(f"{ts_code} {持仓信息['name']} 买入当天不卖")
            continue

        个股当日数据 = 当日数据[当日数据['ts_code'] == ts_code]
        if 个股当日数据.empty:
            logger.error(f"{ts_code} {持仓信息['name']} {now_date} 当日数据为空")
            continue
        个股历史 = 日线数据[日线数据['ts_code'] == ts_code].sort_values('trade_date')
        个股昨日数据 = 个股历史[个股历史['trade_date'] < int(now_date)].tail(1)
        if 执行时间 == '开盘' and 个股昨日数据.empty:
            logger.error(f"{ts_code} {持仓信息['name']} {now_date} 无昨日数据，无法开盘卖出判断")
            continue
        个股当日 = 个股当日数据.iloc[0]

        close_price = float(个股当日['close'])
        open_price = float(个股当日['open'])
        low_price = float(个股当日['low'])
        if 执行时间 == '开盘':
            操作价格 = open_price
            均线参考 = float(个股昨日数据.iloc[0][f'ma{卖出均线天数}'])
            均线说明 = f"昨日MA{卖出均线天数}"
        elif 执行时间 == '收盘':
            操作价格 = close_price
            均线参考 = float(个股当日[f'ma{卖出均线天数}'])
            均线说明 = f"当日MA{卖出均线天数}"
        else:
            raise ValueError(f"不支持的卖出执行时间：{执行时间}")

        if pd.isna(均线参考):
            logger.error(f"{ts_code} {持仓信息['name']} {now_date} {均线说明}为空，跳过卖出判断")
            continue

        买入价 = float(持仓信息.get('买入价', 持仓信息['成本价'] / 持仓信息['lots']))
        防守价 = float(持仓信息.get('防守价', 买入价 * (1 + 止损比例 / 100)))
        止损价 = 持仓信息.get('止损价')
        if 止损价 is None:
            止损价, _, _ = _计算买入止损价(买入价, 防守价)
        if 止损价 is None:
            止损价 = 买入价 * (1 + 止损比例 / 100)
        止损价 = float(止损价)
        当前盈亏比 = float(持仓信息.get('盈亏比', 0))
        持仓最高回撤 = float(持仓信息.get('持仓最高回撤', 0))

        if 操作价格 <= 止损价:
            _清仓(持仓信息, ts_code, 操作价格, now_date, f"{执行时间}跌破止损价 {止损价:.2f}")
            continue
        if 执行时间 == '收盘' and low_price <= 止损价:
            _清仓(持仓信息, ts_code, 止损价, now_date, f"日内触发止损价 {止损价:.2f}")
            continue
        if 操作价格 < 均线参考:
            _清仓(
                持仓信息,
                ts_code,
                操作价格,
                now_date,
                f"{执行时间}跌破{均线说明}: price={操作价格:.2f}, {均线说明}={均线参考:.2f}",
            )
            continue
        if 当前盈亏比 >= 强制止盈比例:
            _清仓(持仓信息, ts_code, 操作价格, now_date, f"达到强制止盈 {当前盈亏比:.2f}%")
            continue
        if 当前盈亏比 > 0 and 持仓最高回撤 <= 盈利回撤阈值:
            _清仓(持仓信息, ts_code, 操作价格, now_date, f"盈利后回撤 {持仓最高回撤:.2f}%")
            continue
        if 当前盈亏比 >= 减半仓盈利阈值 and not 持仓信息.get('是否已减半仓', False):
            _减半仓(持仓信息, ts_code, 操作价格, now_date, f"盈利超过{减半仓盈利阈值}%")
            continue
        if 持仓信息['持股天数'] >= 最大持仓天数 and 当前盈亏比 < 减半仓盈利阈值:
            _清仓(持仓信息, ts_code, 操作价格, now_date, f"持仓超过{最大持仓天数}天且未进入强势盈利")
            continue

    logger.warning(f"检查持仓卖出/减仓逻辑 完成 | 执行时间:{执行时间}")


def process_daily(target_date=None, filtered_codes=None):
    _校验执行时间配置()
    买入时点列表 = _标准化执行时间列表(买入执行时间, '买入执行时间')
    卖出时点列表 = _标准化执行时间列表(卖出执行时间, '卖出执行时间')

    # 开盘前同步持仓到开盘价，再做开盘卖出/买入。
    account.sync_open_market_before(now_date=target_date)
    if '开盘' in 卖出时点列表:
        simulated_sell(now_date=target_date, 执行时间='开盘')
    if '开盘' in 买入时点列表:
        simulated_buy(
            now_date=target_date,
            执行时间='开盘',
            是否清空预选池='收盘' not in 买入时点列表,
        )

    # 收盘后同步持仓到收盘价，再做收盘卖出/买入。
    account.sync_close_market(now_date=target_date)
    if '收盘' in 卖出时点列表:
        simulated_sell(now_date=target_date, 执行时间='收盘')
    if '收盘' in 买入时点列表:
        simulated_buy(now_date=target_date, 执行时间='收盘', 是否清空预选池=True)
    account.sync_close_market(now_date=target_date)

    selected_stocks = strategy(filtered_codes, target_date)
    if selected_stocks.empty:
        logger.error(f"{target_date} 未筛选到符合策略的股票")
        return
    account.add_next_date_stocks(selected_stocks, target_date)


def main(start_date=开始日期, end_date=结束日期):
    file_name = __file__.split(".py")[0].split("\\")[-1].split("/")[-1]
    common.process_for_strategy(start_date, end_date, process_daily, file_name)


if __name__ == "__main__":
    main(start_date=开始日期, end_date=结束日期)
