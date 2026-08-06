import traceback
from datetime import datetime, timedelta
from multiprocessing import Pool

import pandas as pd
from loguru import logger

from utils import db, common, account


def process_stock_batch(args):
    codes_batch, grouped, target_date = args
    min_rise_days = 30
    results = []
    for ts_code in codes_batch:
        # 使用预分组数据
        if ts_code not in grouped.groups:
            # logger.warning(f"ts_code {ts_code} not found in daily_quotes, skipping")
            continue
        df = grouped.get_group(ts_code)
        target_data = df[df['trade_date'] == target_date]
        if target_data.empty:
            continue

        # 红K线：收盘价 > 开盘价，涨幅在 min_pct_chg 到 max_pct_chg 之间
        target_row = target_data.iloc[0]

        # 20250701
        # if target_row['stock_name'] not in ['创元科技']:
        #     continue
        if target_row['close'] > 50 or target_row['close'] < 2:
            # logger.info("不满足 股价小于20 跳过")
            continue

        # 检查当天是否上涨
        # if target_row['pct_chg'] < 0:
        #     # logger.info("当前上涨 跳过")
        #     continue
        if target_row['pct_chg'] < 2:
            continue
        if target_row['pct_chg'] > 8:
            continue
        # if len(df) < range_days:  # 需要足够数据计算均量
        #     continue
        recent_data = df[df['trade_date'] < target_date].tail(min_rise_days)
        if recent_data.empty:
            continue
        if target_row['close'] < recent_data.iloc[-1]['high']:
            continue
        if target_row['vol'] < recent_data.iloc[-1]['vol'] * 1.05:
            continue
        if recent_data.iloc[-1]['pct_chg'] > -2 or recent_data.iloc[-1]['pct_chg'] < -8:
            continue
        if recent_data.iloc[-2]['pct_chg'] > -1 or recent_data.iloc[-1]['pct_chg'] < -8:
            continue

        # 1日前~45日前 上下波动设置阈值偏离不能超过平均值上下10%
        _day_ago_close_mean = recent_data['close'].mean()
        _day_ago_high_max = recent_data['high'].max()
        _day_ago_high_volatility = abs(_day_ago_high_max - _day_ago_close_mean) / min(_day_ago_close_mean,
                                                                                      _day_ago_high_max) * 100
        _day_ago_low_min = recent_data['low'].min()
        _day_ago_low_volatility = abs(_day_ago_low_min - _day_ago_close_mean) / min(_day_ago_close_mean,
                                                                                    _day_ago_low_min) * 100
        volatility = abs(_day_ago_high_max - _day_ago_low_min) / min(_day_ago_low_min, _day_ago_high_max) * 100
        logger.info(
            f"{target_date} {target_row['stock_name']} 近 {min_rise_days} 日 波动率：{volatility} 收盘平均价：{_day_ago_close_mean} 最高价：{_day_ago_high_max} 最低价：{_day_ago_low_min} "
            f"上波动率：{_day_ago_high_volatility:.2f}% 下波动率：{_day_ago_low_volatility:.2f}%")
        if _day_ago_high_volatility >= 30 or _day_ago_low_volatility >= 30:
            # logger.info(f"不满足 1日前~{range_days}日前 上下波动设置阈值偏离不能超过平均值上下5% 跳过")
            continue
        volatility_threshold = 70
        if volatility >= volatility_threshold:
            # logger.info(f"不满足 1日前~{range_days}日前 上下波动率大于{volatility_threshold}% 跳过")
            continue
        logger.warning(f"当前日期：{target_date} {target_row['stock_name']} 入选")
        pass
        results.append({
            'ts_code': ts_code,
            'stock_name': target_row['stock_name'],
            'trade_date': target_row['trade_date'],
            'close': target_row['close']
        })
    return results


