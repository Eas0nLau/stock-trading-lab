import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from utils import account, common, db


策略名称 = '20260706_三连阳趋势均线多头策略'
# 开始日期 = int(datetime.now().strftime('%Y%m%d'))
# 结束日期 = int(datetime.now().strftime('%Y%m%d'))
开始日期 = 20260720
结束日期 = int(datetime.now().strftime('%Y%m%d'))
# ===== 可调参数 =====
连续红盘天数 = 3
区间涨幅天数 = 3
区间涨幅下限 = 7
涨跌停过滤天数 = 5
涨停阈值 = 9.5
跌停阈值 = -9.5
均线周期列表 = [5, 10, 20, 30]
新高周期 = 120
回看交易日数 = 新高周期 + 20
成交额下限 = 100000
最大仓位数 = 5
单日最多买入数 = 1
买入开盘涨幅上限 = 7
买入开盘涨幅下限 = -3
买入开盘偏离MA5上限 = 5
减仓MA5乖离阈值 = 8
MA5乖离减仓比例 = 0.8
首日开盘浮盈减仓阈值 = 4
首日开盘浮盈减仓比例 = 0.5

# None 表示返回全部符合条件的股票；改成整数则只返回前 N 只。
每日候选数量 = None

# ===== 动态输出列名 =====
连续红盘列名 = f'连续{连续红盘天数}日收盘大于开盘'
区间涨幅列名 = f'近{区间涨幅天数}日涨幅'
近N日涨停次数列名 = f'近{涨跌停过滤天数}日涨停次数'
近N日跌停次数列名 = f'近{涨跌停过滤天数}日跌停次数'
连续放量列名 = f'连续{连续红盘天数}日成交量逐日放大'
收盘新高列名 = f'近{新高周期}日收盘新高'
是否收盘新高列名 = f'是否近{新高周期}日收盘新高'
上一日是否收盘新高列名 = f'上一日是否近{新高周期}日收盘新高'
近3日成交额列名 = f'近{区间涨幅天数}日成交额'


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
    return set(代码序列.map(common.normalize_ts_code).tolist())


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
    代码条件, 代码参数 = common.stock_code_filter(股票代码列表, "sd.ts_code")
    日期占位符 = ", ".join(["%s"] * len(交易日列表))

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
            sd.volume AS vol,
            sd.turnover AS amount,
            sd.change_pct AS pct_chg,
            sb.market,
            sb.list_status
        FROM daily_quotes sd
        LEFT JOIN securities sb ON SUBSTRING_INDEX(sd.ts_code, '.', 1) = sb.symbol
        WHERE sd.trade_date IN ({日期占位符})
          AND {代码条件}
          AND sb.market = '主板'
          AND sb.list_status = 'L'
          AND sd.stock_name NOT REGEXP 'ST|退'
          AND sd.previous_close > 0
          AND sd.open_price IS NOT NULL
          AND sd.high_price IS NOT NULL
          AND sd.low_price IS NOT NULL
          AND sd.close_price IS NOT NULL
          AND sd.volume IS NOT NULL
          AND sd.turnover IS NOT NULL
          AND sd.change_pct IS NOT NULL
        ORDER BY sd.ts_code, sd.trade_date
    """
    return db.read_sql(查询语句, (*交易日列表, *代码参数))


def _计算指标(日线数据):
    日线数据 = 日线数据.copy()
    日线数据['ts_code'] = 日线数据['ts_code'].map(common.normalize_symbol)
    日线数据 = 日线数据.sort_values(['ts_code', 'trade_date'])
    分组 = 日线数据.groupby('ts_code', group_keys=False)

    for 均线周期 in 均线周期列表:
        日线数据[f'ma{均线周期}'] = 分组['close'].transform(
            lambda s, n=均线周期: s.rolling(n, min_periods=n).mean()
        )

    日线数据['红盘'] = 日线数据['close'] > 日线数据['open']
    日线数据[连续红盘列名] = 分组['红盘'].transform(
        lambda s: s.rolling(连续红盘天数, min_periods=连续红盘天数).sum()
    )
    日线数据[连续放量列名] = (
        (日线数据['vol'] > 分组['vol'].shift(1))
        & (分组['vol'].shift(1) > 分组['vol'].shift(2))
    )
    日线数据[收盘新高列名] = 分组['close'].transform(
        lambda s: s.rolling(新高周期, min_periods=新高周期).max()
    )
    日线数据[是否收盘新高列名] = 日线数据['close'] >= 日线数据[收盘新高列名]
    日线数据[上一日是否收盘新高列名] = 日线数据.groupby('ts_code')[是否收盘新高列名].shift(1).eq(True)
    日线数据[区间涨幅列名] = 分组['close'].transform(
        lambda s: (s / s.shift(区间涨幅天数) - 1) * 100
    )
    日线数据[近3日成交额列名] = 分组['amount'].transform(
        lambda s: s.rolling(区间涨幅天数, min_periods=区间涨幅天数).sum()
    )
    日线数据['是否涨停'] = 日线数据['pct_chg'] >= 涨停阈值
    日线数据['是否跌停'] = 日线数据['pct_chg'] <= 跌停阈值
    日线数据[近N日涨停次数列名] = 分组['是否涨停'].transform(
        lambda s: s.rolling(涨跌停过滤天数, min_periods=1).sum()
    )
    日线数据[近N日跌停次数列名] = 分组['是否跌停'].transform(
        lambda s: s.rolling(涨跌停过滤天数, min_periods=1).sum()
    )
    return 日线数据


def strategy(filtered_codes, target_date):
    """
    三连阳趋势均线多头选股策略。
    只做收盘后选股，不额外定义买入卖出逻辑。
    """
    target_date = int(target_date)
    logger.warning(f"【{策略名称}】开始筛选 {target_date} ...")
    logger.info(
        f"参数 | 连续红盘:{连续红盘天数}天 "
        f"连续放量:{连续红盘天数}天 "
        f"近{区间涨幅天数}日涨幅>{区间涨幅下限}% "
        f"收盘创近{新高周期}日新高且上一日不是新高 "
        f"成交额>{成交额下限} "
        f"近{涨跌停过滤天数}日无涨停/跌停 "
        f"均线: close>MA5>MA10>MA20>MA30 "
        f"买入开盘涨幅:{买入开盘涨幅下限}%~{买入开盘涨幅上限}% "
        f"买入开盘偏离信号MA5<={买入开盘偏离MA5上限}% "
        f"买入后首日开盘浮盈>{首日开盘浮盈减仓阈值}%卖出{首日开盘浮盈减仓比例:.0%} "
        f"价格偏离MA5>{减仓MA5乖离阈值}%减掉{MA5乖离减仓比例:.0%}仓位 "
        f"仓位:{最大仓位数}仓 单日最多买入:{单日最多买入数}只 "
        f"每日候选:{每日候选数量 if 每日候选数量 is not None else '全部'}"
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

    均线列名列表 = [f'ma{n}' for n in 均线周期列表]
    选中数据 = 当日数据[
        (当日数据[连续红盘列名] == 连续红盘天数)
        & 当日数据[连续放量列名]
        & (当日数据[区间涨幅列名] > 区间涨幅下限)
        & (当日数据['amount'] > 成交额下限)
        & (当日数据['close'] >= 当日数据[收盘新高列名])
        & (~当日数据[上一日是否收盘新高列名].fillna(False))
        & (当日数据[近N日涨停次数列名] == 0)
        & (当日数据[近N日跌停次数列名] == 0)
        & (当日数据['close'] > 当日数据['ma5'])
        & (当日数据['ma5'] > 当日数据['ma10'])
        & (当日数据['ma10'] > 当日数据['ma20'])
        & (当日数据['ma20'] > 当日数据['ma30'])
        & 当日数据[均线列名列表].notna().all(axis=1)
        & 当日数据[区间涨幅列名].notna()
        & 当日数据[近3日成交额列名].notna()
        & 当日数据[收盘新高列名].notna()
    ].copy()

    if 选中数据.empty:
        logger.warning(
            f"{target_date} 未筛选到符合连续{连续红盘天数}日红盘、"
            f"连续{连续红盘天数}日成交量逐日放大、"
            f"近{区间涨幅天数}日涨幅>{区间涨幅下限}%、"
            f"收盘创近{新高周期}日新高且上一日不是新高、"
            f"成交额>{成交额下限}、"
            f"近{涨跌停过滤天数}日无涨跌停、close>MA5>MA10>MA20>MA30 的股票"
        )
        return pd.DataFrame([])

    选中数据 = 选中数据.sort_values(
        [近3日成交额列名, 区间涨幅列名, 'pct_chg'],
        ascending=False,
        kind='mergesort',
    ).reset_index(drop=True)
    if 每日候选数量 is not None:
        选中数据 = 选中数据.head(int(每日候选数量)).reset_index(drop=True)
    选中数据['排序'] = 选中数据.index + 1

    logger.warning(f"{target_date} 【{策略名称}】最终选中 {len(选中数据)} 只股票")
    logger.warning(f"入选股票：{' '.join(选中数据['stock_name'].astype(str).tolist())}")
    for _, 行 in 选中数据.iterrows():
        logger.info(
            f"   → 候选 {行['stock_name']} {common.normalize_symbol(行['ts_code'])} | "
            f"排序:{int(行['排序'])} | {区间涨幅列名}:{行[区间涨幅列名]:.2f}% | "
            f"当日涨幅:{行['pct_chg']:.2f}% | 成交量:{行['vol']:.2f} | "
            f"成交额:{行['amount']:.2f} | {近3日成交额列名}:{行[近3日成交额列名]:.2f} | "
            f"close:{行['close']:.2f} | MA5:{行['ma5']:.2f} | MA10:{行['ma10']:.2f} | "
            f"MA20:{行['ma20']:.2f} | MA30:{行['ma30']:.2f} | "
            f"{收盘新高列名}:{行[收盘新高列名]:.2f} | "
            f"上一日新高:{bool(行[上一日是否收盘新高列名])} | "
            f"{近N日涨停次数列名}:{int(行[近N日涨停次数列名])} | "
            f"{近N日跌停次数列名}:{int(行[近N日跌停次数列名])}"
        )

    return 选中数据[[
        'ts_code', 'stock_name', 'trade_date',
        'open', 'high', 'low', 'close', 'pre_close',
        'vol', 'amount', 'pct_chg',
        'ma5', 'ma10', 'ma20', 'ma30',
        连续红盘列名, 连续放量列名, 区间涨幅列名, 近3日成交额列名,
        收盘新高列名, 是否收盘新高列名, 上一日是否收盘新高列名,
        近N日涨停次数列名, 近N日跌停次数列名,
        '排序',
    ]]


def _当前持仓数量():
    return sum(1 for 持仓 in account.holding_stocks.values() if 持仓.get('lots', 0) > 0)


def buy(name, code, price, buy_date, close_price, signal_date):
    code = common.normalize_symbol(code)
    if code in account.holding_stocks and account.holding_stocks[code].get('lots', 0) > 0:
        logger.error(f"{name} {code} 之前买入的仓位还没有卖完，不重复买入")
        return False
    if _当前持仓数量() >= 最大仓位数:
        logger.error(f"{name} {code} 当前持仓已达到 {最大仓位数} 仓，不买")
        return False

    最大买入金额 = (account.available_amount + account.market_value) / 最大仓位数
    if 最大买入金额 > account.available_amount:
        最大买入金额 = account.available_amount
    logger.info(
        f"可用金额：{account.available_amount} 目前市值：{account.market_value} "
        f"单仓最大买入金额：{最大买入金额}"
    )

    lots = account.计算最大可买手数(price=price, price_max=最大买入金额)
    if lots <= 0:
        logger.error(f"{name} {code} 最大可买手数为:{lots}，不买")
        return False

    buy_price = round(price * lots, 3)
    if buy_price > account.available_amount:
        logger.error(f"{name} {code} 买入失败，可用金额不足：{account.available_amount}")
        return False

    logger.warning(
        f"{name} {code} 股价：{price} 买入：{lots}股 买入金额：{buy_price} 尝试买入，"
        f"买入前 市值：{account.market_value} 可用金额：{account.available_amount}"
    )
    account.available_amount -= buy_price
    account.market_value += buy_price
    if account.min_available_amount >= account.available_amount:
        account.min_available_amount = account.available_amount
    logger.warning(
        f"{name} {code} 股价：{price} 买入：{lots}股 买入金额：{buy_price} 买入成功，"
        f"买入后 市值：{account.market_value} 可用金额：{account.available_amount}"
    )

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
        '信号日期': int(signal_date),
        '卖出原因': None,
        '是否已MA5乖离减仓': False,
        '是否已首日开盘浮盈减仓': False,
    }
    return True


def simulated_buy():
    selected_stocks = account.next_date_pre_selection_stocks['selected_stocks']
    target_date = account.next_date_pre_selection_stocks['target_date']
    if selected_stocks is None or target_date is None:
        logger.error("下一日预选买入池为空")
        return
    if selected_stocks.empty:
        logger.error("下一日预选买入池为空")
        account.next_date_pre_selection_stocks = {'selected_stocks': None, 'target_date': None}
        return

    target_date = int(target_date)
    buy_date = common.get_next_date(target_date)
    if buy_date is None:
        logger.warning(f"{target_date} 无下一交易日，不买")
        account.next_date_pre_selection_stocks = {'selected_stocks': None, 'target_date': None}
        return

    查询语句 = f"""
        SELECT ts_code, trade_date, stock_name, open_price AS open, high_price AS high, low_price AS low, close_price AS close, previous_close AS pre_close
        FROM daily_quotes
        WHERE ts_code IN {common.stock_code_literals(selected_stocks['ts_code'].tolist())}
          AND trade_date = {int(buy_date)}
    """
    买入日数据 = pd.read_sql(查询语句, db.engine)
    买入数量 = 0
    selected_stocks = selected_stocks.sort_values(
        [近3日成交额列名, 区间涨幅列名, 'pct_chg'],
        ascending=False,
        kind='mergesort',
    )

    for _, 候选 in selected_stocks.iterrows():
        if 买入数量 >= 单日最多买入数:
            break
        if _当前持仓数量() >= 最大仓位数:
            logger.warning(f"当前持仓已达到 {最大仓位数} 仓，停止买入")
            break

        ts_code = common.normalize_symbol(候选['ts_code'])
        stock_name = str(候选['stock_name'])
        if ts_code in account.holding_stocks and account.holding_stocks[ts_code].get('lots', 0) > 0:
            logger.error(f"{stock_name} {ts_code} 之前买入的仓位还没有卖完，跳过")
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
        if open_price == high_price == low_price == close_price:
            logger.error(f"{stock_name} {buy_date} 一字，不买")
            continue

        开盘涨幅 = (open_price / pre_close - 1) * 100
        if not (买入开盘涨幅下限 < 开盘涨幅 < 买入开盘涨幅上限):
            logger.error(
                f"{stock_name} {buy_date} 开盘涨幅 {开盘涨幅:.2f}% "
                f"不在 ({买入开盘涨幅下限}%, {买入开盘涨幅上限}%) 内，不买"
            )
            continue

        if 'ma5' not in 候选 or pd.isna(候选['ma5']):
            logger.error(f"{stock_name} {target_date} 信号日MA5为空，不买")
            continue
        信号MA5 = float(候选['ma5'])
        if 信号MA5 <= 0:
            logger.error(f"{stock_name} {target_date} 信号日MA5异常：{信号MA5}，不买")
            continue
        开盘偏离MA5 = abs(open_price / 信号MA5 - 1) * 100
        if 开盘偏离MA5 > 买入开盘偏离MA5上限:
            logger.error(
                f"{stock_name} {buy_date} 开盘价 {open_price:.2f} 偏离信号日MA5 {信号MA5:.2f} "
                f"{开盘偏离MA5:.2f}% > {买入开盘偏离MA5上限}%，不买"
            )
            continue

        buy_status = buy(
            stock_name,
            ts_code,
            price=open_price,
            buy_date=int(buy_date),
            close_price=close_price,
            signal_date=target_date,
        )
        if buy_status:
            买入数量 += 1
            当日浮盈 = (close_price / open_price - 1) * 100
            logger.warning(
                f"{stock_name} {buy_date} 开盘涨幅 {开盘涨幅:.2f}%，"
                f"开盘偏离信号MA5 {开盘偏离MA5:.2f}%，"
                f"按开盘价 {open_price:.2f} 买入，当天收盘浮盈：{当日浮盈:.2f}%"
            )
        else:
            logger.error(f"{stock_name} {buy_date} 买入失败")

    account.next_date_pre_selection_stocks = {'selected_stocks': None, 'target_date': None}


def simulated_sell(now_date=None, 卖出时点='收盘'):
    logger.warning(f"检查持仓是否{卖出时点}跌破MA5 开始")
    持仓代码列表 = [common.normalize_symbol(code) for code, 持仓 in account.holding_stocks.items() if 持仓.get('lots', 0) > 0]
    if not 持仓代码列表:
        logger.warning(f"检查持仓是否{卖出时点}跌破MA5 完成")
        return

    try:
        交易日列表 = _最近交易日(now_date, 30)
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
        if 持仓信息.get('lots', 0) <= 0:
            continue
        if 持仓信息['买入日期'] == int(now_date):
            logger.error(f"{ts_code} {持仓信息['name']} 买入当天不卖")
            continue

        个股当日数据 = 当日数据[当日数据['ts_code'] == ts_code]
        if 个股当日数据.empty:
            logger.error(f"{ts_code} {持仓信息['name']} {now_date} 当日数据为空")
            continue
        个股当日 = 个股当日数据.iloc[0]

        if 卖出时点 == '开盘':
            个股历史数据 = 日线数据[
                (日线数据['ts_code'] == ts_code)
                & (日线数据['trade_date'] < int(now_date))
            ].sort_values('trade_date')
            if 个股历史数据.empty:
                logger.error(f"{ts_code} {持仓信息['name']} {now_date} 无上一交易日数据，不卖")
                continue
            上一交易日 = 个股历史数据.iloc[-1]
            if pd.isna(上一交易日['ma5']):
                logger.error(f"{ts_code} {持仓信息['name']} {上一交易日['trade_date']} MA5为空，不卖")
                continue
            price = float(个股当日['open'])
            ma5 = float(上一交易日['ma5'])
            reason = f"开盘跌破上一交易日MA5: open={price:.2f}, 上一交易日MA5={ma5:.2f}"
        else:
            if pd.isna(个股当日['ma5']):
                logger.error(f"{ts_code} {持仓信息['name']} {now_date} MA5为空，不卖")
                continue
            price = float(个股当日['close'])
            ma5 = float(个股当日['ma5'])
            reason = f"收盘跌破MA5: close={price:.2f}, MA5={ma5:.2f}"

        买入后首个交易日 = common.get_next_date(int(持仓信息['买入日期']))
        if 买入后首个交易日 is not None:
            买入后首个交易日 = int(买入后首个交易日)
        首日开盘浮盈率 = (price / float(持仓信息['买入价']) - 1) * 100
        if (
                卖出时点 == '开盘'
                and 买入后首个交易日 == int(now_date)
                and 首日开盘浮盈率 > 首日开盘浮盈减仓阈值
                and not 持仓信息.get('是否已首日开盘浮盈减仓', False)
        ):
            减仓股数 = int(int(持仓信息['lots']) * 首日开盘浮盈减仓比例 // 100) * 100
            if 减仓股数 <= 0:
                logger.error(
                    f"{ts_code} {持仓信息['name']} 买入后首日开盘浮盈 {首日开盘浮盈率:.2f}% "
                    f"超过 {首日开盘浮盈减仓阈值}% 但持仓不足，无法减仓"
                )
            else:
                持仓信息['卖出原因'] = (
                    f"买入后首日开盘浮盈超过{首日开盘浮盈减仓阈值}%卖出{首日开盘浮盈减仓比例:.0%}: "
                    f"open={price:.2f}, 买入价={持仓信息['买入价']:.2f}, 浮盈={首日开盘浮盈率:.2f}%"
                )
                logger.warning(
                    f"{ts_code} {持仓信息['name']} 买入后首日开盘浮盈 {首日开盘浮盈率:.2f}% "
                    f"超过 {首日开盘浮盈减仓阈值}% 卖出{首日开盘浮盈减仓比例:.0%} | "
                    f"open:{price:.2f} 买入价:{持仓信息['买入价']:.2f} 卖出股数:{减仓股数}"
                )
                account.sell(持仓信息['name'], ts_code, price, 减仓股数, int(now_date))
                if ts_code in account.holding_stocks:
                    account.holding_stocks[ts_code]['是否已首日开盘浮盈减仓'] = True
                continue

        ma5乖离率 = (price / ma5 - 1) * 100
        if ma5乖离率 > 减仓MA5乖离阈值 and not 持仓信息.get('是否已MA5乖离减仓', False):
            减仓股数 = int(int(持仓信息['lots']) * MA5乖离减仓比例 // 100) * 100
            if 减仓股数 <= 0:
                logger.error(
                    f"{ts_code} {持仓信息['name']} {卖出时点}偏离MA5 {ma5乖离率:.2f}% "
                    f"超过 {减仓MA5乖离阈值}% 但持仓不足，无法减仓"
                )
            else:
                持仓信息['卖出原因'] = (
                    f"{卖出时点}偏离MA5超过{减仓MA5乖离阈值}%减掉{MA5乖离减仓比例:.0%}仓位: "
                    f"price={price:.2f}, MA5={ma5:.2f}, 乖离={ma5乖离率:.2f}%"
                )
                logger.warning(
                    f"{ts_code} {持仓信息['name']} {卖出时点}偏离MA5 {ma5乖离率:.2f}% "
                    f"超过 {减仓MA5乖离阈值}% 减掉{MA5乖离减仓比例:.0%}仓位 | "
                    f"price:{price:.2f} MA5:{ma5:.2f} 卖出股数:{减仓股数}"
                )
                account.sell(持仓信息['name'], ts_code, price, 减仓股数, int(now_date))
                if ts_code in account.holding_stocks:
                    account.holding_stocks[ts_code]['是否已MA5乖离减仓'] = True
                continue

        if price < ma5:
            持仓信息['卖出原因'] = reason
            logger.error(
                f"{ts_code} {持仓信息['name']} {卖出时点}跌破MA5 卖出 | "
                f"price:{price:.2f} MA5:{ma5:.2f} 盈亏比:{持仓信息['盈亏比']:.2f}%"
            )
            account.sell(持仓信息['name'], ts_code, price, 持仓信息['lots'], int(now_date))
            continue

    logger.warning(f"检查持仓是否{卖出时点}跌破MA5 完成")


def process_daily(target_date=None, filtered_codes=None):
    account.sync_open_market_before(now_date=target_date)
    simulated_sell(now_date=target_date, 卖出时点='开盘')
    simulated_buy()
    account.sync_close_market(now_date=target_date)
    simulated_sell(now_date=target_date, 卖出时点='收盘')
    account.sync_close_market(now_date=target_date)

    选中股票 = strategy(filtered_codes, target_date)
    if 选中股票.empty:
        logger.error(f"{target_date} 未筛选到符合策略的股票")
        return
    account.add_next_date_stocks(选中股票, target_date)


def main(start_date=开始日期, end_date=结束日期):
    文件名 = __file__.split(".py")[0].split("\\")[-1].split("/")[-1]
    common.process_for_strategy(start_date, end_date, process_daily, 文件名)


if __name__ == "__main__":
    main(start_date=开始日期, end_date=结束日期)
