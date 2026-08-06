import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from loguru import logger

项目根目录 = Path(__file__).resolve().parents[1]
sys.path.append(str(项目根目录))

from utils import account, common, db


策略名称 = '20260629_强趋势龙头加速增强策略'
开始日期 = 20260720
结束日期 = int(datetime.now().strftime('%Y%m%d'))

选股最少涨幅 = 5.0
选股最大涨幅 = 9.3
近5日最少涨幅 = 20.0
成交额放大倍数 = 1.5
成交额下限 = 500000
市场大涨家数阈值 = 35
近5日涨停次数上限 = 2
候选返回数量 = 8

买入最低开盘涨幅 = -3.0
买入最高开盘涨幅 = 9.2
单票仓位数 = 1
止盈阈值 = 12.0
最大回撤阈值 = -5.0
最大持股天数 = 2


def _提取整数股票代码集合(codes):
    if codes is None:
        return set()
    if isinstance(codes, pd.DataFrame):
        if 'ts_code' in codes.columns:
            codes = codes['ts_code']
        elif 'symbol' in codes.columns:
            codes = codes['symbol']
        else:
            return set()
    codes_series = pd.Series(list(codes)).astype(str).str.extract(r'(\d+)')[0].dropna()
    if codes_series.empty:
        return set()
    return set(codes_series.map(common.normalize_symbol).tolist())


def _最近交易日列表(end_date, days):
    rows = db.mysql_localhost(
        sql=f"""
            SELECT DISTINCT trade_date
            FROM daily_quotes
            WHERE trade_date <= {int(end_date)}
            ORDER BY trade_date DESC
            LIMIT {int(days)}
        """,
        fetch=True,
    )
    trade_dates = sorted([int(row['trade_date']) for row in rows])
    if len(trade_dates) < days:
        raise ValueError(f'交易日不足 {days} 天，当前只有 {len(trade_dates)} 天')
    return trade_dates


def _读取日线数据(filtered_codes, trade_dates):
    trade_date_tuple = str(tuple([common.normalize_ts_code(i) for i in trade_dates])).replace(',)', ')')
    codes = sorted(_提取整数股票代码集合(filtered_codes))
    code_filter = ''
    if codes:
        code_filter = f"AND sd.ts_code IN {common.stock_code_literals(codes)}"

    query = f"""
        SELECT
            sd.ts_code,
            sd.stock_name,
            sd.trade_date,
            sd.open_price AS open,
            sd.high_price AS high,
            sd.low_price AS low,
            sd.close_price AS close,
            sd.previous_close AS pre_close,
            sd.turnover AS amount,
            sd.change_pct AS pct_chg,
            sb.market,
            sb.list_status
        FROM daily_quotes sd
        LEFT JOIN securities sb ON SUBSTRING_INDEX(sd.ts_code, '.', 1) = sb.symbol
        WHERE sd.trade_date IN {trade_date_tuple}
          {code_filter}
          AND sb.market = '主板'
          AND sb.list_status = 'L'
          AND sd.stock_name NOT REGEXP 'ST|退'
          AND sd.previous_close > 0
          AND sd.turnover IS NOT NULL
          AND sd.change_pct IS NOT NULL
          AND sd.open_price IS NOT NULL
          AND sd.high_price IS NOT NULL
          AND sd.low_price IS NOT NULL
          AND sd.close_price IS NOT NULL
        ORDER BY sd.ts_code, sd.trade_date
    """
    return pd.read_sql(query, db.engine)


