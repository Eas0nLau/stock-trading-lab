import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.append(os.pardir)

from utils import db, common, account, ini_util
from task import _2_分时数据获取_5分k
symbol_ts_code_dict = common.load_stock_symbol_ts_code_dict()


量窒息周期天数 = 3
量窒息统计交易日数 = 20
量窒息排名阈值 = 3
近5日成交量排名阈值 = 2
振幅统计交易日数 = 3
振幅阈值 = 8.5
开收偏离统计交易日数 = 2
开收偏离阈值 = 3
五日线天数 = 5
五日线统计交易日数 = 15
五日线排名阈值 = 3
均线天数 = 20
前期龙头窗口天数 = 180
连板天数 = 3
涨停涨幅阈值 = 9.5
连续一字板天数阈值 = 2
跌停跌幅阈值 = -9.5
龙虎榜上榜次数阈值 = 10


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

    return set(codes_series.map(common.normalize_ts_code).tolist())


def _生成每日入选股票ini(选中_df, target_date):
    if 选中_df.empty:
        return None

    output_dir = Path(__file__).resolve().parents[1] / 'output' / '20260609_龙头缩量收红策略' / str(target_date)
    stock_items = [(row['ts_code'], row['stock_name']) for _, row in 选中_df.iterrows()]
    ini_path = ini_util.write_ini_list(stock_items, output_dir, f"{len(stock_items)}_全部.ini")

    logger.warning(f"{target_date} 入选股票ini文件生成完成：{ini_path}")
    return ini_path


def _近3个月有过3连板(单股数据, target_date):
    target_date_obj = datetime.strptime(str(target_date), "%Y%m%d")
    前期龙头起始日期 = int((target_date_obj - timedelta(days=前期龙头窗口天数)).strftime("%Y%m%d"))
    连板窗口数据 = 单股数据[
        (单股数据['trade_date'] >= 前期龙头起始日期) &
        (单股数据['trade_date'] <= target_date)
    ]
    if len(连板窗口数据) < 连板天数:
        return False

    连续涨停天数 = 0
    for _, row in 连板窗口数据.iterrows():
        if row['pct_chg'] >= 涨停涨幅阈值 and row['close'] == row['high']:
            连续涨停天数 += 1
            if 连续涨停天数 >= 连板天数:
                return True
        else:
            连续涨停天数 = 0

    return False


def _近3个月存在连续2天一字涨跌停(单股数据, target_date):
    target_date_obj = datetime.strptime(str(target_date), "%Y%m%d")
    风险窗口起始日期 = int((target_date_obj - timedelta(days=前期龙头窗口天数)).strftime("%Y%m%d"))
    风险窗口数据 = 单股数据[
        (单股数据['trade_date'] >= 风险窗口起始日期) &
        (单股数据['trade_date'] <= target_date)
    ]

    连续一字板天数 = 0
    for _, row in 风险窗口数据.iterrows():
        是否一字板 = row['open'] == row['close'] == row['high'] == row['low']
        是否一字涨停 = 是否一字板 and row['pct_chg'] >= 涨停涨幅阈值
        是否一字跌停 = 是否一字板 and row['pct_chg'] <= 跌停跌幅阈值
        if 是否一字涨停 or 是否一字跌停:
            连续一字板天数 += 1
            if 连续一字板天数 >= 连续一字板天数阈值:
                return True
        else:
            连续一字板天数 = 0

    return False


def _加载龙虎榜上榜次数(股票代码列表, target_date):
    if not 股票代码列表:
        return {}

    target_date_obj = datetime.strptime(str(target_date), "%Y%m%d")
    龙虎榜起始日期 = int((target_date_obj - timedelta(days=前期龙头窗口天数)).strftime("%Y%m%d"))
    code_clause, code_params = common.stock_code_filter(股票代码列表, "stock_code")
    query = f"""
        SELECT `stock_code` AS `股票代码`, COUNT(*) AS `龙虎榜上榜次数`
        FROM `dragon_tiger`
        WHERE `trade_date` >= %s
          AND `trade_date` <= %s
          AND {code_clause}
        GROUP BY `stock_code`
    """
    龙虎榜次数_df = db.read_sql(query, (龙虎榜起始日期, int(target_date), *code_params))
    if 龙虎榜次数_df.empty:
        return {}

    龙虎榜次数_df['股票代码'] = 龙虎榜次数_df['股票代码'].map(common.normalize_ts_code)
    return 龙虎榜次数_df.set_index('股票代码')['龙虎榜上榜次数'].astype(int).to_dict()


