from datetime import datetime, timedelta
from multiprocessing import Pool

import pandas as pd
from loguru import logger

from utils import db, common, account


def process_stock_batch(args):
    codes_batch, grouped, target_date = args
    min_rise_days = 4
    results = []
    for ts_code in codes_batch:
        # 使用预分组数据
        if ts_code not in grouped.groups:
            # logger.warning(f"ts_code {ts_code} not found in stock_daily, skipping")
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
        # logger.info(f"当前日期：{target_date} {target_row['stock_name']}")
        # if target_row['stock_name'] in ['梅花生物']:
        #     # 20250703
        #     # if target_row['stock_name'] in ['森林包装']:
        #     # 20250702
        #     # if target_row['stock_name'] in ['獐子岛']:
        #     pass

        if target_row['close'] > 30 or target_row['close'] < 2:
            # logger.info("不满足 股价小于20 跳过")
            continue

        # 检查当天是否上涨
        # if target_row['pct_chg'] < 0:
        #     # logger.info("当前上涨 跳过")
        #     continue
        if target_row['pct_chg'] > 5:
            # logger.info("涨得太多了 跳过")
            continue
        # if len(df) < range_days:  # 需要足够数据计算均量
        #     continue
        if target_row['close'] < df.tail(90).iloc[:-1]['close'].max():
            # logger.info(f"不满足 {60}日新高 跳过")
            continue

        recent_data = df[df['trade_date'] <= target_date].tail(min_rise_days)

        # 检查连续 min_rise_days 天是否上涨且跌幅满足条件
        is_consecutive_rise = True
        up_count = 0
        down_count = 0
        for i in range(-1, -min_rise_days - 1, -1):
            try:
                pct_chg = recent_data['pct_chg'].iloc[i]
                close = recent_data['close'].iloc[i]
                open = recent_data['open'].iloc[i]
            except:
                logger.error(f"可统计交易日为空")
                is_consecutive_rise = False
                break
            # if pct_chg < -1.5:
            #     is_consecutive_rise = False
            #     break
            if pct_chg > 5:
                is_consecutive_rise = False
                break
            if pct_chg > 0.5:
                up_count += 1
                continue
            if pct_chg < -0.5:
                down_count += 1
                continue
        if down_count > 0:
            continue
        if is_consecutive_rise is False:
            continue
        # logger.warning(f"当前日期：{target_date} {target_row['stock_name']} 入选")
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
    range_days = 90

    start_date = (datetime.strptime(str(target_date), "%Y%m%d") - timedelta(days=range_days)).strftime(
        '%Y%m%d')  # 余量确保足够数据

    # 加载日线数据
    stock_daily = common.load_stock_daily_data(filtered_codes, start_date, target_date)

    logger.info(f"根据策略选择股票 开始")
    selected_stocks = []
    # 预分组 stock_daily
    grouped = stock_daily.groupby('ts_code')

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
    if common.check_指数开盘(target_date):
        return
    range_date = (datetime.strptime(str(target_date), "%Y%m%d") + timedelta(days=15)).strftime('%Y%m%d')

    stock_name_list = selected_stocks['stock_name'].tolist()
    # 批量查询下一交易日数据
    query = f"""
        SELECT ts_code, trade_date, close, stock_name, open, pre_close, high, low
        FROM stock_daily
        WHERE ts_code IN  {str(tuple([int(i) for i in selected_stocks['ts_code'].tolist()])).replace(",)", ")")}
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
        if volatility < 0.5:
            # logger.error(f"{stock_name} 开盘跟昨日收盘偏离:{volatility} 不买")
            continue
        if open_price == close_price == high_price == low_price:
            # logger.error(f"{stock_name} {stock_name_buy_date} 一字板涨停 买不进 跳过")
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


def start(target_date=None, filtered_codes=None):
    """
    主函数：加载股票池，筛选股票，评估胜率
    """
    sell_out_fall_threshold = -5
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
        return
    # 加入下一日买入列表
    account.add_next_date_stocks(selected_stocks, target_date)

    # 3. 评估下一交易日胜率
    return


def main():
    # 1. 加载股票池
    filtered_codes = common.load_stock_pool_symbol()
    distinct_trade_date = db.mysql_localhost(sql=f"""
        select distinct trade_date FROM stock_daily
        where trade_date >= '20250501'
        and trade_date < '20250901'
        order by trade_date
    """, fetch=True)
    for target_date in distinct_trade_date:
        target_date = target_date['trade_date']
        start(target_date, filtered_codes)

    account.print_account_info()


if __name__ == "__main__":
    main()
