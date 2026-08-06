import math
from datetime import datetime, timedelta

import pandas as pd
from loguru import logger

from utils import db, common
from stock_lab.modules.market_data.helpers import normalize_ts_code

# 初始金额
init_amount = float(1000000)
profit_loss = float(0)
# 最小可用金额
min_available_amount = init_amount
# 最大持仓个股数量
max_holding_stock_count = 0
# 可用金额
available_amount = init_amount
# 市值
market_value = 0
market_max_value = 0
# 持仓
holding_stocks = {}

# 下一日预选买入池
next_date_pre_selection_stocks = {
    'selected_stocks': None,
    'target_date': None,
}


def print_account_info():
    global holding_stocks, available_amount, market_value, market_max_value, min_available_amount, max_holding_stock_count, profit_loss

    _盈亏 = (available_amount + market_value) - init_amount
    profit_loss = ((available_amount + market_value) - init_amount) / init_amount * 100
    _最大使用金额 = market_max_value
    if market_value > market_max_value:
        market_max_value = market_value
    if _最大使用金额 == 0:
        _最大使用金额盈亏比 = 0
    else:
        _最大使用金额盈亏比 = ((_最大使用金额 + _盈亏) - _最大使用金额) / _最大使用金额 * 100

    logger.warning(f"持仓明细：")
    # 按盈亏比从小到大排序
    sorted_stocks = sorted(holding_stocks.items(), key=lambda x: x[1]['盈亏比'])
    max_holding_stock_count_ = 0
    for code, stock in sorted_stocks:
        if stock['lots'] > 0:
            max_holding_stock_count_ += 1
        logger.warning(
            f"盈亏比：{stock['盈亏比']:.2f}% 盈亏：{stock['盈亏']} {stock['name']} {code} "
            f"持仓：{stock['lots']}股 持股天数：{stock['持股天数']} "
            f"最高市值：{stock['持仓最高市值']} 最高回撤：{round(stock['持仓最高回撤'], 2):.2f}% "
            f"市值：{stock['market_value']} 成本价：{stock['成本价']} "
            f"买入日期：{stock['买入日期']} 卖出日期：{stock['卖出日期']} 是否发生除权：{stock['是否发生除权']}")
    if max_holding_stock_count_ > max_holding_stock_count:
        max_holding_stock_count = max_holding_stock_count_
    logger.warning(f"账号可用金额：{available_amount} 持仓市值：{market_value} 总资产：{available_amount + market_value} "
                   f"总盈亏比：{profit_loss:.2f}% 总盈亏：{_盈亏} "
                   f"最大使用金额：{market_max_value} 最大使用金额盈亏比：{_最大使用金额盈亏比:.2f}%")
    logger.warning(f"最大持仓个股数量：{max_holding_stock_count} 当前持仓数量：{max_holding_stock_count_}")
    pass


