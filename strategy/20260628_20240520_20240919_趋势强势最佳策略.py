import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from loguru import logger

项目根目录 = Path(__file__).resolve().parents[1]
sys.path.append(str(项目根目录))

from utils import account, common, db


策略名称 = '20260628_20240520_20240919_趋势强势最佳策略'
# 开始日期 = 20240520
# 结束日期 = 20240919
开始日期 = 20260620
结束日期 = int(datetime.now().strftime('%Y%m%d'))

最大仓位数 = 1
单日最多买入数 = 1
候选返回数量 = 10

最小涨幅 = 1.0
最大涨幅 = 8.5
近5日最小涨幅 = 0.0
近20日最大涨幅 = 80.0
成交额下限 = 200000
成交额放大倍数 = 1.0
买入最低开盘涨幅 = -2.0
买入最高开盘涨幅 = 4.5
止盈阈值 = 8.0
止损阈值 = -3.5
最大持股天数 = 3


def _提取整数股票代码集合(codes):
    if codes is None:
        return set()
    codes_series = pd.Series(list(codes)).astype(str).str.extract(r'(\d+)')[0].dropna()
    if codes_series.empty:
        return set()
    return set(codes_series.astype(int).tolist())


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


def _读取日线数据(trade_dates, filtered_codes=None):
    trade_date_tuple = str(tuple([int(i) for i in trade_dates])).replace(',)', ')')
    code_filter = ''
    codes = sorted(_提取整数股票代码集合(filtered_codes))
    if codes:
        code_filter = f"AND sd.ts_code IN {str(tuple(codes)).replace(',)', ')')}"

    return pd.read_sql(
        f"""
            SELECT
                sd.ts_code,
                sd.trade_date,
                sd.open_price AS open,
                sd.high_price AS high,
                sd.low_price AS low,
                sd.close_price AS close,
                sd.previous_close AS pre_close,
                sd.turnover AS amount,
                sd.change_pct AS pct_chg,
                sd.stock_name,
                sb.market,
                sb.list_status
            FROM daily_quotes sd
            LEFT JOIN securities sb ON SUBSTRING_INDEX(sd.ts_code, '.', 1) = sb.symbol
            WHERE sd.trade_date IN {trade_date_tuple}
              {code_filter}
              AND sb.market = '主板'
              AND sb.list_status = 'L'
              AND sd.open_price IS NOT NULL
              AND sd.high_price IS NOT NULL
              AND sd.low_price IS NOT NULL
              AND sd.close_price IS NOT NULL
              AND sd.previous_close IS NOT NULL
              AND sd.turnover IS NOT NULL
              AND sd.change_pct IS NOT NULL
              AND sd.previous_close > 0
              AND sd.stock_name NOT REGEXP 'ST|退'
            ORDER BY sd.ts_code, sd.trade_date
        """,
        db.engine,
    )


def _计算技术指标(日线数据):
    日线数据 = 日线数据.copy()
    日线数据['ts_code'] = 日线数据['ts_code'].astype(int)
    日线数据 = 日线数据.sort_values(['ts_code', 'trade_date'])
    group = 日线数据.groupby('ts_code', group_keys=False)
    日线数据['ma5'] = group['close'].transform(lambda s: s.rolling(5, min_periods=5).mean())
    日线数据['ma10'] = group['close'].transform(lambda s: s.rolling(10, min_periods=10).mean())
    日线数据['ma20'] = group['close'].transform(lambda s: s.rolling(20, min_periods=20).mean())
    日线数据['amount_ma20_pre'] = group['amount'].transform(lambda s: s.shift(1).rolling(20, min_periods=20).mean())
    日线数据['ret5'] = group['close'].transform(lambda s: (s / s.shift(5) - 1) * 100)
    日线数据['ret20'] = group['close'].transform(lambda s: (s / s.shift(20) - 1) * 100)
    日线数据['是否跌停'] = (日线数据['pct_chg'] <= -9.5) & (日线数据['close'] == 日线数据['low'])
    日线数据['一字'] = (
        (日线数据['open'] == 日线数据['high']) &
        (日线数据['high'] == 日线数据['low']) &
        (日线数据['low'] == 日线数据['close'])
    )
    振幅 = 日线数据['high'] - 日线数据['low']
    日线数据['收盘位置'] = ((日线数据['close'] - 日线数据['low']) / 振幅).where(振幅 != 0, 0.5)
    return 日线数据


