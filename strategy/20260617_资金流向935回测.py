import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
from loguru import logger

项目根目录 = Path(__file__).resolve().parents[1]
sys.path.append(str(项目根目录))

from task import _2_分时数据获取_5分k
from utils import db, common, account


策略名称 = '20260617_资金流向935回测'
开始日期 = 20260506
结束日期 = 20260617
信号时间 = '09:35'
信号时间数字后缀 = '093500000'
资金净流入阈值_万 = 50000
市值阈值_亿元 = 500
市值阈值_万元 = 市值阈值_亿元 * 10000
单票最大买入金额 = 100000.0
最大回撤止损阈值 = -5.0


_5分k缓存 = {}
_股票基础信息缓存 = None
_最新市值达标股票缓存 = None


def _读取资金流向快照(target_date, signal_time=信号时间):
    key = f'fund_flow:history:{target_date}'
    snapshots = db.redis_con_localhost.lrange(key, 0, -1)
    for raw in snapshots:
        try:
            snapshot = json.loads(raw)
        except Exception:
            continue
        if snapshot and snapshot[0].get('时间') == signal_time:
            return snapshot
    return []


def _读取股票基础信息():
    global _股票基础信息缓存

    if _股票基础信息缓存 is None:
        _股票基础信息缓存 = pd.read_sql(
            """
                SELECT ts_code, symbol, name, market, list_status
                FROM securities
            """,
            db.engine,
        )
    return _股票基础信息缓存


def _读取最新市值达标股票():
    global _最新市值达标股票缓存

    if _最新市值达标股票缓存 is not None:
        return _最新市值达标股票缓存

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

    mv_df['symbol_int'] = mv_df['ts_code'].map(common.normalize_symbol)
    mv_df['市值_亿元'] = mv_df['total_mv'] / 10000
    mv_df['市值统计日期'] = mv_date
    _最新市值达标股票缓存 = mv_df[['symbol_int', 'total_mv', '市值_亿元', '市值统计日期']]
    return _最新市值达标股票缓存


