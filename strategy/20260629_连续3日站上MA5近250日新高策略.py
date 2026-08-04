import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from utils import account, common, db


策略名称 = '20260629_连续3日站上MA5近250日新高策略'
开始日期 = 20260701
结束日期 = int(datetime.now().strftime('%Y%m%d'))

# ===== 可调参数 =====
均线天数 = 5
乖离均线天数 = 10
连续站上均线天数 = 3
新高周期 = 250
回看交易日数 = 新高周期 + max(均线天数, 乖离均线天数) + 连续站上均线天数 + 20
成交额下限 = 2000000
收盘距离均线上限 = 15
买入开盘距离均线上限 = 5
减半仓盈利阈值 = 20
要求上一日不是新高 = True
每日候选数量 = 3
最大仓位数 = 5
单日最多买入数 = 2

# ===== 动态输出列名 =====
均线列名 = f'ma{均线天数}'
乖离均线列名 = f'ma{乖离均线天数}'
收盘距离均线列名 = f'收盘距离MA{乖离均线天数}'
连续站上均线列名 = f'连续{连续站上均线天数}日站上MA{均线天数}'
收盘新高列名 = f'近{新高周期}日收盘新高'
最高价新高列名 = f'近{新高周期}日最高价新高'
区间涨幅列名 = f'近{新高周期}日涨幅'
是否新高列名 = f'是否近{新高周期}日新高'
上一日是否新高列名 = f'上一日是否近{新高周期}日新高'



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
            FROM stock_daily
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
    交易日元组 = str(tuple([int(i) for i in 交易日列表])).replace(',)', ')')
    股票代码列表 = sorted(_提取整数代码(filtered_codes))
    代码过滤条件 = ''
    if 股票代码列表:
        代码过滤条件 = f"AND sd.ts_code IN {str(tuple(股票代码列表)).replace(',)', ')')}"

    查询语句 = f"""
        SELECT
            sd.ts_code,
            sd.stock_name,
            sd.trade_date,
            sd.open,
            sd.high,
            sd.low,
            sd.close,
            sd.pre_close,
            sd.amount,
            sd.pct_chg,
            sb.market,
            sb.list_status
        FROM stock_daily sd
        LEFT JOIN stock_basic sb ON sd.ts_code = sb.symbol
        WHERE sd.trade_date IN {交易日元组}
          {代码过滤条件}
          AND sb.market = '主板'
          AND sb.list_status = 'L'
          AND sd.stock_name NOT REGEXP 'ST|退'
          AND sd.pre_close > 0
          AND sd.open IS NOT NULL
          AND sd.high IS NOT NULL
          AND sd.low IS NOT NULL
          AND sd.close IS NOT NULL
          AND sd.amount IS NOT NULL
          AND sd.pct_chg IS NOT NULL
        ORDER BY sd.ts_code, sd.trade_date
    """
    return pd.read_sql(查询语句, db.engine)


def _计算指标(日线数据):
    日线数据 = 日线数据.copy()
    日线数据['ts_code'] = 日线数据['ts_code'].astype(int)
    日线数据 = 日线数据.sort_values(['ts_code', 'trade_date'])
    分组 = 日线数据.groupby('ts_code', group_keys=False)

    日线数据[均线列名] = 分组['close'].transform(
        lambda s: s.rolling(均线天数, min_periods=均线天数).mean()
    )
    日线数据[乖离均线列名] = 分组['close'].transform(
        lambda s: s.rolling(乖离均线天数, min_periods=乖离均线天数).mean()
    )
    日线数据[收盘距离均线列名] = (
        (日线数据['close'] / 日线数据[乖离均线列名] - 1).abs() * 100
    )
    日线数据[收盘新高列名] = 分组['close'].transform(
        lambda s: s.rolling(新高周期, min_periods=新高周期).max()
    )
    日线数据[最高价新高列名] = 分组['high'].transform(
        lambda s: s.rolling(新高周期, min_periods=新高周期).max()
    )
    日线数据['above_ma'] = 日线数据['close'] > 日线数据[均线列名]
    日线数据[连续站上均线列名] = 分组['above_ma'].transform(
        lambda s: s.rolling(连续站上均线天数, min_periods=连续站上均线天数).sum()
    )
    日线数据[区间涨幅列名] = 分组['close'].transform(
        lambda s: (s / s.shift(新高周期) - 1) * 100
    )
    日线数据[是否新高列名] = 日线数据['close'] >= 日线数据[收盘新高列名]
    日线数据[上一日是否新高列名] = (
        日线数据.groupby('ts_code')[是否新高列名].shift(1).eq(True)
    )
    return 日线数据


