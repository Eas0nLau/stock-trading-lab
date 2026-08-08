from datetime import datetime, timedelta

import pandas as pd
from loguru import logger

from utils import db, common, account
from utils.common import timer_statistics

from multiprocessing import Pool


def process_stock_batch(args):
    codes_batch, 日线数据, target_date = args
    batch_data = 日线数据[日线数据['ts_code'].isin(codes_batch)]
    grouped = batch_data.groupby('ts_code')
    候选列表 = []
    for ts_code in codes_batch:
        if len(str(ts_code)) > 5 and str(ts_code)[0:2] in ['92', '68', '30']:
            continue
        # 使用预分组数据
        if ts_code not in grouped.groups:
            continue
        单股数据 = grouped.get_group(ts_code)
        if len(单股数据) < 15:
            continue
        当天数据 = 单股数据.iloc[-1]
        股票名称 = 当天数据.get('stock_name', f"未知{ts_code}")
        if 'ST' in 股票名称:
            continue
        # 当天必须上涨 ≥ 0.8%
        if 当天数据['pct_chg'] < 0.8:
            continue
        if 当天数据['pct_chg'] > 8:
            continue

        if 单股数据.tail(10)['pct_chg'].min() < -9:
            # logger.info("存在跌停 跳过")
            continue
        # 近5日累计下跌 ≥ 8%
        近5日累计 = 单股数据.iloc[-6:-1]['pct_chg'].sum()
        if 近5日累计 > -8:
            continue

        # 成交量放大
        前10日均量 = 单股数据.iloc[-11:-1]['vol'].mean()
        if 当天数据['vol'] < 前10日均量 * 1.6:
            continue

        股票名称 = 当天数据.get('stock_name', f"未知{ts_code}")

        候选列表.append({
            'ts_code': common.normalize_symbol(ts_code),
            'stock_name': 股票名称,
            'trade_date': target_date,
            'close': float(当天数据['close']),
            'pct_chg': float(当天数据['pct_chg']),
            '近5日累计跌幅': 近5日累计,
            '量比': 当天数据['vol'] / 前10日均量
        })

        logger.info(
            f"候选 {股票名称} | 近5日累计跌幅:{近5日累计:.2f}% | 当天涨幅:{当天数据['pct_chg']:.2f}% | 量比:{当天数据['vol'] / 前10日均量:.2f}x")
    return 候选列表


@timer_statistics
def strategy(filtered_codes, target_date):
    target_date = int(target_date)
    logger.warning(f"开始筛选 {target_date} ...")

    开始日期 = (datetime.strptime(str(target_date), "%Y%m%d") - timedelta(days=30)).strftime('%Y%m%d')
    日线数据 = common.load_daily_quotes_data(filtered_codes, 开始日期, target_date)

    候选列表 = []

    # 分批，每批 200 个代码（3000 ÷ 200 = 15 批）
    batch_size = 450
    batches = [filtered_codes[i:i + batch_size] for i in range(0, len(filtered_codes), batch_size)]

    # 使用 6 个进程（8 核留一些余量）
    with Pool(processes=6) as pool:
        tasks = [(batch, 日线数据, target_date) for batch in batches]
        results = pool.imap_unordered(process_stock_batch, tasks)

        # 最小化 tqdm 开销
        for batch_results in results:
            候选列表.extend(batch_results)

    if not 候选列表:
        logger.warning(f"{target_date} 无符合“连续下跌后止跌反转”的股票")
        return pd.DataFrame([])

    # 5. 优中选优：只保留前3只
    候选列表.sort(key=lambda x: x['量比'], reverse=True)
    最终前3只 = 候选列表[:3]

    最终选中_df = pd.DataFrame(最终前3只)

    logger.warning(f"{target_date} 最终选中 {len(最终前3只)} 只股票")
    入选名称 = 最终选中_df['stock_name'].tolist()
    logger.warning(f"入选股票：{' '.join(入选名称)}")

    return 最终选中_df[['ts_code', 'stock_name', 'trade_date', 'close']]


def buy(name, code, price, buy_date, close_price):
    # if code in account.holding_stocks:
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
        logger.info(f"{stock_name} 开盘跟昨日收盘偏离:{volatility}")
        # if volatility > 5:
        #     continue
        if volatility < -0.5:
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
            SELECT ts_code, trade_date, close_price AS close, stock_name, open_price AS open, previous_close AS pre_close, high_price AS high, low_price AS low, change_pct AS pct_chg
            FROM daily_quotes
            WHERE ts_code IN {common.stock_code_literals(selected_stocks)}
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
            # account.sell(stock_info['name'], ts_code, stock_now_date_df['close'], stock_info['lots'], now_date)
            # continue
            # if stock_now_date_df['pct_chg'] < 3:
            #     account.sell(stock_info['name'], ts_code, stock_now_date_df['close'], stock_info['lots'], now_date)
            #     continue
            # if stock_info['持股天数'] < 2 and _持仓最高回撤 < -3:
            #     account.sell(stock_info['name'], ts_code, stock_now_date_df['close'], stock_info['lots'], now_date)
            #     continue
            if _持仓最高回撤 < -1:
                account.sell(stock_info['name'], ts_code, stock_now_date_df['close'], stock_info['lots'], now_date)
                continue
            # if stock_info['持股天数'] >= 5:
            #     account.sell(stock_info['name'], ts_code, stock_now_date_df['close'], stock_info['lots'], now_date)
            #     continue

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

    return


def main(start_date, end_date):
    file_name = __file__.split(".py")[0].split("\\")[-1].split("/")[-1].split("/")[-1]
    common.process_for_strategy(start_date, end_date, process_daily, file_name)


if __name__ == "__main__":
    # main(start_date=int(datetime.now().strftime('%Y%m%d')), end_date=int(datetime.now().strftime('%Y%m%d')))
    main(start_date=20260720, end_date=int(datetime.now().strftime('%Y%m%d')))
