from datetime import datetime, timedelta
from multiprocessing import Pool

import pandas as pd
from loguru import logger

from utils import db, common, account


def process_stock_batch(args):
    codes_batch, grouped, target_date = args
    results = []
    for ts_code in codes_batch:
        # 使用预分组数据
        if ts_code not in grouped.groups:
            # logger.warning(f"ts_code {ts_code} not found in daily_quotes, skipping")
            continue
        df = grouped.get_group(ts_code)
        if len(df) < 10:
            continue
        target_data = df[df['trade_date'] == target_date]
        if target_data.empty:
            continue
        target_row = target_data.iloc[0]

        # if target_row['stock_name'] not in ['宇晶股份']:
        #     # logger.info(f"当前日期：{target_date} {target_row['stock_name']}")
        #     continue
        if target_row['close'] > 200:
            continue
        if target_row['amount'] < 200000:  # 2亿
            continue
        if df.tail(2).iloc[-2]['amount'] < 1000000:  # 10亿
            continue
        # 昨日爆量 是前日的五倍的
        if df.tail(2).iloc[-2]['amount'] / 5 < df.tail(3).iloc[-3]['amount']:
            continue
        if df.tail(2).iloc[-2]['amount'] <= df.tail(45).iloc[:-2]['amount'].max():
            continue
        # 收盘价>爆量最低价
        if target_row['close'] < df.tail(2).iloc[-2]['low']:
            continue

        logger.warning(f"当前日期：{target_date} {target_row['stock_name']} 入选")
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
    # range_days = 180

    # 新高
    range_days = 60

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

    # 使用 6 个进程（8 核留一些余量）
    with Pool(processes=6) as pool:
        tasks = [(batch, grouped, target_date) for batch in batches]
        results = pool.imap_unordered(process_stock_batch, tasks)

        # 最小化 tqdm 开销
        for batch_results in results:
            selected_stocks.extend(batch_results)

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


def simulated_buy():
    selected_stocks = account.next_date_pre_selection_stocks['selected_stocks']
    target_date = account.next_date_pre_selection_stocks['target_date']
    if selected_stocks is None or target_date is None:
        logger.error("下一日预选买入池 为空")
        return
    # if common.check_指数开盘(target_date):
    #     return
    range_date = (datetime.strptime(str(target_date), "%Y%m%d") + timedelta(days=15)).strftime('%Y%m%d')

    stock_name_list = selected_stocks['stock_name'].tolist()
    # 批量查询下一交易日数据
    query = f"""
        SELECT ts_code, trade_date, close_price AS close, stock_name, open_price AS open, previous_close AS pre_close, high_price AS high, low_price AS low
        FROM daily_quotes
        WHERE ts_code IN {str(tuple(selected_stocks['ts_code'].tolist())).replace(",)", ")")}
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
        if volatility < -0.1:
            logger.error(f"{stock_name} 开盘跟昨日收盘偏离:{volatility} 不买")
            continue
        target_date_high = stock_name_df[stock_name_df['trade_date'] == target_date].iloc[0]['high']
        # if pre_close >= close_price:
        #     # logger.error(f"{stock_name} 未开在昨日最高点之上不买")
        #     continue
        is_一字板涨停 = False
        if open_price == close_price == high_price == low_price:
            is_一字板涨停 = True
            logger.error(f"{stock_name} {stock_name_buy_date} 一字板涨停 买不进 跳过")
            continue
        else:
            buy_date_yield_rate = (close_price - open_price) / open_price * 100
            buy_status = account.buy(stock_name, ts_code, price=open_price, buy_date=buy_date, close_price=close_price)
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


def process_daily(target_date=None, filtered_codes=None):
    """
    主函数：加载股票池，筛选股票，评估胜率
    """
    sell_out_fall_threshold = -3
    sell_out_rise_threshold = 30

    # 同步早盘操作前市值
    account.sync_open_market_before(now_date=target_date)
    # 昨日选中模拟买入 早盘
    simulated_buy()
    # 查看是否有符合卖出逻辑的股票进行卖出
    account.simulated_sell(sell_out_fall_threshold=sell_out_fall_threshold,
                           sell_out_rise_threshold=sell_out_rise_threshold, now_date=target_date)
    # 同步收盘市值
    account.sync_close_market(now_date=target_date)
    # 2. 筛选股票
    selected_stocks = strategy(filtered_codes, target_date)
    if selected_stocks.empty:
        logger.error(f"{target_date} 未筛选到符合策略的股票")
        return {
            'msg': f"{target_date} 未筛选到符合策略的股票",
        }
    # 加入下一日买入列表
    account.add_next_date_stocks(selected_stocks, target_date)

    # 3. 评估下一交易日胜率
    return



def main(start_date, end_date):
    file_name = __file__.split(".py")[0].split("\\")[-1].split("/")[-1].split("/")[-1]
    common.process_for_strategy(start_date, end_date, process_daily, file_name)


if __name__ == "__main__":
    main(start_date=20260415, end_date=20270901)