def strategy(filtered_codes, target_date):
    """
    根据“策略筛选指定日期的股票
    参数:
        filtered_codes: 过滤后的股票池 DataFrame
        target_date: 目标日期（格式：YYYYMMDD）
    返回:
        DataFrame: 选中的股票（ts_code, stock_name, trade_date, close）
    """
    # 计算前 range_days 交易日的起始日期
    range_days = 30

    start_date = (datetime.strptime(str(target_date), "%Y%m%d") - timedelta(days=range_days)).strftime(
        '%Y%m%d')  # 余量确保足够数据

    # 加载日线数据
    daily_quotes = common.load_daily_quotes_data(filtered_codes, start_date, target_date)

    logger.info(f"根据策略选择股票 开始")
    selected_stocks = []
    # 预分组 daily_quotes
    grouped = daily_quotes.groupby('ts_code')

    # 分批，每批 200 个代码（3000 ÷ 200 = 15 批）
    batch_size = 300
    batches = [filtered_codes[i:i + batch_size] for i in range(0, len(filtered_codes), batch_size)]
    # for batch in batches:
    #     process_stock_batch(args=(batch, grouped, target_date))
    # 使用 6 个进程（8 核留一些余量）
    try:
        with Pool(processes=6) as pool:
            tasks = [(batch, grouped, target_date) for batch in batches]
            results = pool.imap_unordered(process_stock_batch, tasks)

            # 最小化 tqdm 开销
            for batch_results in results:
                selected_stocks.extend(batch_results)
    except Exception as e:
        logger.error(f"{e}")
        logger.error(traceback.format_exc())
        return pd.DataFrame([])
    selected_df = pd.DataFrame(selected_stocks)
    if not selected_df.empty:
        # selected_df.to_csv(f'../data/red_k_stocks_{target_date.replace("-", "")}.csv', index=False,
        #                    encoding='utf-8-sig')
        logger.warning(f"筛选出 {len(selected_df)} 只符合策略的股票（日期：{target_date}）")
        selected_stock_name = selected_df['stock_name'].tolist()
        logger.warning(f"{' '.join(selected_stock_name)}")

    else:
        logger.warning(f"在 {target_date} 未找到符合策略的股票")
    return selected_df


def buy(name, code, price, buy_date, close_price):
    # if code in holding_stocks:
    #     logger.error(f"{name} {code} 买过了，不买了。")
    #     return False
    if code in account.holding_stocks and account.holding_stocks[code]['lots'] > 0:
        logger.error(f"{name} {code} 买有了，不买了。")
        return False
    price_max = (account.available_amount + account.market_value) / 5
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
        # 股数
        'lots': lots,
        # 市值
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
    }
    return True