def _最近3日振幅都较小(单股数据, 当天索引):
    if 当天索引 < 振幅统计交易日数 - 1:
        return False

    最近3日数据 = 单股数据.iloc[当天索引 - 振幅统计交易日数 + 1:当天索引 + 1].copy()
    最近3日数据['振幅'] = (最近3日数据['high'] - 最近3日数据['low']) / 最近3日数据['pre_close'] * 100

    return bool((最近3日数据['振幅'] < 振幅阈值).all())


def _连续2日开收偏离不大(单股数据, 当天索引):
    if 当天索引 < 开收偏离统计交易日数 - 1:
        return None

    最近2日数据 = 单股数据.iloc[当天索引 - 开收偏离统计交易日数 + 1:当天索引 + 1].copy()
    if (最近2日数据['open'] <= 0).any():
        return None

    最近2日数据['开收偏离'] = (最近2日数据['close'] - 最近2日数据['open']).abs() / 最近2日数据['open'] * 100
    最大开收偏离 = float(最近2日数据['开收偏离'].max())
    if 最大开收偏离 > 开收偏离阈值:
        return None

    return 最大开收偏离


def _五日线处于15日内前3低位(单股数据, 当天索引):
    需要数据天数 = 五日线天数 + 五日线统计交易日数 - 1
    if 当天索引 < 需要数据天数 - 1:
        return None

    均线计算窗口 = 单股数据.iloc[当天索引 - 需要数据天数 + 1:当天索引 + 1].copy()
    均线计算窗口['5日线'] = 均线计算窗口['close'].rolling(五日线天数).mean()
    近15日五日线 = 均线计算窗口['5日线'].dropna().tail(五日线统计交易日数)
    if len(近15日五日线) < 五日线统计交易日数:
        return None

    当前五日线 = float(近15日五日线.iloc[-1])
    当前五日线排名 = int(近15日五日线.rank(method='min').iloc[-1])
    if 当前五日线排名 > 五日线排名阈值:
        return None

    return {
        '5日线': 当前五日线,
        '5日线15日排名': 当前五日线排名,
    }


def _近5日成交量排名(单股数据, 当天索引):
    if 当天索引 < 4:
        return None

    近5日数据 = 单股数据.iloc[当天索引 - 4:当天索引 + 1]
    return int(近5日数据['vol'].rank(method='min').iloc[-1])


def _量窒息收红(单股数据, 当天索引):
    if 当天索引 < 量窒息统计交易日数 - 1:
        return None

    量窒息窗口数据 = 单股数据.iloc[当天索引 - 量窒息统计交易日数 + 1:当天索引 + 1].copy()
    当天数据 = 量窒息窗口数据.iloc[-1]
    if 当天数据['close'] <= 当天数据['open']:
        return None

    量窒息窗口数据['3日周期量'] = 量窒息窗口数据['vol'].rolling(量窒息周期天数).sum()
    有效3日周期量 = 量窒息窗口数据['3日周期量'].dropna()
    if len(有效3日周期量) < 量窒息排名阈值:
        return None

    当前3日周期量 = 量窒息窗口数据.iloc[-1]['3日周期量']
    当前3日周期量排名 = int(有效3日周期量.rank(method='min').iloc[-1])
    if 当前3日周期量排名 > 量窒息排名阈值:
        return None

    当日单日量排名 = int(量窒息窗口数据['vol'].rank(method='min').iloc[-1])
    return {
        '3日周期量': float(当前3日周期量),
        '3日周期量排名': 当前3日周期量排名,
        '当日单日量排名': 当日单日量排名,
    }


