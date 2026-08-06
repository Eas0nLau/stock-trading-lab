from datetime import datetime, timedelta
from multiprocessing import Pool

import pandas as pd
from loguru import logger

from task import _2_分时数据获取_5分k
from utils import db, common, account

symbol_ts_code_dict = common.load_stock_symbol_ts_code_dict()


def process_stock_batch(args):
    codes_batch, grouped, target_date = args
    min_rise_days = 4
    range_days = 15
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
        # if target_row['stock_name'] in ['博纳影业']:
        #     logger.info(f"当前日期：{target_date} {target_row['stock_name']}")
        #     continue
        # if target_row['stock_name'] in ['梅花生物']:
        #     # 20250703
        #     # if target_row['stock_name'] in ['森林包装']:
        #     # 20250702
        #     # if target_row['stock_name'] in ['獐子岛']:
        #     pass

        if target_row['close'] > 50 or target_row['close'] < 0:
            # logger.info("不满足 股价小于20 跳过")
            continue

        # 检查当天是否上涨
        # if target_row['pct_chg'] < 0:
        #     # logger.info("当前上涨 跳过")
        #     continue
        if target_row['pct_chg'] > 9.5:
            # logger.info("涨得太多了 跳过")
            continue
        if len(df) < range_days:  # 需要足够数据计算均量
            continue
        # if target_row['close'] < df.tail(90).iloc[:-1]['close'].max():
        #     # logger.info(f"不满足 {60}日新高 跳过")
        #     continue

        recent_data = df[df['trade_date'] <= target_date].tail(min_rise_days + range_days)

        # 检查连续 min_rise_days 天是否上涨且跌幅满足条件
        is_consecutive_rise = True
        up_count = 0
        down_count = 0
        if recent_data['pct_chg'].iloc[-min_rise_days - 1] > 0:
            continue
        for i in range(-1, -min_rise_days, -1):
            try:
                pct_chg = recent_data['pct_chg'].iloc[i]
                close = recent_data['close'].iloc[i]
                open = recent_data['open'].iloc[i]
                amount = recent_data['amount'].iloc[i]
                # logger.info(f"{target_row['stock_name']} {recent_data['trade_date'].iloc[i]} {open}")

            except:
                logger.error(f"可统计交易日为空")
                is_consecutive_rise = False
                break
            if close < open:
                is_consecutive_rise = False
                break

            if pct_chg > 7:
                is_consecutive_rise = False
                break
            if pct_chg < 0.5:
                is_consecutive_rise = False
                break

            amount = recent_data['amount'].iloc[i]
            if amount < recent_data['amount'].iloc[i - 1]:
                is_consecutive_rise = False
                break
            volatility = (amount - recent_data['amount'].iloc[i - 1]) / recent_data['amount'].iloc[i - 1] * 100
            if volatility > 50:
                is_consecutive_rise = False
                break

            if recent_data['open'].iloc[i] < recent_data['open'].iloc[i - 1]:
                is_consecutive_rise = False
                break

            if recent_data['open'].iloc[i] > recent_data['high'].iloc[i - 1]:
                is_consecutive_rise = False
                break

        if is_consecutive_rise is False:
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
    stock_daily = common.load_stock_daily_data(filtered_codes, start_date, target_date)

    logger.info(f"根据策略选择股票 开始")
    selected_stocks = []
    # 预分组 stock_daily
    grouped = stock_daily.groupby('ts_code')

    # 分批，每批 200 个代码（3000 ÷ 200 = 15 批）
    batch_size = 300
    batches = [filtered_codes[i:i + batch_size] for i in range(0, len(filtered_codes), batch_size)]

    # 使用 6 个进程（8 核留一些余量）
    with Pool(processes=2) as pool:
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
    # if common.check_指数开盘(target_date):
    #     return
    range_date = (datetime.strptime(str(target_date), "%Y%m%d") + timedelta(days=15)).strftime('%Y%m%d')

    stock_name_list = selected_stocks['stock_name'].tolist()
    # 批量查询下一交易日数据
    query = f"""
        SELECT ts_code, trade_date, close, stock_name, open, pre_close, high, low
        FROM stock_daily
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
        if volatility < -0.2:
            logger.error(f"{stock_name} 开盘跟昨日收盘偏离:{volatility} 不买")
            continue
        buy_price = open_price
        # 计算五分k
        # query = f"""
        #     SELECT trade_time AS time, open_price AS open, high_price AS high,
        #            low_price AS low, close_price AS close, volume, turnover AS amount
        #     FROM intraday_bars_5m
        #     WHERE stock_code = {ts_code}
        #     AND trade_date = {stock_name_buy_date}
        #     AND trade_time <= {f'{stock_name_buy_date}0945'}
        #     order by time
        # """
        # stock_5_min_k_data = db.mysql_localhost(sql=query, fetch=True)
        stock_5_min_k_data = _2_分时数据获取_5分k.get_data(start_date=stock_name_buy_date, end_date=stock_name_buy_date,
                                                           stock=symbol_ts_code_dict[ts_code])
        if len(stock_5_min_k_data) == 0:
            logger.error(f"{stock_name} 五分k数据为空，异常")
            exit()
        # 判断前几跟五分k是否为正
        # volatility = (float(stock_5_min_k_data[-1][1]) - float(stock_5_min_k_data[0][0])) / float(
        #     stock_5_min_k_data[0][0]) * 100
        # if volatility < 0:
        #     logger.error(f"{stock_name} 开盘10分钟后五分k偏离为:{volatility}，不买")
        #     continue
        # buy_price = float(stock_5_min_k_data[-1][1])
        # 判断买入价跟0轴偏离
        buy_price_volatility = (buy_price - pre_close) / pre_close * 100
        if buy_price_volatility > 8:
            logger.error(f"{stock_name} 开盘10分钟后五分k跟0轴偏离为:{buy_price_volatility}，已经比较高了，不追高，不买")
            continue
        if open_price == close_price == high_price == low_price:
            logger.error(f"{stock_name} {stock_name_buy_date} 一字板涨停 买不进 跳过")
            continue
        else:
            buy_date_yield_rate = (close_price - buy_price) / buy_price * 100
            buy_status = buy(stock_name, ts_code, price=buy_price, buy_date=buy_date, close_price=close_price)
            if buy_status:
                logger.warning(
                    f"{stock_name} {stock_name_buy_date} 以15分钟后价格 {buy_price} 买入，当天收盘收益率：{buy_date_yield_rate:.2f}%")
            else:
                logger.error(f"{stock_name} {str(stock_name_buy_date)} 买入失败")
                continue
    # 清空
    account.next_date_pre_selection_stocks = {
        'selected_stocks': None,
        'target_date': None,
    }


