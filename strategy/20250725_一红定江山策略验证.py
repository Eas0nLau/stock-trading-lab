from datetime import datetime, timedelta

import pandas as pd
from loguru import logger
from tqdm import tqdm

from utils import db, common, account


def strategy(filtered_codes, target_date):
    """
    根据策略筛选指定日期的股票
    参数:
        filtered_codes: 过滤后的股票池 DataFrame
        target_date: 目标日期（格式：YYYYMMDD）
    返回:
        DataFrame: 选中的股票（ts_code, stock_name, trade_date, close）
    """

    vol_multiplier = 2

    # 计算前 range_days 交易日的起始日期
    range_days = 30
    start_date = (datetime.strptime(str(target_date), "%Y%m%d") - timedelta(days=range_days)).strftime(
        '%Y%m%d')  # 余量确保足够数据

    # 加载日线数据
    daily_quotes = common.load_daily_quotes_data(filtered_codes, start_date, target_date)

    logger.info(f"根据策略选择股票 开始")
    selected_stocks = []
    for ts_code in tqdm(filtered_codes):
        range_days = 90
        df = daily_quotes[daily_quotes['ts_code'] == ts_code]
        if len(df) < range_days:  # 需要足够数据计算均量
            continue

        # 获取目标日期的数据
        target_data = df[df['trade_date'] == target_date]
        if target_data.empty:
            continue

        # 红K线：收盘价 > 开盘价，涨幅在 min_pct_chg 到 max_pct_chg 之间
        target_row = target_data.iloc[0]

        # 20250701
        # if target_row['stock_name'] not in ['柳钢股份']:
        #     # 20250703
        # #     # if target_row['stock_name'] in ['森林包装']:
        # #     # 20250702
        # #     # if target_row['stock_name'] in ['獐子岛']:
        #     continue

        if target_row['close'] > 30:
            # logger.info("不满足 股价小于20 跳过")
            continue
        if target_row['pct_chg'] < 9:
            # logger.info("不满足 当天涨幅>5 跳过")
            continue
        if target_row['open'] == target_row['close']:
            # logger.info("一字板 跳过")
            continue
        # 跳空高开
        # pre_high_price = df.iloc[-2]['high']
        # if target_row['open'] < pre_high_price:
        #     # logger.info("不满足 跳空高开 跳过")
        #     continue
        # 最近3天涨幅 5%<_3day_pct_chg_sum<15%
        _3day_pct_chg_sum = df.iloc[-2:]['pct_chg'].sum()
        if 15 < _3day_pct_chg_sum and _3day_pct_chg_sum > 5:
            # logger.info("不满足 最近3天涨幅<20 跳过")
            continue
        # range_days日新高
        # 检查当前价格是否为历史最高价
        if target_row['close'] < df.iloc[:-1]['high'].max():
            # logger.info(f"不满足 {range_days}日新高 跳过")
            continue
        # 2日前股价稳定 涨幅平均值在2以内
        # _2day_ago_pct_chg_mean = df.iloc[:-int(range_days/2)]['pct_chg'].mean()
        # if -2 > _2day_ago_pct_chg_mean or _2day_ago_pct_chg_mean > 2:
        #     logger.info("不满足 2日前股价稳定 涨幅平均值在3以内 跳过")
        #     continue
        logger.info(f"{target_row['stock_name']}")
        recent_data = df[df['trade_date'] < target_date].tail(range_days)
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
            f"近 {range_days} 日 波动率：{volatility} 收盘平均价：{_day_ago_close_mean} 最高价：{_day_ago_high_max} 最低价：{_day_ago_low_min} "
            f"上波动率：{_day_ago_high_volatility:.2f}% 下波动率：{_day_ago_low_volatility:.2f}%")
        if _day_ago_high_volatility >= 4 or _day_ago_low_volatility >= 4:
            # logger.info(f"不满足 1日前~{range_days}日前 上下波动设置阈值偏离不能超过平均值上下5% 跳过")
            continue
        volatility_threshold = 8
        if volatility >= volatility_threshold:
            # logger.info(f"不满足 1日前~{range_days}日前 上下波动率大于{volatility_threshold}% 跳过")
            continue
        pct_chg_avg = recent_data['pct_chg'].abs().mean()
        if pct_chg_avg >= 2:
            continue

        pass
        # 计算当天成交额是否大于 前20日最大成交量*vol_multiplier
        max_vol = recent_data['vol'].mean()
        if target_row['vol'] <= max_vol * vol_multiplier:
            logger.info(f"不满足 计算当天成交交是否大于 前{range_days}日最大成交额*{vol_multiplier} 跳过")
            continue
        logger.warning(f"{target_row['stock_name']} 入选")
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
    # 查看是否有符合清仓逻辑的股票
    # 3. 评估下一交易日胜率
    return


def main():
    # 1. 加载股票池
    filtered_codes = common.load_stock_pool_symbol()
    results = {}
    distinct_trade_date = db.mysql_localhost(sql=f"""
        select distinct trade_date FROM daily_quotes
        where trade_date >= '20250801'
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