def strategy(filtered_codes, target_date):
    """
    量窒息收红前期龙头策略
    - 量窒息收红：近3日成交量合计在近1个月所有3日周期量中排名前3小，且当天收红
    - 当日成交量在近5个交易日内排名前2小
    - 连续3日每日振幅都小于8.5%
    - 连续2日每日开盘价和收盘价偏离绝对值不大于配置阈值
    - 当天5日线处于近15个交易日5日线的前3低位
    - 股价小于20日线
    - 前期龙头：近3个月有过3连板以上
    - 近3个月不存在连续2天一字涨停或一字跌停
    - 近90天龙虎榜上榜次数大于配置阈值
    - 剔除ST和*ST
    """
    target_date = int(target_date)
    logger.warning(f"【量窒息收红前期龙头策略】开始筛选 {target_date} ...")

    当前日期对象 = datetime.strptime(str(target_date), "%Y%m%d")
    最终候选池 = sorted(_提取整数股票代码集合(filtered_codes))

    if not 最终候选池:
        logger.warning(f"{target_date} 无可用候选股票池")
        return pd.DataFrame([])

    龙虎榜上榜次数 = _加载龙虎榜上榜次数(最终候选池, target_date)
    最终候选池 = [
        code for code in 最终候选池
        if int(龙虎榜上榜次数.get(common.normalize_ts_code(code), 0)) > 龙虎榜上榜次数阈值
    ]
    if not 最终候选池:
        logger.warning(f"{target_date} 无近90天龙虎榜上榜次数大于{龙虎榜上榜次数阈值}的股票")
        return pd.DataFrame([])

    # 取足够自然日，覆盖近3个月连板判断和20日均线计算。
    开始日期 = (当前日期对象 - timedelta(days=120)).strftime('%Y%m%d')
    日线数据 = common.load_daily_quotes_data(最终候选池, 开始日期, target_date)

    if 日线数据.empty:
        logger.warning(f"{target_date} 无足够日线数据")
        return pd.DataFrame([])

    候选列表 = []
    for ts_code in 最终候选池:
        股票代码文本 = str(ts_code).zfill(6)
        if 股票代码文本[:2] in ['92', '68', '30']:
            continue

        股票龙虎榜上榜次数 = int(龙虎榜上榜次数.get(common.normalize_ts_code(ts_code), 0))

        单股数据 = 日线数据[日线数据['ts_code'] == ts_code].sort_values('trade_date').reset_index(drop=True).copy()
        if len(单股数据) < 均线天数:
            continue

        当天索引 = 单股数据[单股数据['trade_date'] == target_date].index
        if len(当天索引) == 0:
            continue

        当天索引 = 当天索引[0]
        if 当天索引 < 均线天数 - 1:
            continue

        均线窗口数据 = 单股数据.iloc[当天索引 - 均线天数 + 1:当天索引 + 1]
        当天数据 = 均线窗口数据.iloc[-1]
        股票名称 = str(当天数据.get('stock_name', f"未知{ts_code}"))

        if 'ST' in 股票名称.upper():
            continue
        if '退市' in 股票名称.upper():
            continue

        if _近3个月存在连续2天一字涨跌停(单股数据, target_date):
            continue

        # if not _近3个月有过3连板(单股数据, target_date):
        #     continue

        量窒息数据 = _量窒息收红(单股数据, 当天索引)
        if 量窒息数据 is None:
            continue

        近5日量排名 = _近5日成交量排名(单股数据, 当天索引)
        if 近5日量排名 is None or 近5日量排名 > 近5日成交量排名阈值:
            continue

        # if not _最近3日振幅都较小(单股数据, 当天索引):
        #     continue

        最大开收偏离 = _连续2日开收偏离不大(单股数据, 当天索引)
        if 最大开收偏离 is None:
            continue

        五日线数据 = _五日线处于15日内前3低位(单股数据, 当天索引)
        if 五日线数据 is None:
            continue

        二十日线 = 均线窗口数据['close'].mean()
        if 当天数据['close'] >= 二十日线:
            continue

        候选列表.append({
            'ts_code': common.normalize_symbol(ts_code),
            'stock_name': 股票名称,
            'trade_date': target_date,
            'close': float(当天数据['close']),
            'pct_chg': float(当天数据['pct_chg']),
            '当日成交量': float(当天数据['vol']),
            '3日周期量': 量窒息数据['3日周期量'],
            '3日周期量排名': 量窒息数据['3日周期量排名'],
            '当日单日量排名': 量窒息数据['当日单日量排名'],
            '近5日成交量排名': 近5日量排名,
            '近2日最大开收偏离': 最大开收偏离,
            '5日线': 五日线数据['5日线'],
            '5日线15日排名': 五日线数据['5日线15日排名'],
            '20日线': float(二十日线),
            '近3个月有过3连板': True,
            '龙虎榜上榜次数': 股票龙虎榜上榜次数,
        })

        logger.info(
            f"   → 候选 {股票名称} | 当天涨幅:{当天数据['pct_chg']:.2f}% | "
            f"成交量:{当天数据['vol']:.2f} | 3日周期量:{量窒息数据['3日周期量']:.2f} | "
            f"3日周期量排名:{量窒息数据['3日周期量排名']} | "
            f"当日单日量排名:{量窒息数据['当日单日量排名']} | 近5日量排名:{近5日量排名} | "
            f"近2日最大开收偏离:{最大开收偏离:.2f}% | "
            f"5日线:{五日线数据['5日线']:.2f} | 5日线15日排名:{五日线数据['5日线15日排名']} | "
            f"龙虎榜上榜次数:{股票龙虎榜上榜次数} | 20日线:{二十日线:.2f}"
        )

    if not 候选列表:
        logger.warning(f"{target_date} 无符合“量窒息收红 + 5日量前2小 + 3日小振幅 + 2日开收偏离<={开收偏离阈值}% + 5日线15日前3低 + 价低于20日线 + 前期龙头 + 龙虎榜次数>{龙虎榜上榜次数阈值} + 无连续2天一字涨跌停”的股票")
        return pd.DataFrame([])

    候选列表.sort(key=lambda x: x['龙虎榜上榜次数'], reverse=True)
    最终选中_df = pd.DataFrame(候选列表)

    logger.warning(f"{target_date} 【量窒息收红前期龙头策略】最终选中 {len(最终选中_df)} 只股票")
    入选名称 = 最终选中_df['stock_name'].tolist()
    logger.warning(f"入选股票：{' '.join(入选名称)}")
    _生成每日入选股票ini(最终选中_df, target_date)

    return 最终选中_df[['ts_code', 'stock_name', 'trade_date', 'close', '龙虎榜上榜次数', '近5日成交量排名', '近2日最大开收偏离', '5日线', '5日线15日排名']]