def _计算指标(日线数据):
    日线数据 = 日线数据.copy()
    日线数据['ts_code'] = 日线数据['ts_code'].map(common.normalize_symbol)
    日线数据 = 日线数据.sort_values(['ts_code', 'trade_date'])
    group = 日线数据.groupby('ts_code', group_keys=False)

    日线数据['ma5'] = group['close'].transform(lambda s: s.rolling(5, min_periods=5).mean())
    日线数据['ma10'] = group['close'].transform(lambda s: s.rolling(10, min_periods=10).mean())
    日线数据['ma20'] = group['close'].transform(lambda s: s.rolling(20, min_periods=20).mean())
    日线数据['amt20'] = group['amount'].transform(lambda s: s.rolling(20, min_periods=20).mean())
    日线数据['high20_prev'] = group['high'].transform(lambda s: s.shift(1).rolling(20, min_periods=20).max())
    日线数据['近5日涨幅'] = group['close'].transform(lambda s: (s / s.shift(5) - 1) * 100)
    日线数据['近20日涨幅'] = group['close'].transform(lambda s: (s / s.shift(20) - 1) * 100)
    日线数据['是否涨停'] = (日线数据['pct_chg'] >= 9.5) & (日线数据['close'] == 日线数据['high'])
    日线数据['近5日涨停次数'] = group['是否涨停'].transform(lambda s: s.shift(1).rolling(5, min_periods=1).sum())

    振幅 = 日线数据['high'] - 日线数据['low']
    日线数据['收盘位置'] = ((日线数据['close'] - 日线数据['low']) / 振幅).where(振幅 != 0, 0.5)
    日线数据['上影线'] = (日线数据['high'] - 日线数据['close']) / 日线数据['pre_close'] * 100
    日线数据['实体强度'] = (日线数据['close'] - 日线数据['open']) / 日线数据['pre_close'] * 100
    日线数据['成交额倍数'] = 日线数据['amount'] / 日线数据['amt20']

    市场热度 = 日线数据.groupby('trade_date').agg(
        市场大涨家数=('pct_chg', lambda s: int((s >= 5).sum())),
        市场大跌家数=('pct_chg', lambda s: int((s <= -5).sum())),
        市场涨停家数=('是否涨停', 'sum'),
        市场上涨比例=('pct_chg', lambda s: float((s > 0).mean())),
        市场中位涨幅=('pct_chg', 'median'),
    ).reset_index()
    日线数据 = 日线数据.merge(市场热度, on='trade_date', how='left')
    return 日线数据