def strategy(filtered_codes, target_date):
    """
    趋势强势最佳参数版：
    - 主板、非ST、非退市；
    - 当日涨幅 1% 到 8.5%；
    - 近5日涨幅 >= 0，近20日涨幅 <= 80；
    - 成交额 >= 2 亿，且不低于前20日均额；
    - close > MA5 > MA10 > MA20；
    - 收盘位置 >= 0.55；
    - 排除一字和跌停。
    """
    target_date = int(target_date)
    logger.warning(f"【{策略名称}】开始筛选 {target_date} ...")

    try:
        trade_dates = _最近交易日列表(target_date, 80)
    except ValueError as exc:
        logger.warning(f"{target_date} 数据不足：{exc}")
        return pd.DataFrame([])

    日线数据 = _读取日线数据(trade_dates, filtered_codes)
    if 日线数据.empty:
        logger.warning(f"{target_date} 无足够日线数据")
        return pd.DataFrame([])

    日线数据 = _计算技术指标(日线数据)
    当日数据 = 日线数据[日线数据['trade_date'] == target_date].copy()
    if 当日数据.empty:
        logger.warning(f"{target_date} 当日日线为空")
        return pd.DataFrame([])

    selected_df = 当日数据[
        (当日数据['pct_chg'].between(最小涨幅, 最大涨幅)) &
        (当日数据['ret5'] >= 近5日最小涨幅) &
        (当日数据['ret20'] <= 近20日最大涨幅) &
        (当日数据['amount'] >= 成交额下限) &
        (当日数据['amount'] >= 当日数据['amount_ma20_pre'] * 成交额放大倍数) &
        (当日数据['close'] > 当日数据['ma5']) &
        (当日数据['ma5'] > 当日数据['ma10']) &
        (当日数据['ma10'] > 当日数据['ma20']) &
        (当日数据['收盘位置'] >= 0.55) &
        (~当日数据['是否跌停']) &
        (~当日数据['一字'])
    ].copy()

    if selected_df.empty:
        logger.error(f"{target_date} 未筛选到符合趋势强势最佳参数的股票")
        return pd.DataFrame([])

    selected_df['策略分'] = (
        selected_df['amount'] / 1000000 * 3
        + selected_df['ret5'].clip(-10, 40) * 0.08
        + selected_df['pct_chg'].clip(-5, 10) * 0.15
        + selected_df['收盘位置'].fillna(0) * 1.2
    )
    selected_df = selected_df.sort_values(
        ['策略分', 'amount'],
        ascending=False,
        kind='mergesort',
    ).head(候选返回数量).reset_index(drop=True)
    selected_df['排序'] = selected_df.index + 1

    logger.warning(f"{target_date} 【{策略名称}】最终选中 {len(selected_df)} 只股票")
    logger.warning(f"入选股票：{' '.join(selected_df['stock_name'].astype(str).tolist())}")
    for _, row in selected_df.iterrows():
        logger.info(
            f"   → 候选 {row['stock_name']} {int(row['ts_code'])} | 排序:{int(row['排序'])} | "
            f"涨幅:{row['pct_chg']:.2f}% | 近5日:{row['ret5']:.2f}% | 近20日:{row['ret20']:.2f}% | "
            f"成交额:{row['amount']:.2f} | MA5:{row['ma5']:.2f} MA10:{row['ma10']:.2f} MA20:{row['ma20']:.2f} | "
            f"收盘位置:{row['收盘位置']:.2f} | 策略分:{row['策略分']:.2f}"
        )

    return selected_df[[
        'ts_code', 'stock_name', 'trade_date',
        'open', 'high', 'low', 'close', 'pre_close', 'amount', 'pct_chg',
        'ma5', 'ma10', 'ma20', 'amount_ma20_pre',
        'ret5', 'ret20', '收盘位置', '策略分', '排序',
    ]]


def buy(name, code, price, buy_date, close_price, signal_date):
    code = int(code)
    if code in account.holding_stocks:
        logger.error(f"{name} {code} 已经买过，本策略不允许重复买，不买了。")
        return False

    price_max = (account.available_amount + account.market_value) / 最大仓位数
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
        '信号日期': signal_date,
        '卖出原因': None,
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

    query = f"""
        SELECT ts_code, trade_date, close_price AS close, stock_name, open_price AS open, previous_close AS pre_close, high_price AS high, low_price AS low
        FROM daily_quotes
        WHERE ts_code IN {str(tuple([int(i) for i in selected_stocks['ts_code'].tolist()])).replace(',)', ')')}
          AND trade_date = {int(buy_date)}
    """
    buy_day_data = pd.read_sql(query, db.engine)
    selected_stocks = selected_stocks.sort_values('策略分', ascending=False, kind='mergesort')
    bought_count = 0

    for row in selected_stocks.itertuples(index=False):
        if bought_count >= 单日最多买入数:
            break

        ts_code = int(row.ts_code)
        stock_name = str(row.stock_name)
        if ts_code in account.holding_stocks:
            logger.error(f"{stock_name} {ts_code} 已经买过，本策略不允许重复买，跳过")
            continue

        buy_day_df = buy_day_data[buy_day_data['ts_code'] == ts_code]
        if buy_day_df.empty:
            logger.error(f"{stock_name} {buy_date} 买入日日线为空")
            continue
        buy_day = buy_day_df.iloc[0]

        open_price = float(buy_day['open'])
        pre_close = float(buy_day['pre_close'])
        high_price = float(buy_day['high'])
        low_price = float(buy_day['low'])
        close_price = float(buy_day['close'])
        open_gap = (open_price - pre_close) / pre_close * 100

        if open_gap < 买入最低开盘涨幅 or open_gap > 买入最高开盘涨幅:
            logger.error(
                f"{stock_name} {buy_date} 开盘涨幅:{open_gap:.2f}% 不在 "
                f"{买入最低开盘涨幅}%~{买入最高开盘涨幅}% 范围内，不买"
            )
            continue
        if open_price == high_price == low_price == close_price:
            logger.error(f"{stock_name} {buy_date} 一字，不买")
            continue
        if open_price >= pre_close * 1.095:
            logger.error(f"{stock_name} {buy_date} 开盘接近涨停，不买")
            continue

        buy_date_yield_rate = (close_price - open_price) / open_price * 100
        buy_status = buy(
            stock_name,
            ts_code,
            price=open_price,
            buy_date=int(buy_date),
            close_price=close_price,
            signal_date=target_date,
        )
        if buy_status:
            bought_count += 1
            logger.warning(
                f"{stock_name} {buy_date} 以开盘价 {open_price:.2f} 买入，"
                f"开盘涨幅:{open_gap:.2f}%，当天收盘收益率:{buy_date_yield_rate:.2f}%"
            )
        else:
            logger.error(f"{stock_name} {buy_date} 买入失败")

    account.next_date_pre_selection_stocks = {'selected_stocks': None, 'target_date': None}


