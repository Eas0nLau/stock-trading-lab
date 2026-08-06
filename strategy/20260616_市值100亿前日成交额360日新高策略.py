import sys
from pathlib import Path

import pandas as pd
from loguru import logger
from datetime import datetime, timedelta

项目根目录 = Path(__file__).resolve().parents[1]
sys.path.append(str(项目根目录))

from utils import db, common, account, ini_util

策略名称 = '20260616_市值100亿前日成交额360日新高策略'
市值阈值_亿元 = 100
市值阈值_万元 = 市值阈值_亿元 * 10000
成交额新高交易日数 = 360
额外比较交易日数 = 2
前日往前三日交易日数 = 3
最近无跌停交易日数 = 5
最近无连板交易日数 = 10
涨停涨幅阈值 = 9.5
跌停跌幅阈值 = -9.5
最大允许跌幅 = -5


def _提取整数股票代码集合(codes):
    if codes is None:
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


def _读取最新市值达标股票():
    result = db.mysql_localhost(
        sql="""
            SELECT MAX(trade_date) AS trade_date
            FROM daily_quotes
            WHERE total_mv IS NOT NULL
        """,
        fetch=True,
    )
    if not result or result[0]['trade_date'] is None:
        raise ValueError('未找到可用的 total_mv 市值数据')

    mv_date = int(result[0]['trade_date'])
    mv_df = pd.read_sql(
        f"""
            SELECT ts_code, total_mv
            FROM daily_quotes
            WHERE trade_date = {mv_date}
              AND total_mv IS NOT NULL
              AND total_mv > {市值阈值_万元}
        """,
        db.engine,
    )
    if mv_df.empty:
        raise ValueError(f'最新市值日期 {mv_date} 无市值>{市值阈值_亿元}亿股票')

    mv_df['ts_code'] = mv_df['ts_code'].map(common.normalize_symbol)
    mv_df['市值统计日期'] = mv_date
    return mv_df