def strategy(filtered_codes, target_date):
    """
    强趋势龙头加速增强策略：
    - 在 20260619 强趋势突破基础上增强，而不是直接按近5日涨幅排序。
    - 必须是主板、非ST、非退市。
    - 信号日 5%-9.3% 大阳，近5日涨幅>=20%，close > MA5 > MA10 > MA20。
    - 突破前20日高点，成交额大于20日均额1.5倍，且成交额>5亿。
    - 当日市场大涨家数>=35，说明有足够赚钱效应再开仓。
    - 综合强度、放量质量、收盘位置、上影风险打分，返回前排候选。
    - 次日买入时按分数顺位检查开盘条件，只买第一只真正符合条件的票。
    """
    target_date = int(target_date)
    logger.warning(f"【{策略名称}】开始筛选 {target_date} ...")

    try:
        trade_dates = _最近交易日列表(target_date, 80)
    except ValueError as exc:
        logger.warning(f"{target_date} 数据不足：{exc}")
        return pd.DataFrame([])

    日线数据 = _读取日线数据(filtered_codes, trade_dates)
    if 日线数据.empty:
        logger.warning(f"{target_date} 无足够日线数据")
        return pd.DataFrame([])

    日线数据 = _计算指标(日线数据)
    当日数据 = 日线数据[日线数据['trade_date'] == target_date].copy()
    if 当日数据.empty:
        logger.warning(f"{target_date} 当日日线为空")
        return pd.DataFrame([])

    selected_df = 当日数据[
        (当日数据['pct_chg'] >= 选股最少涨幅)
        & (当日数据['pct_chg'] <= 选股最大涨幅)
        & (当日数据['近5日涨幅'] >= 近5日最少涨幅)
        & (当日数据['close'] > 当日数据['ma5'])
        & (当日数据['ma5'] > 当日数据['ma10'])
        & (当日数据['ma10'] > 当日数据['ma20'])
        & (当日数据['close'] >= 当日数据['high20_prev'])
        & (当日数据['amount'] > 当日数据['amt20'] * 成交额放大倍数)
        & (当日数据['amount'] > 成交额下限)
        & (当日数据['近5日涨停次数'] <= 近5日涨停次数上限)
        & (当日数据['市场大涨家数'] >= 市场大涨家数阈值)
        & (~当日数据['是否涨停'])
    ].copy()

    if selected_df.empty:
        logger.warning(
            f"{target_date} 无符合“强趋势加速 + 市场热度 + 放量突破”的股票，"
            f"当日市场大涨家数:{int(当日数据['市场大涨家数'].max()) if '市场大涨家数' in 当日数据 else 0}"
        )
        return pd.DataFrame([])

    selected_df['策略分'] = (
        selected_df['近5日涨幅'].clip(0, 80) * 0.8
        + selected_df['pct_chg'].clip(0, 10) * 1.2
        + selected_df['成交额倍数'].clip(0, 8) * 5
        + selected_df['收盘位置'].fillna(0.5) * 5
        - selected_df['上影线'].clip(0, 8) * 2
    )

    selected_df = selected_df.sort_values(
        ['策略分', 'amount', '近5日涨幅'],
        ascending=False,
        kind='mergesort',
    ).head(候选返回数量).reset_index(drop=True)
    selected_df['排序'] = selected_df.index + 1

    logger.warning(f"{target_date} 【{策略名称}】最终选中 {len(selected_df)} 只股票")
    logger.warning(f"入选股票：{' '.join(selected_df['stock_name'].astype(str).tolist())}")
    for _, row in selected_df.iterrows():
        logger.info(
            f"   → 候选 {row['stock_name']} {common.normalize_symbol(row['ts_code'])} | "
            f"排序:{int(row['排序'])} | 涨幅:{row['pct_chg']:.2f}% | 近5日:{row['近5日涨幅']:.2f}% | "
            f"成交额:{row['amount']:.2f} | 成交额倍数:{row['成交额倍数']:.2f} | "
            f"收盘位置:{row['收盘位置']:.2f} | 上影线:{row['上影线']:.2f}% | "
            f"市场大涨家数:{int(row['市场大涨家数'])} | 策略分:{row['策略分']:.2f}"
        )

    return selected_df[[
        'ts_code', 'stock_name', 'trade_date',
        'open', 'high', 'low', 'close', 'pre_close',
        'amount', 'pct_chg',
        'ma5', 'ma10', 'ma20', 'amt20', 'high20_prev',
        '近5日涨幅', '近20日涨幅', '成交额倍数',
        '收盘位置', '上影线', '实体强度',
        '市场大涨家数', '市场大跌家数', '市场涨停家数', '市场上涨比例', '市场中位涨幅',
        '策略分', '排序',
    ]]


def buy(name, code, price, buy_date, close_price):
    code = common.normalize_symbol(code)
    if code in account.holding_stocks and account.holding_stocks[code]['lots'] > 0:
        logger.error(f"{name} {code} 已经持仓，不买了。")
        return False

    price_max = (account.available_amount + account.market_value) / 单票仓位数
    if price_max > account.available_amount:
        price_max = account.available_amount
    logger.info(f"可用金额：{account.available_amount} 目前市值：{account.market_value} 最大买入金额：{price_max}")
    lots = account.计算最大可买手数(price=price, price_max=price_max)
    if lots == 0:
        logger.error(f"{name} {code} 最大可买手数为:{lots}，不买了。")
        return False

    buy_price = round(price * lots, 3)
    logger.warning(f"{name} {code} 股价：{price} 买入：{lots}股 买入金额：{buy_price} 尝试买入，"
                   f"买入前 市值：{account.market_value} 可用金额：{account.available_amount} ")
    if buy_price > account.available_amount:
        logger.error(f"买入失败，可用金额不足：{account.available_amount}")
        return False

    account.available_amount = account.available_amount - buy_price
    account.market_value += buy_price
    if account.min_available_amount >= account.available_amount:
        account.min_available_amount = account.available_amount
    logger.warning(f"{name} {code} 股价：{price} 买入：{lots}股 买入金额：{buy_price} 买入成功，"
                   f"买入后 市值：{account.market_value} 可用金额：{account.available_amount}")

    account.holding_stocks[code] = {
        'name': name,
        'code': code,
        'lots': lots,
        'market_value': buy_price,
        '持股天数': 1,
        '成本价': buy_price,
        '盈亏比': 0,
        '盈亏': 0,
        '买入日期': buy_date,
        '卖出日期': None,
        '持仓最高市值': buy_price,
        '持仓最高回撤': 0,
        '是否发生除权': "否",
        'close_price': close_price,
        '买入价': price,
        '持仓最高价': price,
        '卖出原因': None,
    }
    return True