def buy(name, code, price, buy_date, close_price):
    # if code in account.holding_stocks:
    #     logger.error(f"{name} {code} 买过了，不买了。")
    #     return False
    if code in account.holding_stocks and account.holding_stocks[code]['lots'] > 0:
        logger.error(f"{name} {code} 买有了，不买了。")
        return False
    price_max = (account.available_amount + account.market_value) / 10
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
        if open_volatility < 0.5:
            continue
        buy_price = open_price
        stock_5_min_k_data = _2_分时数据获取_5分k.get_data(start_date=stock_name_buy_date, end_date=stock_name_buy_date,
                                                           stock=symbol_ts_code_dict[ts_code])
        if len(stock_5_min_k_data) == 0:
            logger.error(f"{stock_name} 五分k数据为空，异常")
            exit()
        # 判断前几跟五分k是否为正
        volatility = (float(stock_5_min_k_data[0][1]) - float(stock_5_min_k_data[0][0])) / float(
            stock_5_min_k_data[0][0]) * 100
        logger.warning(f"{stock_name} 开盘5分钟后五分k偏离为:{volatility}")
        if volatility < 0:
            continue
        buy_price = float(stock_5_min_k_data[0][1])
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
    # main(start_date=20260701, end_date=int(datetime.now().strftime('%Y%m%d')))
    main(start_date=20260601, end_date=20260701)
    # main(start_date=20260529, end_date=20260529)
    # main(start_date=20260101, end_date=20260610)
    # main(start_date=20260101, end_date=20260609)
    # main(start_date=20150101, end_date=20260101)