def sync_open_market_before(now_date):
    """同步开盘操作前市值"""
    global holding_stocks, market_value, available_amount
    # logger.warning(f"同步开盘操作前市值 开始")
    selected_stocks = holding_stocks.keys()
    if selected_stocks:
        query = f"""
            SELECT ts_code, trade_date, close_price AS close, stock_name, open_price AS open,
                   previous_close AS pre_close, high_price AS high, low_price AS low
            FROM daily_quotes
            WHERE ts_code IN {str(tuple([normalize_ts_code(i) for i in selected_stocks])).replace(",)", ")")}
            AND trade_date = {now_date}
        """
        range_data = pd.read_sql(query, db.engine)
        for ts_code in selected_stocks:
            stock_info = holding_stocks[ts_code]
            ts_code_df = range_data[range_data['ts_code'] == ts_code]
            if ts_code_df.empty:
                logger.error(f"{ts_code} {now_date} 当日数据为空。")
                continue
            if stock_info['lots'] == 0:
                # logger.error(f"{ts_code} {stock_info['name']} 已卖出")
                continue
            # logger.info(ts_code)
            # try:
            # 判断是否发生“除权”
            if holding_stocks[ts_code]['close_price'] != ts_code_df.iloc[0]['pre_close']:
                # 发生除权，当没买过
                logger.error(f"{ts_code} 发生除权，当没买过")
                # 同步账户总市值
                available_amount += holding_stocks[ts_code]['成本价']
                market_value -= holding_stocks[ts_code]['market_value']
                holding_stocks[ts_code]['lots'] = 0
                holding_stocks[ts_code]['market_value'] = 0
                holding_stocks[ts_code]['盈亏比'] = 0
                holding_stocks[ts_code]['盈亏'] = 0
                holding_stocks[ts_code]['卖出日期'] = now_date
                holding_stocks[ts_code]['是否发生除权'] = "是"
                continue
            # except Exception as e:
            #     pass
            # 计算盈亏比
            _成本价 = holding_stocks[ts_code]['成本价']
            open_price = ts_code_df.iloc[0]['open']
            # 当前持有股数
            lots = holding_stocks[ts_code]['lots']
            # 最新市值
            price = round(open_price * lots, 3)
            # 同步账户总市值
            market_value -= holding_stocks[ts_code]['market_value']
            market_value += price
            if price != holding_stocks[ts_code]['market_value']:
                if holding_stocks[ts_code]['持仓最高市值'] < price:
                    holding_stocks[ts_code]['持仓最高市值'] = price
                _持仓最高回撤 = (price - holding_stocks[ts_code]['持仓最高市值']) / holding_stocks[ts_code]['持仓最高市值'] * 100
                holding_stocks[ts_code]['持仓最高回撤'] = _持仓最高回撤
            holding_stocks[ts_code]['market_value'] = price
            holding_stocks[ts_code]['持股天数'] += 1
            _盈亏比 = (price - _成本价) / _成本价 * 100
            holding_stocks[ts_code]['盈亏比'] = _盈亏比
            holding_stocks[ts_code]['盈亏'] = price - _成本价
    # logger.warning(f"同步开盘操作前市值 完成")
    # print_account_info()
    pass


def sync_close_market(now_date):
    """同步收盘市值"""
    global holding_stocks, market_value
    # logger.warning(f"同步收盘市值 开始")
    selected_stocks = holding_stocks.keys()
    if selected_stocks:
        query = f"""
            SELECT ts_code, trade_date, close_price AS close, stock_name, open_price AS open,
                   previous_close AS pre_close, high_price AS high, low_price AS low
            FROM daily_quotes
            WHERE ts_code IN {str(tuple([normalize_ts_code(i) for i in selected_stocks])).replace(",)", ")")}
            AND trade_date = {now_date}
        """
        range_data = pd.read_sql(query, db.engine)
        for ts_code in selected_stocks:
            stock_info = holding_stocks[ts_code]
            ts_code_df = range_data[range_data['ts_code'] == ts_code]
            if ts_code_df.empty:
                logger.error(f"{ts_code} {now_date} 当日数据为空。")
                continue
            if stock_info['lots'] == 0:
                # logger.error(f"{ts_code} {stock_info['name']} 已卖出")
                continue
            # 计算盈亏比
            _成本价 = holding_stocks[ts_code]['成本价']
            close_price = ts_code_df.iloc[0]['close']
            # 当前持有股数
            lots = holding_stocks[ts_code]['lots']
            # 最新市值
            price = round(close_price * lots, 3)
            # 同步账户总市值
            market_value -= holding_stocks[ts_code]['market_value']
            market_value += price
            if price != holding_stocks[ts_code]['market_value']:
                if holding_stocks[ts_code]['持仓最高市值'] < price:
                    holding_stocks[ts_code]['持仓最高市值'] = price
                _持仓最高回撤 = (price - holding_stocks[ts_code]['持仓最高市值']) / holding_stocks[ts_code]['持仓最高市值'] * 100
                holding_stocks[ts_code]['持仓最高回撤'] = _持仓最高回撤
            holding_stocks[ts_code]['market_value'] = price
            _盈亏比 = (price - _成本价) / _成本价 * 100
            holding_stocks[ts_code]['盈亏比'] = _盈亏比
            holding_stocks[ts_code]['盈亏'] = price - _成本价
            holding_stocks[ts_code]['close_price'] = close_price
    # logger.warning(f"同步收盘市值 完成")
    # print_account_info()
    pass