def strategy(filtered_codes, target_date):
    """
    资金流向 9:35 回测
    - 读取 Redis fund_flow:history:{target_date} 中 9:35 的行业资金流向快照。
    - 选出资金净流入 > 50000 万的板块龙头。
    - 使用 securities 映射股票代码，只保留主板、上市状态正常的股票。
    - 使用 daily_quotes 最新 total_mv 日期过滤市值 > 300 亿的股票。
    """
    target_date = int(target_date)
    logger.warning(f"【{策略名称}】开始筛选 {target_date} ...")

    snapshot = _读取资金流向快照(target_date)
    if not snapshot:
        logger.warning(f"{target_date} {信号时间} 无资金流向快照")
        return pd.DataFrame([])

    selected_rows = []
    for item in snapshot:
        flow = float(item.get('资金净流入(亿)', 0) or 0)
        leader = str(item.get('龙头', '') or '').strip()
        if flow <= 资金净流入阈值_万:
            continue
        if not leader or leader == '-':
            continue
        selected_rows.append({
            'trade_date': target_date,
            '信号时间': item.get('时间'),
            '板块代码': item.get('板块代码', ''),
            '板块名称': item.get('板块名称', ''),
            'stock_name': leader,
            '资金净流入_万': flow,
        })

    if not selected_rows:
        logger.warning(f"{target_date} {信号时间} 无资金净流入>{资金净流入阈值_万}万的板块龙头")
        return pd.DataFrame([])

    securities_df = _读取股票基础信息()
    selected_df = pd.DataFrame(selected_rows)
    selected_df = selected_df.sort_values('资金净流入_万', ascending=False, kind='mergesort')
    selected_df = selected_df.drop_duplicates('stock_name', keep='first')
    selected_df = selected_df.merge(
        securities_df,
        left_on='stock_name',
        right_on='name',
        how='left',
    )

    missing_df = selected_df[selected_df['ts_code'].isna()]
    for _, row in missing_df.iterrows():
        logger.error(f"{target_date} 龙头股票无法映射代码：{row['stock_name']} | 板块:{row['板块名称']}")

    selected_df = selected_df[
        selected_df['ts_code'].notna() &
        (selected_df['list_status'] == 'L') &
        (selected_df['market'] == '主板')
    ].copy()
    if selected_df.empty:
        logger.warning(f"{target_date} {信号时间} 入选龙头无主板且上市状态正常的股票")
        return pd.DataFrame([])

    try:
        市值_df = _读取最新市值达标股票()
    except ValueError as exc:
        logger.warning(f"{target_date} 市值数据不足：{exc}")
        return pd.DataFrame([])

    selected_df['symbol_int'] = pd.to_numeric(selected_df['symbol'], errors='coerce')
    selected_df = selected_df[selected_df['symbol_int'].notna()].copy()
    selected_df['symbol_int'] = selected_df['symbol_int'].map(common.normalize_symbol)
    selected_df = selected_df.merge(市值_df, on='symbol_int', how='inner')
    if selected_df.empty:
        logger.warning(
            f"{target_date} {信号时间} 入选龙头无主板、上市状态正常且市值>{市值阈值_亿元}亿的股票"
        )
        return pd.DataFrame([])

    logger.warning(f"{target_date} 【{策略名称}】最终选中 {len(selected_df)} 只股票")
    logger.warning(f"入选股票：{' '.join(selected_df['stock_name'].astype(str).tolist())}")
    for _, row in selected_df.iterrows():
        logger.info(
            f"   → 候选 {row['stock_name']} {row['ts_code']} | 板块:{row['板块名称']} | "
            f"资金净流入:{row['资金净流入_万']:.2f}万 | 市值:{row['市值_亿元']:.2f}亿 | "
            f"市值日期:{int(row['市值统计日期'])} | 龙头:{row['stock_name']}"
        )

    return selected_df[[
        'trade_date', '信号时间', '板块代码', '板块名称', 'stock_name',
        '资金净流入_万', 'ts_code', 'symbol', 'name', 'market', 'list_status',
        'total_mv', '市值_亿元', '市值统计日期',
    ]]


def _读取本地5分k(target_date, ts_code):
    code = int(str(ts_code).split('.')[0])
    df = pd.read_sql(
        f"""
            SELECT trade_date AS date, trade_time AS time, stock_code AS code,
                   open_price AS open, high_price AS high, low_price AS low,
                   close_price AS close, volume, turnover AS amount
            FROM intraday_bars_5m
            WHERE trade_date = {int(target_date)}
              AND stock_code = '{code:06d}'
            ORDER BY trade_time
        """,
        db.engine,
    )
    if df.empty:
        return df
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)
    df['time'] = df['time'].astype(str)
    return df


def _读取远程5分k(target_date, ts_code):
    raw_data = _2_分时数据获取_5分k.get_data(target_date, target_date, ts_code)
    if not raw_data:
        return pd.DataFrame([])

    df = pd.DataFrame(
        raw_data,
        columns=['open', 'close', 'date', 'time', 'code', 'high', 'low', 'volume', 'amount', 'adjustflag'],
    )
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)
    df['time'] = df['time'].astype(str)
    df['date'] = df['date'].astype(str).str.replace('-', '', regex=False).astype(int)
    return df.sort_values('time').reset_index(drop=True)


def _读取5分k(target_date, ts_code):
    cache_key = (int(target_date), str(ts_code))
    if cache_key in _5分k缓存:
        return _5分k缓存[cache_key]

    df = _读取本地5分k(target_date, ts_code)
    if df.empty:
        df = _读取远程5分k(target_date, ts_code)

    _5分k缓存[cache_key] = df
    return df