def simulated_buy():
    selected_stocks = account.next_date_pre_selection_stocks['selected_stocks']
    target_date = account.next_date_pre_selection_stocks['target_date']
    if selected_stocks is None or target_date is None:
        logger.error("下一日预选买入池 为空")
        return

    if common.check_指数开盘(target_date):
        return
    range_date = (datetime.strptime(str(target_date), "%Y%m%d") + timedelta(days=15)).strftime('%Y%m%d')

    stock_name_list = selected_stocks['stock_name'].tolist()
    # 批量查询下一交易日数据
    query = f"""
        SELECT ts_code, trade_date, close_price AS close, stock_name, open_price AS open, previous_close AS pre_close, high_price AS high, low_price AS low
        FROM daily_quotes
        WHERE ts_code IN {common.stock_code_literals(selected_stocks['ts_code'].tolist())}
        AND trade_date >= {target_date}
        AND trade_date <= {range_date}
        order by trade_date
    """
    range_data = pd.read_sql(query, db.engine)
    # buy_date = range_data['trade_date'].min()
    # 入选后的交易日期
    after_purchase_date_list = sorted(list(set(range_data['trade_date'].tolist())))
    if len(after_purchase_date_list) <= 1:
        msg = f"{target_date}下一交易日 入选后可买入的交易日期为空 {stock_name_list} "
        logger.warning(msg)
        account.next_date_pre_selection_stocks = {
            'selected_stocks': None,
            'target_date': None,
        }
        return
    buy_date = common.get_next_date(target_date)

    for stock_name in stock_name_list:
        stock_name_df = range_data[range_data['stock_name'] == stock_name]
        if stock_name_df.empty:
            logger.error(f"{stock_name} 入选后可统计的交易日期为空")
            continue
        stock_name_buy_date = buy_date
        # 买入日期open价
        if stock_name_df[stock_name_df['trade_date'] == stock_name_buy_date].empty:
            logger.error(f"{stock_name} 入选后可统计的交易日期为空")
            continue
        pre_close = stock_name_df[stock_name_df['trade_date'] == stock_name_buy_date].iloc[0]['pre_close']
        open_price = stock_name_df[stock_name_df['trade_date'] == stock_name_buy_date].iloc[0]['open']
        close_price = stock_name_df[stock_name_df['trade_date'] == stock_name_buy_date].iloc[0]['close']
        high_price = stock_name_df[stock_name_df['trade_date'] == stock_name_buy_date].iloc[0]['high']
        low_price = stock_name_df[stock_name_df['trade_date'] == stock_name_buy_date].iloc[0]['low']
        ts_code = stock_name_df[stock_name_df['trade_date'] == stock_name_buy_date].iloc[0]['ts_code']
        volatility = (open_price - pre_close) / pre_close * 100
        if volatility < 1:
            logger.error(f"{stock_name} 开盘跟昨日收盘偏离:{volatility} 不买")
            continue
        if open_price == close_price == high_price == low_price:
            # logger.error(f"{stock_name} {stock_name_buy_date} 一字板涨停 买不进 跳过")
            continue
        else:
            buy_date_yield_rate = (close_price - open_price) / open_price * 100
            buy_status = buy(stock_name, ts_code, price=open_price, buy_date=buy_date, close_price=close_price)
            if buy_status:
                logger.warning(
                    f"{stock_name} {stock_name_buy_date} 以开盘价 {open_price} 买入，当天收盘收益率：{buy_date_yield_rate:.2f}%")
            else:
                logger.error(f"{stock_name} {stock_name_buy_date} 买入失败")
                continue
    # 清空
    account.next_date_pre_selection_stocks = {
        'selected_stocks': None,
        'target_date': None,
    }


def start(target_date=None, filtered_codes=None):
    """
    主函数：加载股票池，筛选股票，评估胜率
    """
    sell_out_fall_threshold = -5
    sell_out_rise_threshold = 40
    sell_out_盈利回撤_threshold = -5

    # 同步早盘操作前市值
    account.sync_open_market_before(now_date=target_date)
    # 昨日选中模拟买入 早盘
    simulated_buy()
    # 查看是否有符合卖出逻辑的股票进行卖出
    account.simulated_sell(sell_out_fall_threshold=sell_out_fall_threshold,
                           sell_out_rise_threshold=sell_out_rise_threshold,
                           sell_out_盈利回撤_threshold=sell_out_盈利回撤_threshold, now_date=target_date)
    # 同步收盘市值
    account.sync_close_market(now_date=target_date)
    # 2. 筛选股票
    selected_stocks = strategy(filtered_codes, target_date)
    if selected_stocks.empty:
        logger.error(f"{target_date} 未筛选到符合策略的股票")
        return
    # 加入下一日买入列表
    account.add_next_date_stocks(selected_stocks, target_date)

    # 3. 评估下一交易日胜率
    return


def main():
    # 1. 加载股票池
    filtered_codes = common.load_stock_pool_symbol()
    distinct_trade_date = db.mysql_localhost(sql=f"""
        select distinct trade_date FROM daily_quotes
        where trade_date >= 20250101
        and trade_date < 20251001
        order by trade_date
    """, fetch=True)
    for target_date in distinct_trade_date:
        target_date = target_date['trade_date']
        start(target_date, filtered_codes)
        account.print_account_info()


if __name__ == "__main__":
    main()