def strategy(filtered_codes, target_date):
    """
    连续站上均线并创N日新高的选股策略。
    可调参数集中在文件顶部。
    """
    target_date = int(target_date)
    logger.warning(f"【{策略名称}】开始筛选 {target_date} ...")
    logger.info(
        f"参数 | MA:{均线天数} 连续站上:{连续站上均线天数}天 "
        f"新高周期:{新高周期}天 成交额下限:{成交额下限} "
        f"收盘距离MA{乖离均线天数}<={收盘距离均线上限}% "
        f"次日开盘距离MA{乖离均线天数}<{买入开盘距离均线上限}% "
        f"盈利>{减半仓盈利阈值}%减半仓 "
        f"读取交易日:{回看交易日数} 每日候选:{每日候选数量}只"
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

    上一日不是新高 = ~当日数据[上一日是否新高列名].fillna(False)
    if not 要求上一日不是新高:
        上一日不是新高 = pd.Series(True, index=当日数据.index)

    选中数据 = 当日数据[
        (当日数据['amount'] >= 成交额下限)
        & (当日数据[连续站上均线列名] == 连续站上均线天数)
        & (当日数据['close'] >= 当日数据[收盘新高列名])
        & (当日数据['high'] >= 当日数据[最高价新高列名])
        & (当日数据[收盘距离均线列名] <= 收盘距离均线上限)
        & 上一日不是新高
        & 当日数据[均线列名].notna()
        & 当日数据[乖离均线列名].notna()
        & 当日数据[收盘距离均线列名].notna()
        & 当日数据[收盘新高列名].notna()
        & 当日数据[最高价新高列名].notna()
    ].copy()

    if 选中数据.empty:
        logger.warning(
            f"{target_date} 未筛选到符合连续{连续站上均线天数}日"
            f"站上MA{均线天数}、近{新高周期}日收盘和最高价新高、"
            f"成交额>={成交额下限}、收盘距离MA{乖离均线天数}<={收盘距离均线上限}%的股票"
        )
        return pd.DataFrame([])

    选中数据 = 选中数据.sort_values(
        ['amount', 'pct_chg'],
        ascending=False,
        kind='mergesort',
    ).head(每日候选数量).reset_index(drop=True)
    选中数据['排序'] = 选中数据.index + 1

    logger.warning(f"{target_date} 【{策略名称}】最终选中 {len(选中数据)} 只股票")
    logger.warning(f"入选股票：{' '.join(选中数据['stock_name'].astype(str).tolist())}")
    for _, 行 in 选中数据.iterrows():
        logger.info(
            f"   → 候选 {行['stock_name']} {int(行['ts_code'])} | "
            f"排序:{int(行['排序'])} | 成交额:{行['amount']:.2f} | "
            f"涨幅:{行['pct_chg']:.2f}% | close:{行['close']:.2f} | "
            f"{均线列名.upper()}:{行[均线列名]:.2f} | "
            f"{乖离均线列名.upper()}:{行[乖离均线列名]:.2f} | "
            f"{收盘距离均线列名}:{行[收盘距离均线列名]:.2f}% | "
            f"{收盘新高列名}:{行[收盘新高列名]:.2f} | "
            f"{最高价新高列名}:{行[最高价新高列名]:.2f} | "
            f"上一日新高:{bool(行[上一日是否新高列名])} | {区间涨幅列名}:{行[区间涨幅列名]:.2f}%"
        )

    return 选中数据[[
        'ts_code', 'stock_name', 'trade_date',
        'open', 'high', 'low', 'close', 'pre_close',
        'amount', 'pct_chg',
        均线列名, 乖离均线列名, 收盘距离均线列名,
        连续站上均线列名, 收盘新高列名, 最高价新高列名,
        是否新高列名, 上一日是否新高列名, 区间涨幅列名,
        '排序',
    ]]


def _当前持仓数量():
    return sum(1 for 持仓 in account.holding_stocks.values() if 持仓.get('lots', 0) > 0)


def buy(name, code, price, buy_date, close_price, signal_date, signal_ma10):
    code = int(code)
    if code in account.holding_stocks:
        logger.error(f"{name} {code} 已经买过，本策略不允许重复买，不买了。")
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
        f'信号MA{乖离均线天数}': signal_ma10,
        '卖出原因': None,
        '是否已减半仓': False,
    }
    return True