def simulated_buy():
    selected_stocks = account.next_date_pre_selection_stocks['selected_stocks']
    target_date = account.next_date_pre_selection_stocks['target_date']
    if selected_stocks is None or target_date is None:
        logger.error("下一日预选买入池 为空")
        return

    range_date = (datetime.strptime(str(target_date), "%Y%m%d") + timedelta(days=15)).strftime('%Y%m%d')
    query = f"""
        SELECT ts_code, trade_date, close_price AS close, stock_name, open_price AS open, previous_close AS pre_close, high_price AS high, low_price AS low
        FROM daily_quotes
        WHERE ts_code IN {common.stock_code_literals(selected_stocks['ts_code'].tolist())}
          AND trade_date >= {int(target_date)}
          AND trade_date <= {range_date}
        ORDER BY trade_date
    """
    range_data = pd.read_sql(query, db.engine)
    after_purchase_date_list = sorted(list(set(range_data['trade_date'].tolist())))
    if len(after_purchase_date_list) <= 1:
        logger.warning(f"{target_date} 下一交易日 入选后可买入的交易日期为空")
        account.next_date_pre_selection_stocks = {'selected_stocks': None, 'target_date': None}
        return

    buy_date = common.get_next_date(target_date)
    selected_stocks = selected_stocks.sort_values('策略分', ascending=False, kind='mergesort')

    for row in selected_stocks.itertuples(index=False):
        signal_row = row._asdict()
        ts_code = common.normalize_symbol(signal_row['ts_code'])
        stock_name = str(signal_row['stock_name'])
        if ts_code in account.holding_stocks and account.holding_stocks[ts_code]['lots'] > 0:
            logger.error(f"{stock_name} {ts_code} 已经持仓，不买")
            continue

        buy_day_df = range_data[(range_data['ts_code'] == ts_code) & (range_data['trade_date'] == buy_date)]
        if buy_day_df.empty:
            logger.error(f"{stock_name} {buy_date} 买入日日线为空")
            continue

        buy_day = buy_day_df.iloc[0]
        open_price = float(buy_day['open'])
        pre_close = float(buy_day['pre_close'])
        close_price = float(buy_day['close'])
        high_price = float(buy_day['high'])
        low_price = float(buy_day['low'])
        open_gap = (open_price - pre_close) / pre_close * 100

        if open_gap < 买入最低开盘涨幅 or open_gap > 买入最高开盘涨幅:
            logger.error(
                f"{stock_name} {buy_date} 开盘涨幅:{open_gap:.2f}% 不在 "
                f"{买入最低开盘涨幅}%~{买入最高开盘涨幅}% 范围内，不买"
            )
            continue
        if open_price == close_price == high_price == low_price:
            logger.error(f"{stock_name} {buy_date} 一字板，买不进，跳过")
            continue
        if open_price >= round(pre_close * 1.10, 2):
            logger.error(f"{stock_name} {buy_date} 开盘已接近涨停，开盘价:{open_price}，不买")
            continue

        buy_date_yield_rate = (close_price - open_price) / open_price * 100
        buy_status = buy(stock_name, ts_code, price=open_price, buy_date=buy_date, close_price=close_price)
        if buy_status:
            logger.warning(
                f"{stock_name} {buy_date} 以开盘价 {open_price} 买入，"
                f"开盘涨幅:{open_gap:.2f}%，当天收盘收益率:{buy_date_yield_rate:.2f}%"
            )
        else:
            logger.error(f"{stock_name} {buy_date} 买入失败")
        break

    account.next_date_pre_selection_stocks = {'selected_stocks': None, 'target_date': None}