def simulated_sell(now_date=None):
    logger.warning(f"检查止盈止损/MA5破位/到期卖出 开始")
    selected_codes = [int(code) for code, stock in account.holding_stocks.items() if stock['lots'] > 0]
    if not selected_codes:
        logger.warning(f"检查止盈止损/MA5破位/到期卖出 完成")
        return

    try:
        trade_dates = _最近交易日列表(now_date, 10)
    except ValueError as exc:
        logger.warning(f"{now_date} 卖出检查数据不足：{exc}")
        return

    range_data = _读取日线数据(trade_dates, selected_codes)
    if range_data.empty:
        logger.warning(f"{now_date} 持仓日线为空")
        return
    range_data = _计算技术指标(range_data)
    now_data = range_data[range_data['trade_date'] == int(now_date)].copy()

    for ts_code in selected_codes:
        stock_info = account.holding_stocks[ts_code]
        if stock_info['lots'] == 0:
            continue
        if stock_info['买入日期'] == int(now_date):
            logger.error(f"{ts_code} {stock_info['name']} 买入当天不卖")
            continue

        stock_now_df = now_data[now_data['ts_code'] == ts_code]
        if stock_now_df.empty:
            logger.error(f"{ts_code} {stock_info['name']} {now_date} 当日数据为空")
            continue
        stock_now = stock_now_df.iloc[0]

        buy_price = float(stock_info['买入价'])
        target_price = buy_price * (1 + 止盈阈值 / 100)
        stop_price = buy_price * (1 + 止损阈值 / 100)
        open_price = float(stock_now['open'])
        high_price = float(stock_now['high'])
        low_price = float(stock_now['low'])
        close_price = float(stock_now['close'])
        sell_price = None
        sell_reason = None

        if open_price <= stop_price:
            sell_price = open_price
            sell_reason = f"开盘跌破止损{止损阈值}%"
        elif open_price >= target_price:
            sell_price = open_price
            sell_reason = f"开盘达到止盈{止盈阈值}%"
        elif low_price <= stop_price and high_price >= target_price:
            sell_price = stop_price
            sell_reason = "同日触发止盈止损，按保守止损"
        elif low_price <= stop_price:
            sell_price = stop_price
            sell_reason = f"日内触发止损{止损阈值}%"
        elif high_price >= target_price:
            sell_price = target_price
            sell_reason = f"日内触发止盈{止盈阈值}%"
        elif pd.notna(stock_now['ma5']) and close_price < float(stock_now['ma5']):
            sell_price = close_price
            sell_reason = f"收盘跌破MA5 close={close_price:.2f}, MA5={float(stock_now['ma5']):.2f}"
        elif stock_info['持股天数'] > 最大持股天数:
            sell_price = close_price
            sell_reason = f"持仓超过{最大持股天数}天"

        if sell_price is None:
            continue

        stock_info['卖出原因'] = sell_reason
        logger.error(
            f"{ts_code} {stock_info['name']} {sell_reason} 卖出 | "
            f"卖出价:{sell_price:.2f} 盈亏比:{stock_info['盈亏比']:.2f}%"
        )
        account.sell(stock_info['name'], ts_code, sell_price, stock_info['lots'], int(now_date))

    logger.warning(f"检查止盈止损/MA5破位/到期卖出 完成")


def process_daily(target_date=None, filtered_codes=None):
    account.sync_open_market_before(now_date=target_date)
    simulated_buy()
    account.sync_close_market(now_date=target_date)
    simulated_sell(now_date=target_date)
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