def simulated_buy():
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

    查询语句 = f"""
        SELECT ts_code, trade_date, close, stock_name, open, pre_close, high, low
        FROM stock_daily
        WHERE ts_code IN {str(tuple([int(i) for i in selected_stocks['ts_code'].tolist()])).replace(',)', ')')}
          AND trade_date = {int(buy_date)}
    """
    买入日数据 = pd.read_sql(查询语句, db.engine)
    买入数量 = 0
    selected_stocks = selected_stocks.sort_values('amount', ascending=False, kind='mergesort')

    for _, 候选 in selected_stocks.iterrows():
        if 买入数量 >= 单日最多买入数:
            break
        if _当前持仓数量() >= 最大仓位数:
            logger.warning(f"当前持仓已达到 {最大仓位数} 仓，停止买入")
            break

        ts_code = int(候选['ts_code'])
        stock_name = str(候选['stock_name'])
        if ts_code in account.holding_stocks:
            logger.error(f"{stock_name} {ts_code} 已经买过，本策略不允许重复买，跳过")
            continue

        if 乖离均线列名 not in 候选 or pd.isna(候选[乖离均线列名]):
            logger.error(f"{stock_name} {target_date} 信号日MA{乖离均线天数}为空，不买")
            continue
        信号均线 = float(候选[乖离均线列名])
        if 信号均线 <= 0:
            logger.error(f"{stock_name} {target_date} 信号日MA{乖离均线天数}异常：{信号均线}，不买")
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
        if open_price == high_price == low_price == close_price:
            logger.error(f"{stock_name} {buy_date} 一字，不买")
            continue

        开盘距离均线 = abs(open_price / 信号均线 - 1) * 100
        if 开盘距离均线 >= 买入开盘距离均线上限:
            logger.error(
                f"{stock_name} {buy_date} 开盘价 {open_price:.2f} 距离信号MA{乖离均线天数} "
                f"{信号均线:.2f} 为 {开盘距离均线:.2f}%，不小于 {买入开盘距离均线上限}%，不买"
            )
            continue

        buy_date_yield_rate = (close_price - open_price) / open_price * 100
        buy_status = buy(
            stock_name,
            ts_code,
            price=open_price,
            buy_date=int(buy_date),
            close_price=close_price,
            signal_date=target_date,
            signal_ma10=信号均线,
        )
        if buy_status:
            买入数量 += 1
            logger.warning(
                f"{stock_name} {buy_date} 开盘价距离信号MA{乖离均线天数} {开盘距离均线:.2f}%，"
                f"以开盘价 {open_price:.2f} 买入，当天收盘收益率：{buy_date_yield_rate:.2f}%"
            )
        else:
            logger.error(f"{stock_name} {buy_date} 买入失败")

    account.next_date_pre_selection_stocks = {
        'selected_stocks': None,
        'target_date': None,
    }


def simulated_sell(now_date=None):
    logger.warning(f"检查持仓是否收盘跌破MA{乖离均线天数} 开始")
    持仓代码列表 = [int(code) for code, 持仓 in account.holding_stocks.items() if 持仓.get('lots', 0) > 0]
    if not 持仓代码列表:
        logger.warning(f"检查持仓是否收盘跌破MA{乖离均线天数} 完成")
        return

    try:
        交易日列表 = _最近交易日(now_date, 乖离均线天数 + 5)
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
        个股当日 = 个股当日数据.iloc[0]
        if pd.isna(个股当日[乖离均线列名]):
            logger.error(f"{ts_code} {持仓信息['name']} {now_date} MA{乖离均线天数}为空，不卖")
            continue

        close_price = float(个股当日['close'])
        当前均线 = float(个股当日[乖离均线列名])
        if close_price < 当前均线:
            持仓信息['卖出原因'] = (
                f"收盘跌破MA{乖离均线天数}: close={close_price:.2f}, "
                f"MA{乖离均线天数}={当前均线:.2f}"
            )
            logger.error(
                f"{ts_code} {持仓信息['name']} 收盘跌破MA{乖离均线天数} 卖出 | "
                f"close:{close_price:.2f} MA{乖离均线天数}:{当前均线:.2f} "
                f"盈亏比:{持仓信息['盈亏比']:.2f}%"
            )
            account.sell(持仓信息['name'], ts_code, close_price, 持仓信息['lots'], int(now_date))
            continue

        当前盈亏比 = float(持仓信息.get('盈亏比', 0))
        是否已减半仓 = 持仓信息.get('是否已减半仓', False)
        if 当前盈亏比 > 减半仓盈利阈值 and not 是否已减半仓:
            减仓股数 = (int(持仓信息['lots']) // 200) * 100
            if 减仓股数 <= 0:
                logger.error(
                    f"{ts_code} {持仓信息['name']} 盈利超过{减半仓盈利阈值}%但持仓不足200股，无法减半仓"
                )
                continue

            持仓信息['卖出原因'] = (
                f"盈利超过{减半仓盈利阈值}%减半仓: 盈亏比={当前盈亏比:.2f}%"
            )
            logger.warning(
                f"{ts_code} {持仓信息['name']} 盈利超过{减半仓盈利阈值}% 减半仓 | "
                f"close:{close_price:.2f} MA{乖离均线天数}:{当前均线:.2f} "
                f"盈亏比:{当前盈亏比:.2f}% 卖出股数:{减仓股数}"
            )
            account.sell(持仓信息['name'], ts_code, close_price, 减仓股数, int(now_date))
            account.holding_stocks[ts_code]['是否已减半仓'] = True
            continue

    logger.warning(f"检查持仓是否收盘跌破MA{乖离均线天数} 完成")


def process_daily(target_date=None, filtered_codes=None):
    account.sync_open_market_before(now_date=target_date)
    simulated_buy()
    account.sync_close_market(now_date=target_date)
    simulated_sell(now_date=target_date)
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
