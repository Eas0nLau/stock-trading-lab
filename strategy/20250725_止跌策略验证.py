from datetime import datetime, timedelta

import pandas as pd
from loguru import logger
from tqdm import tqdm

from utils import db, common, account


def strategy(filtered_codes, target_date):
    """
    根据“策略筛选指定日期的股票
    参数:
        filtered_codes: 过滤后的股票池 DataFrame
        target_date: 目标日期（格式：YYYYMMDD）
    返回:
        DataFrame: 选中的股票（ts_code, stock_name, trade_date, close）
    """
    # 连跌天数
    min_drop_days = 4 + 1

    # 计算前 range_days 交易日的起始日期
    # range_days = 180
    range_days = min_drop_days + 30
    start_date = (datetime.strptime(str(target_date), "%Y%m%d") - timedelta(days=range_days)).strftime(
        '%Y%m%d')  # 余量确保足够数据

    # 加载日线数据
    daily_quotes = common.load_daily_quotes_data(filtered_codes, start_date, target_date)

    logger.info(f"根据策略选择股票 开始")
    selected_stocks = []
    for ts_code in tqdm(filtered_codes):
        # range_days = 30
        df = daily_quotes[daily_quotes['ts_code'] == ts_code]
        # if len(df) < range_days:  # 需要足够数据计算均量
        #     continue

        # 获取目标日期的数据
        target_data = df[df['trade_date'] == target_date]
        if target_data.empty:
            continue

        # 红K线：收盘价 > 开盘价，涨幅在 min_pct_chg 到 max_pct_chg 之间
        target_row = target_data.iloc[0]

        # 20250701
        # if target_row['stock_name'] not in ['沃尔核材']:
        #     continue
        # logger.info(f"当前日期：{target_date} {target_row['stock_name']}")
        if target_row['stock_name'] in ['湖南海利']:
            # 20250703
            # if target_row['stock_name'] in ['森林包装']:
            # 20250702
            # if target_row['stock_name'] in ['獐子岛']:
            pass

        if target_row['close'] > 30:
            # logger.info("不满足 股价小于20 跳过")
            continue

        # 检查当天是否上涨
        # if target_row['close'] < target_row['open']:
        #     # logger.info("当前下跌 跳过")
        #     continue
        # if target_row['pct_chg'] < 0.5 or target_row['pct_chg'] > 8:
        #     # logger.info("涨得太多了 跳过")
        #     continue
        if target_row['pct_chg'] < 0:
            continue

        recent_data = df[df['trade_date'] <= target_date].tail(min_drop_days)

        # 检查连续 min_rise_days 天是否上涨且跌幅满足条件
        is_consecutive_rise = True
        up_count = 0
        down_count = 0
        for i in range(-1, -min_drop_days - 1, -1):
            try:
                pct_chg = recent_data['pct_chg'].iloc[i]
                close = recent_data['close'].iloc[i]
                open = recent_data['open'].iloc[i]
            except:
                logger.error(f"可统计交易日为空")
                is_consecutive_rise = False
                break
            if pct_chg > 3:
                is_consecutive_rise = False
                break
            if pct_chg > 0:
                up_count += 1
                continue
            if pct_chg < 0:
                down_count += 1
                continue
        if up_count > 0:
            is_consecutive_rise = False
        if is_consecutive_rise is False:
            continue
        # 上影线偏离值
        volatility = abs(target_row['high'] - target_row['close']) / min(target_row['high'], target_row['close']) * 100
        if volatility < 1:
            continue
        # 下影线偏离值
        volatility = abs(target_row['low'] - target_row['close']) / min(target_row['low'], target_row['close']) * 100
        if volatility < 1:
            continue
        logger.warning(f"当前日期：{target_date} {target_row['stock_name']} 入选")
        pass
        selected_stocks.append({
            'ts_code': ts_code,
            'stock_name': target_row['stock_name'],
            'trade_date': target_row['trade_date'],
            'close': target_row['close']
        })

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


def start(target_date=None, filtered_codes=None):
    """
    主函数：加载股票池，筛选股票，评估胜率
    """
    sell_out_fall_threshold = -6
    sell_out_rise_threshold = 30

    # 同步早盘操作前市值
    account.sync_open_market_before(now_date=target_date)
    # 昨日选中模拟买入 早盘
    account.simulated_buy()
    # 查看是否有符合卖出逻辑的股票进行卖出
    account.simulated_sell(sell_out_fall_threshold=sell_out_fall_threshold, sell_out_rise_threshold=sell_out_rise_threshold, now_date=target_date)
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
    results = {}
    distinct_trade_date = db.mysql_localhost(sql=f"""
        select distinct trade_date FROM daily_quotes
        where trade_date >= '20250501'
        and trade_date < '20250901'
        order by trade_date
    """, fetch=True)
    for target_date in distinct_trade_date:
        target_date = target_date['trade_date']
        start(target_date, filtered_codes)

    # for target_date in ["20250715"]:
    # # for target_date in ["20250701","20250702","20250703",]:
    # #     # target_date = '20250701'
    #     result = main(target_date, stock_pool)
    #     results[target_date] = result
    # common.backtesting_print(results)
    account.print_account_info()


if __name__ == "__main__":
    main()