def _取935买入价(target_date, ts_code):
    df = _读取5分k(target_date, ts_code)
    if df.empty:
        return None, df

    target_time = f'{target_date}{信号时间数字后缀}'
    after_df = df[df['time'] >= target_time]
    if after_df.empty:
        return None, df

    buy_row = after_df.iloc[0]
    return float(buy_row['close']), df


def _格式化5分k时间(raw_time):
    text = str(raw_time)
    if len(text) >= 12:
        hhmm = text[8:12]
        return f'{hhmm[:2]}:{hhmm[2:]}'
    return text


def _价格四舍五入(price):
    return float(Decimal(str(price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _读取当日日线(target_date, ts_code):
    code = int(str(ts_code).split('.')[0])
    rows = db.mysql_localhost(
        sql=f"""
            SELECT ts_code, trade_date, stock_name, pre_close
            FROM daily_quotes
            WHERE trade_date = {int(target_date)}
              AND ts_code = {code}
            LIMIT 1
        """,
        fetch=True,
    )
    if not rows:
        return None
    return rows[0]


def _是否935已涨停(target_date, ts_code, stock_name, buy_price):
    daily_row = _读取当日日线(target_date, ts_code)
    if daily_row is None:
        logger.error(f"{stock_name} {ts_code} {target_date} 日线数据为空，无法判断9:35是否涨停，不买")
        return True

    pre_close = float(daily_row['pre_close'] or 0)
    if pre_close <= 0:
        logger.error(f"{stock_name} {ts_code} {target_date} pre_close异常:{pre_close}，无法判断9:35是否涨停，不买")
        return True

    limit_rate = Decimal('1.05') if 'ST' in str(stock_name).upper() else Decimal('1.10')
    limit_price = _价格四舍五入(Decimal(str(pre_close)) * limit_rate)
    if buy_price >= limit_price:
        logger.error(
            f"{stock_name} {ts_code} {target_date} {信号时间} 已涨停，"
            f"9:35价格:{buy_price} 涨停价:{limit_price}，不买"
        )
        return True
    return False


def buy(name, code, price, buy_date, close_price, row=None):
    code = str(code)
    if code in account.holding_stocks and account.holding_stocks[code]['lots'] > 0:
        logger.error(f"{name} {code} 买有了，不买了。")
        return False

    price_max = min(单票最大买入金额, account.available_amount)
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
        '买入日期': int(buy_date),
        '卖出日期': None,
        '持仓最高市值': buy_price,
        '持仓最高回撤': 0,
        '是否发生除权': "否",
        'close_price': close_price,
        '买入时间': 信号时间,
        '买入价': price,
        '持仓最高价': price,
        '卖出时间': None,
    }

    if row is not None:
        account.holding_stocks[code].update({
            '板块名称': row.get('板块名称', ''),
            '板块代码': row.get('板块代码', ''),
            '资金净流入_万': row.get('资金净流入_万', 0),
            '市值_亿元': row.get('市值_亿元', 0),
            '市值统计日期': row.get('市值统计日期', None),
        })

    return True


def simulated_buy(selected_stocks=None, target_date=None):
    if selected_stocks is None or target_date is None:
        logger.error("当日选股买入池为空")
        return

    stock_name_list = selected_stocks['stock_name'].tolist()
    logger.warning(f"{target_date} {信号时间} 准备按5分K价格买入：{stock_name_list}")

    for _, row in selected_stocks.iterrows():
        buy_price, k_df = _取935买入价(target_date, row['ts_code'])
        if buy_price is None:
            logger.error(f"{target_date} {row['stock_name']} {row['ts_code']} 9:35 5分K为空，不买")
            continue
        if _是否935已涨停(target_date, row['ts_code'], row['stock_name'], buy_price):
            continue

        close_price = float(k_df.iloc[-1]['close']) if not k_df.empty else buy_price
        buy_status = buy(
            row['stock_name'],
            row['ts_code'],
            price=buy_price,
            buy_date=target_date,
            close_price=close_price,
            row=row,
        )
        if buy_status:
            buy_date_yield_rate = (close_price - buy_price) / buy_price * 100
            logger.warning(
                f"{row['stock_name']} {target_date} {信号时间} 以5分K收盘价 {buy_price} 买入，"
                f"当天收盘收益率：{buy_date_yield_rate:.2f}%"
            )
        else:
            logger.error(f"{row['stock_name']} {target_date} 买入失败")


def _同步持仓价格(stock_info, close_price):
    old_market_value = stock_info['market_value']
    market_value = round(close_price * stock_info['lots'], 3)
    account.market_value -= old_market_value
    account.market_value += market_value

    if close_price > stock_info.get('持仓最高价', close_price):
        stock_info['持仓最高价'] = close_price
    if market_value > stock_info['持仓最高市值']:
        stock_info['持仓最高市值'] = market_value

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
                   sell_out_盈利回撤_threshold=最大回撤止损阈值,
                   now_date=None):
    logger.warning(
        f"开盘看看有没有符合卖出逻辑的进行卖出 开始 止损阈值:{sell_out_fall_threshold},"
        f"止盈阈值:{sell_out_rise_threshold},最大回撤阈值:{sell_out_盈利回撤_threshold}"
    )
    selected_stocks = list(account.holding_stocks.keys())
    for ts_code in selected_stocks:
        stock_info = account.holding_stocks[ts_code]
        if stock_info['lots'] == 0:
            continue

        df = _读取5分k(now_date, ts_code)
        if df.empty:
            logger.error(f"{stock_info['name']} {ts_code} {now_date} 5分K为空，无法同步持仓")
            continue

        target_start_time = f'{now_date}{信号时间数字后缀}'
        if stock_info['买入日期'] == int(now_date):
            df = df[df['time'] >= target_start_time]
        if df.empty:
            continue

        允许卖出 = stock_info['买入日期'] != int(now_date)
        if not 允许卖出:
            logger.info(f"{stock_info['name']} {ts_code} {now_date} 买入当天只同步市值，不触发卖出")

        sold = False
        for _, row in df.iterrows():
            close_price = float(row['close'])
            _同步持仓价格(stock_info, close_price)

            if 允许卖出 and stock_info['持仓最高回撤'] <= sell_out_盈利回撤_threshold:
                sell_time = _格式化5分k时间(row['time'])
                stock_info['卖出时间'] = sell_time
                logger.warning(
                    f"{stock_info['name']} {ts_code} {now_date} {sell_time} 最大回撤 "
                    f"{stock_info['持仓最高回撤']:.2f}% 达到阈值，按5分K收盘价 {close_price} 卖出"
                )
                account.sell(stock_info['name'], ts_code, close_price, stock_info['lots'], now_date)
                sold = True
                break

        if not sold and stock_info['买入日期'] != int(now_date):
            stock_info['持股天数'] += 1

    logger.warning(f"开盘看看有没有符合卖出逻辑的进行卖出 完成")


def process_daily(target_date=None, filtered_codes=None):
    sell_out_fall_threshold = -5
    sell_out_rise_threshold = 40
    sell_out_盈利回撤_threshold = 最大回撤止损阈值

    selected_stocks = strategy(filtered_codes, target_date)
    if selected_stocks.empty:
        logger.error(f"{target_date} 未筛选到符合策略的股票")
    else:
        simulated_buy(selected_stocks, target_date)

    simulated_sell(sell_out_fall_threshold=sell_out_fall_threshold,
                   sell_out_rise_threshold=sell_out_rise_threshold,
                   sell_out_盈利回撤_threshold=sell_out_盈利回撤_threshold,
                   now_date=target_date)

    return


def main(start_date=开始日期, end_date=结束日期):
    file_name = __file__.split(".py")[0].split("\\")[-1].split("/")[-1].split("/")[-1]
    common.process_for_strategy(start_date, end_date, process_daily, file_name)


if __name__ == '__main__':
    main(start_date=开始日期, end_date=结束日期)