def _读取日线数据(filtered_codes, trade_dates):
    trade_date_tuple = str(tuple(trade_dates)).replace(',)', ')')
    code_filter = ''
    codes = sorted(_提取整数股票代码集合(filtered_codes))
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
            sb.list_status,
            sb.name AS basic_name
        FROM daily_quotes sd
        LEFT JOIN securities sb ON SUBSTRING_INDEX(sd.ts_code, '.', 1) = sb.symbol
        WHERE sd.trade_date IN {trade_date_tuple}
          {code_filter}
          AND sb.market = '主板'
          AND sd.turnover IS NOT NULL
          AND sd.low_price IS NOT NULL
          AND sd.close_price IS NOT NULL
    """
    return pd.read_sql(query, db.engine)


def strategy(filtered_codes, target_date):
    """
    市值100亿前日成交额360日新高策略
    - 市值 > 100亿，使用数据库最新 total_mv 日期先筛出代码池。
    - 前日成交额是前日往前360个交易日内的新高。
    - 前日成交额 > 前日往前3个交易日成交额总和。
    - 前日成交额 > 昨日成交额。
    - 前日成交额 > 当日成交额。
    - 前日最低价 < 昨日收盘价。
    - 只保留主板股票。
    - 过滤当天涨停、跌停，以及当天跌幅大于5%的股票。
    - 当日最近5个交易日不能有跌停。
    - 爆量后的每日收盘价必须大于上一日最低价。
    - 最近10个交易日内不能出现连续2连板。
    """
    target_date = int(target_date)
    logger.warning(f"【{策略名称}】开始筛选 {target_date} ...")

    try:
        trade_dates = _最近交易日列表(target_date, 成交额新高交易日数 + 额外比较交易日数)
        市值_df = _读取最新市值达标股票()
    except ValueError as exc:
        logger.warning(f"{target_date} 数据不足：{exc}")
        return pd.DataFrame([])

    市值达标代码 = _提取整数股票代码集合(市值_df['ts_code'].tolist())
    股票池代码 = _提取整数股票代码集合(filtered_codes)
    最终候选池 = 市值达标代码 if not 股票池代码 else 市值达标代码 & 股票池代码
    if not 最终候选池:
        logger.warning(
            f"{target_date} 最新市值日期 {int(市值_df['市值统计日期'].iloc[0])} 无市值>{市值阈值_亿元}亿的候选股票"
        )
        return pd.DataFrame([])
    logger.info(
        f"{target_date} 使用最新市值日期 {int(市值_df['市值统计日期'].iloc[0])} 预筛市值>{市值阈值_亿元}亿股票 {len(最终候选池)} 只"
    )

    today = trade_dates[-1]
    yesterday = trade_dates[-2]
    pre_day = trade_dates[-3]
    amount_window_dates = trade_dates[:成交额新高交易日数]
    pre_day_prev3_dates = trade_dates[-6:-3]
    recent_5_dates = trade_dates[-最近无跌停交易日数:]
    recent_10_dates = trade_dates[-最近无连板交易日数:]
    日线数据 = _读取日线数据(最终候选池, trade_dates)
    if 日线数据.empty:
        logger.warning(f"{target_date} 无足够日线数据")
        return pd.DataFrame([])

    日线数据 = 日线数据.copy()
    日线数据['ts_code'] = 日线数据['ts_code'].map(common.normalize_symbol)
    日线数据['stock_name'] = 日线数据['stock_name'].fillna(日线数据['basic_name'])
    日线数据['是否涨停'] = (日线数据['pct_chg'] >= 涨停涨幅阈值) & (日线数据['close'] == 日线数据['high'])
    日线数据['是否跌停'] = (日线数据['pct_chg'] <= 跌停跌幅阈值) & (日线数据['close'] == 日线数据['low'])

    amount_window_df = 日线数据[日线数据['trade_date'].isin(amount_window_dates)].copy()
    amount_summary_df = (
        amount_window_df
        .groupby('ts_code')
        .agg(
            成交额窗口覆盖交易日数=('trade_date', 'nunique'),
            近360日最高成交额=('amount', 'max'),
        )
        .reset_index()
    )
    前日往前3日_df = (
        日线数据[日线数据['trade_date'].isin(pre_day_prev3_dates)]
        .groupby('ts_code')
        .agg(
            前日往前3日覆盖交易日数=('trade_date', 'nunique'),
            前日往前3日成交额总和=('amount', 'sum'),
        )
        .reset_index()
    )
    最近5日跌停_df = (
        日线数据[日线数据['trade_date'].isin(recent_5_dates)]
        .groupby('ts_code')
        .agg(
            最近5日覆盖交易日数=('trade_date', 'nunique'),
            最近5日跌停次数=('是否跌停', 'sum'),
        )
        .reset_index()
    )
    最近10日涨停_df = 日线数据[日线数据['trade_date'].isin(recent_10_dates)].sort_values(['ts_code', 'trade_date']).copy()
    最近10日涨停_df['前一交易日是否涨停'] = 最近10日涨停_df.groupby('ts_code')['是否涨停'].shift(1) == True
    最近10日涨停_df['是否2连板节点'] = 最近10日涨停_df['是否涨停'] & 最近10日涨停_df['前一交易日是否涨停']
    最近10日连板_df = (
        最近10日涨停_df
        .groupby('ts_code')
        .agg(
            最近10日覆盖交易日数=('trade_date', 'nunique'),
            近10日2连板次数=('是否2连板节点', 'sum'),
        )
        .reset_index()
    )
    前日_df = (
        日线数据[日线数据['trade_date'] == pre_day]
        [[
            'ts_code', 'stock_name', 'trade_date', 'open', 'high', 'low',
            'close', 'pre_close', 'amount', 'pct_chg', 'market',
        ]]
        .rename(columns={
            'trade_date': '前日日期',
            'open': '前日开盘价',
            'high': '前日最高价',
            'low': '前日最低价',
            'close': '前日收盘价',
            'pre_close': '前日前收盘价',
            'amount': '前日成交额',
            'pct_chg': '前日涨跌幅',
            'market': '市场',
        })
    )
    昨日_df = (
        日线数据[日线数据['trade_date'] == yesterday]
        [['ts_code', 'low', 'close', 'amount']]
        .rename(columns={
            'low': '昨日最低价',
            'close': '昨日收盘价',
            'amount': '昨日成交额',
        })
    )
    当日_df = (
        日线数据[日线数据['trade_date'] == today]
        [['ts_code', 'high', 'low', 'close', 'amount', 'pct_chg']]
        .rename(columns={
            'high': '当日最高价',
            'low': '当日最低价',
            'close': '当日收盘价',
            'amount': '当日成交额',
            'pct_chg': '当日涨跌幅',
        })
    )

    result_df = 前日_df.merge(昨日_df, on='ts_code', how='inner')
    result_df = result_df.merge(当日_df, on='ts_code', how='inner')
    result_df = result_df.merge(amount_summary_df, on='ts_code', how='left')
    result_df = result_df.merge(前日往前3日_df, on='ts_code', how='left')
    result_df = result_df.merge(最近5日跌停_df, on='ts_code', how='left')
    result_df = result_df.merge(最近10日连板_df, on='ts_code', how='left')
    result_df = result_df.merge(市值_df, on='ts_code', how='left')
    result_df['市值_亿元'] = result_df['total_mv'] / 10000
    result_df['当日涨停'] = (result_df['当日涨跌幅'] >= 涨停涨幅阈值) & (result_df['当日收盘价'] == result_df['当日最高价'])
    result_df['当日跌停'] = (result_df['当日涨跌幅'] <= 跌停跌幅阈值) & (result_df['当日收盘价'] == result_df['当日最低价'])
    result_df['爆量后昨日收盘高于前日低点'] = result_df['昨日收盘价'] > result_df['前日最低价']
    result_df['爆量后当日收盘高于昨日低点'] = result_df['当日收盘价'] > result_df['昨日最低价']

    selected_df = result_df[
        (result_df['成交额窗口覆盖交易日数'] == 成交额新高交易日数) &
        (result_df['前日成交额'] >= result_df['近360日最高成交额']) &
        (result_df['前日往前3日覆盖交易日数'] == 前日往前三日交易日数) &
        (result_df['前日成交额'] > result_df['前日往前3日成交额总和']) &
        (result_df['前日成交额'] > result_df['昨日成交额']) &
        (result_df['前日成交额'] > result_df['当日成交额']) &
        (result_df['前日最低价'] < result_df['昨日收盘价']) &
        (result_df['爆量后昨日收盘高于前日低点']) &
        (result_df['爆量后当日收盘高于昨日低点']) &
        (result_df['最近5日覆盖交易日数'] == 最近无跌停交易日数) &
        (result_df['最近5日跌停次数'] == 0) &
        (result_df['最近10日覆盖交易日数'] == 最近无连板交易日数) &
        (result_df['近10日2连板次数'] == 0) &
        (~result_df['当日涨停']) &
        (~result_df['当日跌停']) &
        (result_df['当日涨跌幅'] >= 最大允许跌幅)
    ].copy()

    if selected_df.empty:
        logger.warning(
            f"{target_date} 无符合“市值>{市值阈值_亿元}亿 + 前日成交额创{成交额新高交易日数}日新高 + "
            f"前日成交额>前3日总和/昨日/当日成交额 + 前日最低价<昨日收盘价 + "
            f"爆量后收盘价不跌破上一日低点 + 最近5日无跌停 + 近10日无2连板 + "
            f"主板 + 当日非涨跌停且跌幅不超过5%”的股票"
        )
        return pd.DataFrame([])

    selected_df = selected_df.sort_values(
        '市值_亿元',
        ascending=False,
        kind='mergesort',
    ).reset_index(drop=True)

    logger.warning(f"{target_date} 【{策略名称}】最终选中 {len(selected_df)} 只股票")
    logger.warning(f"入选股票：{' '.join(selected_df['stock_name'].astype(str).tolist())}")
    for _, row in selected_df.iterrows():
        logger.info(
            f"   → 候选 {row['stock_name']} | 前日:{int(row['前日日期'])} | "
            f"前日成交额:{row['前日成交额']:.2f} | 近360日最高成交额:{row['近360日最高成交额']:.2f} | "
            f"前3日成交额总和:{row['前日往前3日成交额总和']:.2f} | "
            f"最近5日跌停次数:{int(row['最近5日跌停次数'])} | 近10日2连板次数:{int(row['近10日2连板次数'])} | "
            f"昨日成交额:{row['昨日成交额']:.2f} | 当日成交额:{row['当日成交额']:.2f} | "
            f"当日涨跌幅:{row['当日涨跌幅']:.2f}% | "
            f"昨日收盘>前日低点:{row['爆量后昨日收盘高于前日低点']} | "
            f"当日收盘>昨日低点:{row['爆量后当日收盘高于昨日低点']} | "
            f"前日最低价:{row['前日最低价']:.2f} | 昨日收盘价:{row['昨日收盘价']:.2f} | "
            f"市值:{row['市值_亿元']:.2f}亿 | 市场:{row['市场']}"
        )

    return selected_df[[
        'ts_code', 'stock_name', '市场',
        '前日日期', '前日开盘价', '前日最高价', '前日最低价', '前日收盘价', '前日成交额',
        '昨日最低价', '昨日收盘价', '昨日成交额',
        '当日最高价', '当日最低价', '当日收盘价', '当日成交额', '当日涨跌幅',
        '爆量后昨日收盘高于前日低点', '爆量后当日收盘高于昨日低点',
        '近360日最高成交额', '成交额窗口覆盖交易日数',
        '前日往前3日成交额总和', '前日往前3日覆盖交易日数',
        '最近5日跌停次数', '最近5日覆盖交易日数',
        '近10日2连板次数', '最近10日覆盖交易日数',
        '市值_亿元', '市值统计日期',
    ]]




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
        open_volatility = (open_price - pre_close) / pre_close * 100
        logger.info(f"{stock_name} 开盘跟昨日收盘偏离:{open_volatility}")
        # if open_volatility > 5:
        #     continue
        if open_volatility < -3:
            continue
        buy_price = open_price
        # stock_5_min_k_data = _2_分时数据获取_5分k.get_data(start_date=stock_name_buy_date, end_date=stock_name_buy_date,
        #                                                    stock=symbol_ts_code_dict[ts_code])
        # if len(stock_5_min_k_data) == 0:
        #     logger.error(f"{stock_name} 五分k数据为空，异常")
        #     exit()
        # 判断前几跟五分k是否为正
        # volatility = (float(stock_5_min_k_data[0][1]) - float(stock_5_min_k_data[0][0])) / float(
        #     stock_5_min_k_data[0][0]) * 100
        # logger.warning(f"{stock_name} 开盘5分钟后五分k偏离为:{volatility}")
        # if volatility < 0:
        #     continue
        # buy_price = float(stock_5_min_k_data[0][1])
        if open_price == close_price == high_price == low_price:
            # logger.error(f"{stock_name} {stock_name_buy_date} 一字板涨停 买不进 跳过")
            continue
        else:
            buy_date_yield_rate = (close_price - buy_price) / buy_price * 100
            buy_status = buy(stock_name, ts_code, price=buy_price, buy_date=buy_date, close_price=close_price)
            if buy_status:
                logger.warning(
                    f"{stock_name} {stock_name_buy_date} 以开盘价 {buy_price} 买入，当天收盘收益率：{buy_date_yield_rate:.2f}%")
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
    # main(start_date=20200101, end_date=int(20260616))
    # main(start_date=20260501, end_date=int(20260616))
    main(start_date=int(datetime.now().strftime('%Y%m%d')), end_date=int(datetime.now().strftime('%Y%m%d')))