def simulated_sell(sell_out_fall_threshold=None,
                   sell_out_rise_threshold=None,
                   sell_out_盈利回撤_threshold=-5,
                   now_date=None):
    """开盘看看有没有符合卖出逻辑的进行卖出"""
    pass
    global holding_stocks, market_value
    logger.warning(
        f"开盘看看有没有符合卖出逻辑的进行卖出 开始 止损阈值:{sell_out_fall_threshold},止盈阈值:{sell_out_rise_threshold}")
    selected_stocks = holding_stocks.keys()
    if selected_stocks:
        range_date = (datetime.strptime(str(now_date), "%Y%m%d") - timedelta(days=15)).strftime('%Y%m%d')  # 缓冲 30 天
        query = f"""
            SELECT ts_code, trade_date, close_price AS close, stock_name, open_price AS open,
                   previous_close AS pre_close, high_price AS high, low_price AS low,
                   change_pct AS pct_chg
            FROM daily_quotes
            WHERE ts_code IN {str(tuple([normalize_ts_code(i) for i in selected_stocks])).replace(",)", ")")}
            AND trade_date >= {range_date}
            AND trade_date <= {now_date}
            order by trade_date
        """
        range_data = pd.read_sql(query, db.engine)
        for ts_code in selected_stocks:
            stock_info = holding_stocks[ts_code]
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

            # 昨日收益率达到止损率卖出
            # if stock_pre_date_df['pct_chg'] < sell_out_fall_threshold:
            #     logger.error(f"{ts_code} 昨日收益为负卖出 昨日收益率：{stock_pre_date_df['pct_chg']:.2f}%")
            #     sell(stock_info['name'], ts_code, stock_now_date_df['open'], stock_info['lots'], now_date)
            #     continue
            # 持仓收益率达到止损率卖出
            _盈亏比 = stock_info['盈亏比']
            _盈亏 = stock_info['盈亏']
            # if _盈亏比 < sell_out_fall_threshold:
            #     logger.error(f"{ts_code} 持仓收益为负卖出 达到阈值 盈亏比：{_盈亏比:.2f}% 盈亏：{_盈亏} 持仓最高回撤：{_持仓最高回撤:.2f}% 持仓最高市值：{_持仓最高市值}")
            #     sell(stock_info['name'], ts_code, stock_now_date_df['open'], stock_info['lots'], now_date)
            #     continue
            # if _盈亏比 > 0 and _持仓最高回撤 < sell_out_盈利回撤_threshold:
            #     logger.error(
            #         f"{ts_code} 持仓最高回撤 达到阈值 卖出 盈亏比：{_盈亏比:.2f}% 盈亏：{_盈亏} 持仓最高回撤：{_持仓最高回撤:.2f}% 持仓最高市值：{_持仓最高市值}")
            #     sell(stock_info['name'], ts_code, stock_now_date_df['open'], stock_info['lots'], now_date)
            #     continue

            # 达到止盈比例卖出
            # if _盈亏比 > sell_out_rise_threshold:
            #     logger.error(f"{ts_code} 达到止盈比例卖出 盈亏比：{_盈亏比:.2f}% 盈亏：{_盈亏} 持仓最高回撤：{_持仓最高回撤:.2f}% 持仓最高市值：{_持仓最高市值}")
            #     sell(stock_info['name'], ts_code, stock_now_date_df['open'], stock_info['lots'], now_date)
            #     continue
            if _持仓最高回撤 < -3:
                sell(stock_info['name'], ts_code, stock_now_date_df['open'], stock_info['lots'], now_date)
                continue

    logger.warning(f"开盘看看有没有符合卖出逻辑的进行卖出 完成")
    # print_account_info()