def simulated_sell(sell_out_fall_threshold=None,
                   sell_out_rise_threshold=None,
                   sell_out_盈利回撤_threshold=-5,
                   now_date=None):
    """开盘看看有没有符合卖出逻辑的进行卖出"""
    pass
    logger.warning(f"开盘看看有没有符合卖出逻辑的进行卖出 开始")
    logger.warning(f"止损阈值:{sell_out_fall_threshold},止盈阈值:{sell_out_rise_threshold}")
    selected_stocks = account.holding_stocks.keys()
    if selected_stocks:
        range_date = (datetime.strptime(str(now_date), "%Y%m%d") - timedelta(days=15)).strftime('%Y%m%d')  # 缓冲 30 天
        query = f"""
            SELECT ts_code, trade_date, close, stock_name, open, pre_close, high, low, pct_chg
            FROM stock_daily
            WHERE ts_code IN  {str(tuple([int(i) for i in selected_stocks])).replace(",)", ")")}
            AND trade_date >= {range_date}
            AND trade_date <= {now_date}
            order by trade_date
        """
        range_data = pd.read_sql(query, db.engine)
        for ts_code in selected_stocks:
            stock_info = account.holding_stocks[ts_code]
            if stock_info['持股天数'] < 2:
                logger.error(f"{ts_code} {stock_info['name']} 持仓天数小于2天，不卖")
                continue
            if stock_info['lots'] == 0:
                # logger.error(f"{ts_code} {stock_info['name']} 已卖出")
                continue
            if len(range_data[range_data['ts_code'] == ts_code]) < 3:
                continue
            # 持仓持仓最高回撤达到止损率卖出
            _持仓最高回撤 = stock_info['持仓最高回撤']
            _持仓最高市值 = stock_info['持仓最高市值']
            # 获取当前交易日
            stock_now_date_df = range_data[range_data['ts_code'] == ts_code].iloc[-1]
            # 获取上一个交易日
            stock_pre_date_df = range_data[range_data['ts_code'] == ts_code].iloc[-2]

            if _持仓最高回撤 < 0:
                account.sell(stock_info['name'], ts_code, stock_now_date_df['close'], stock_info['lots'], now_date)
                continue

    logger.warning(f"开盘看看有没有符合卖出逻辑的进行卖出 完成")
    # print_account_info()


def process_daily(target_date=None, filtered_codes=None):
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
    # 同步收盘市值
    account.sync_close_market(now_date=target_date)
    # 查看是否有符合卖出逻辑的股票进行卖出
    simulated_sell(sell_out_fall_threshold=sell_out_fall_threshold,
                   sell_out_rise_threshold=sell_out_rise_threshold,
                   sell_out_盈利回撤_threshold=sell_out_盈利回撤_threshold, now_date=target_date)
    # 同步收盘卖完市值
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



def main(start_date, end_date):
    file_name = __file__.split(".py")[0].split("\\")[-1].split("/")[-1].split("/")[-1]
    common.process_for_strategy(start_date, end_date, process_daily, file_name)


if __name__ == "__main__":
    main(start_date=int(datetime.now().strftime('%Y%m%d')), end_date=int(datetime.now().strftime('%Y%m%d')))