def _同步持仓收盘(stock_info, now_row):
    close_price = float(now_row['close'])
    high_price = float(now_row['high'])
    lots = stock_info['lots']
    old_market_value = stock_info['market_value']
    market_value = round(close_price * lots, 3)

    account.market_value -= old_market_value
    account.market_value += market_value

    if high_price > stock_info.get('持仓最高价', high_price):
        stock_info['持仓最高价'] = high_price
    high_market_value = round(stock_info['持仓最高价'] * lots, 3)
    if high_market_value > stock_info['持仓最高市值']:
        stock_info['持仓最高市值'] = high_market_value

    stock_info['market_value'] = market_value
    stock_info['close_price'] = close_price
    stock_info['盈亏'] = market_value - stock_info['成本价']
    stock_info['盈亏比'] = stock_info['盈亏'] / stock_info['成本价'] * 100
    stock_info['持仓最高回撤'] = (
        (close_price - stock_info['持仓最高价']) / stock_info['持仓最高价'] * 100
        if stock_info['持仓最高价'] else 0
    )


def simulated_sell(sell_out_fall_threshold=None,
                   sell_out_rise_threshold=None,
                   sell_out_盈利回撤_threshold=最大回撤阈值,
                   now_date=None):
    logger.warning(
        f"检查强趋势增强卖出 开始 止盈:{止盈阈值}%, 最大回撤:{最大回撤阈值}%, 最大持股:{最大持股天数}天"
    )
    selected_stocks = [code for code, stock in account.holding_stocks.items() if stock['lots'] > 0]
    if not selected_stocks:
        logger.warning("检查强趋势增强卖出 完成")
        return

    query = f"""
        SELECT ts_code, trade_date, close_price AS close, stock_name, open_price AS open, previous_close AS pre_close, high_price AS high, low_price AS low, change_pct AS pct_chg
        FROM daily_quotes
        WHERE ts_code IN {common.stock_code_literals(selected_stocks)}
          AND trade_date = {int(now_date)}
    """
    now_data = pd.read_sql(query, db.engine)
    for ts_code in selected_stocks:
        stock_info = account.holding_stocks[ts_code]
        if stock_info['lots'] == 0:
            continue
        stock_now_df = now_data[now_data['ts_code'] == common.normalize_symbol(ts_code)]
        if stock_now_df.empty:
            logger.error(f"{ts_code} {stock_info['name']} {now_date} 当日数据为空")
            continue

        stock_now_row = stock_now_df.iloc[0]
        _同步持仓收盘(stock_info, stock_now_row)
        if stock_info['买入日期'] == int(now_date):
            logger.error(f"{ts_code} {stock_info['name']} 买入当天不卖")
            continue

        sell_reason = None
        if stock_info['盈亏比'] >= 止盈阈值:
            sell_reason = f"收益达到{止盈阈值}%"
        elif stock_info['持仓最高回撤'] <= 最大回撤阈值:
            sell_reason = f"最高价回撤达到{最大回撤阈值}%"
        elif stock_info['持股天数'] >= 最大持股天数:
            sell_reason = f"持股天数达到{最大持股天数}天"

        if sell_reason:
            stock_info['卖出原因'] = sell_reason
            logger.error(
                f"{ts_code} {stock_info['name']} {sell_reason} 卖出 "
                f"盈亏比:{stock_info['盈亏比']:.2f}% 最高回撤:{stock_info['持仓最高回撤']:.2f}%"
            )
            account.sell(stock_info['name'], ts_code, stock_now_row['close'], stock_info['lots'], now_date)
            continue

        stock_info['持股天数'] += 1

    logger.warning("检查强趋势增强卖出 完成")


def process_daily(target_date=None, filtered_codes=None):
    sell_out_fall_threshold = -5
    sell_out_rise_threshold = 止盈阈值
    sell_out_盈利回撤_threshold = 最大回撤阈值

    simulated_buy()
    simulated_sell(sell_out_fall_threshold=sell_out_fall_threshold,
                   sell_out_rise_threshold=sell_out_rise_threshold,
                   sell_out_盈利回撤_threshold=sell_out_盈利回撤_threshold,
                   now_date=target_date)

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