def simulated_buy():
    global next_date_pre_selection_stocks
    selected_stocks = next_date_pre_selection_stocks['selected_stocks']
    target_date = next_date_pre_selection_stocks['target_date']
    if selected_stocks is None or target_date is None:
        logger.error("下一日预选买入池 为空")
        return
    if common.check_指数开盘(target_date):
        return

    range_date = (datetime.strptime(str(target_date), "%Y%m%d") + timedelta(days=15)).strftime('%Y%m%d')
    stock_name_list = selected_stocks['stock_name'].tolist()
    # 批量查询下一交易日数据
    query = f"""
        SELECT ts_code, trade_date, close_price AS close, stock_name, open_price AS open,
               previous_close AS pre_close, high_price AS high, low_price AS low
        FROM daily_quotes
        WHERE ts_code IN {str(tuple([normalize_ts_code(i) for i in selected_stocks['ts_code'].tolist()])).replace(",)", ")")}
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
        next_date_pre_selection_stocks = {
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
        if volatility < -5 or volatility > 5:
            logger.error(f"{stock_name} 开盘跟昨日收盘偏离:{volatility} 不买")
            continue
        target_date_high = stock_name_df[stock_name_df['trade_date'] == target_date].iloc[0]['high']
        if target_date_high > open_price:
            logger.error(f"{stock_name} 未开在昨日最高点之上不买")
            continue
        is_一字板涨停 = False
        if open_price == close_price == high_price == low_price:
            is_一字板涨停 = True
            logger.error(f"{stock_name} {stock_name_buy_date} 一字板涨停 买不进 跳过")
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
    next_date_pre_selection_stocks = {
        'selected_stocks': None,
        'target_date': None,
    }


def add_next_date_stocks(selected_stocks, target_date):
    global next_date_pre_selection_stocks
    next_date_pre_selection_stocks['selected_stocks'] = selected_stocks
    next_date_pre_selection_stocks['target_date'] = target_date
    pass


def sell(name, code, price, lots, now_date):
    global available_amount, market_value
    sell_price = round(price * lots, 3)
    logger.warning(f"{name} {code} 股价：{price} 卖出：{lots}股 卖出金额：{sell_price} 尝试卖出，"
                   f"卖出前 市值：{market_value} 可用金额：{available_amount} ")
    available_amount = available_amount + sell_price
    market_value -= sell_price
    logger.warning(f"{name} {code} 股价：{price} 卖出：{lots}股 卖出金额：{sell_price} 卖出成功，"
                   f"卖出后 市值：{market_value} 可用金额：{available_amount}")
    # 原始每股成本
    原始每股成本 = holding_stocks[code]['成本价'] / holding_stocks[code]['lots']

    holding_stocks[code]['lots'] -= lots
    holding_stocks[code]['market_value'] -= sell_price
    if holding_stocks[code]['lots'] == 0:
        _成本价 = holding_stocks[code]['成本价']
        _盈亏比 = (sell_price - _成本价) / _成本价 * 100
        holding_stocks[code]['盈亏比'] = _盈亏比
        holding_stocks[code]['盈亏'] = sell_price - _成本价
    else:
        holding_stocks[code]['持仓最高市值'] -= sell_price
        holding_stocks[code]['成本价'] = holding_stocks[code]['lots'] * 原始每股成本
        _成本价 = holding_stocks[code]['成本价']
        _盈亏比 = (holding_stocks[code]['market_value'] - _成本价) / _成本价 * 100
        holding_stocks[code]['盈亏比'] = _盈亏比
        holding_stocks[code]['盈亏'] = holding_stocks[code]['market_value'] - _成本价
    holding_stocks[code]['卖出日期'] = now_date
    return True


def buy(name, code, price, buy_date, close_price):
    global available_amount, market_value, min_available_amount
    # if code in holding_stocks:
    #     logger.error(f"{name} {code} 买过了，不买了。")
    #     return False
    if code in holding_stocks and holding_stocks[code]['lots'] > 0:
        logger.error(f"{name} {code} 买有了，不买了。")
        return False
    lots = 计算最大可买手数(price)
    if lots == 0:
        logger.error(f"{name} {code} 最大可买手数为:{lots}，不买了。")
        return False

    buy_price = round(price * lots, 3)
    logger.warning(f"{name} {code} 股价：{price} 买入：{lots}股 买入金额：{buy_price} 尝试买入，"
                   f"买入前 市值：{market_value} 可用金额：{available_amount} ")
    if buy_price > available_amount:
        logger.error(f"买入失败，可用金额不足：{available_amount}")
        return False
    available_amount = available_amount - buy_price
    market_value += buy_price
    if min_available_amount >= available_amount:
        min_available_amount = available_amount
    logger.warning(f"{name} {code} 股价：{price} 买入：{lots}股 买入金额：{buy_price} 买入成功，"
                   f"买入后 市值：{market_value} 可用金额：{available_amount}")

    holding_stocks[code] = {
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


def 计算最大可买手数(price, price_max=20000, min_multiple=100):
    """
    计算 price 的多少倍（从 min_multiple 开始）才能达到或超过 price_max

    参数:
        price (float/int): 当前价格
        price_max (float/int): 目标值（默认 5000）
        min_multiple (int): 起始倍数（默认 100）

    返回:
        int: 所需的倍数
    """
    if price <= 0:
        return 0  # 避免除以零或负数

    required_multiple = math.floor(price_max / (price * min_multiple))
    return required_multiple * min_multiple
