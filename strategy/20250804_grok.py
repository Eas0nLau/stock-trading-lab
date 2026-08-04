from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from loguru import logger
from tqdm import tqdm

from utils import db, common, account


def compute_rsi(data, periods=14):
    """计算RSI指标"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def compute_macd(data, fast=12, slow=26, signal=9):
    """计算MACD指标"""
    exp1 = data.ewm(span=fast, adjust=False).mean()
    exp2 = data.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line


def compute_bollinger_bands(data, window=20, num_std=2):
    """计算布林带"""
    rolling_mean = data.rolling(window=window).mean()
    rolling_std = data.rolling(window=window).std()
    upper_band = rolling_mean + (rolling_std * num_std)
    return upper_band


def compute_atr(data, window=14):
    """计算ATR（真实波幅）"""
    high_low = data['high'] - data['low']
    high_close = np.abs(data['high'] - data['close'].shift(1))
    low_close = np.abs(data['low'] - data['close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=window).mean()
    return atr


def strategy(filtered_codes, target_date):
    """
    根据策略筛选指定日期的股票，月收益率达到30%。
    参数:
        filtered_codes: 过滤后的股票池（ts_code列表）
        target_date: 目标日期（格式：YYYYMMDD）
    返回:
        DataFrame: 选中的股票（ts_code, stock_name, trade_date, close, monthly_return）
    """

    # 计算数据范围：前60天用于特征分析
    range_days = 60
    start_date = (datetime.strptime(str(target_date), "%Y%m%d") - timedelta(days=range_days)).strftime('%Y%m%d')

    # 加载日线数据
    stock_daily = common.load_stock_daily_data(filtered_codes, start_date, target_date)

    logger.info(f"根据历史日K特征选择股票 开始")
    selected_stocks = []

    # 计算所有股票在target_date的成交额排名
    target_data_all = stock_daily[stock_daily['trade_date'] == target_date]
    if target_data_all.empty:
        logger.warning(f"在 {target_date} 无数据")
        return pd.DataFrame()
    amount_threshold = target_data_all['amount'].quantile(0.95)  # 成交额前5%

    for ts_code in tqdm(filtered_codes, desc="Processing stocks"):
        df = stock_daily[stock_daily['ts_code'] == ts_code].copy()

        # 确保数据按时间排序
        df = df.sort_values('trade_date')

        # 获取目标日期的数据
        target_data = df[df['trade_date'] == target_date]
        if target_data.empty or len(df) < 30:  # 确保有足够数据
            continue

        target_row = target_data.iloc[0]

        # 初始筛选条件
        # 1. 收盘价范围（4-30元）
        if target_row['close'] > 30 or target_row['close'] < 4:
            continue
        # 2. 红K线+连续5天上涨
        df_30d = df[df['trade_date'] >= (datetime.strptime(str(target_date), "%Y%m%d") - timedelta(days=30))].copy()
        if len(df_30d) < 20:
            continue
        recent_5d = df_30d.tail(5)
        continuous_up = all(recent_5d['pct_chg'] > 0) if len(recent_5d) >= 5 else False
        if not continuous_up:
            continue
        # 3. 成交额排名：前5%
        if target_row['amount'] < amount_threshold:
            continue
        # 4. 近期涨幅限制：30天涨幅<35%
        recent_30d_return = (target_row['close'] / df_30d['close'].iloc[0] - 1) * 100
        if recent_30d_return > 35:
            continue

        # 计算技术指标
        # 5. 均线金叉：MA5上穿MA20，高斜率>1.5%
        df_30d['ma5'] = df_30d['close'].rolling(window=5).mean()
        df_30d['ma20'] = df_30d['close'].rolling(window=20).mean()
        target_ma5 = df_30d[df_30d['trade_date'] == target_date]['ma5'].iloc[0]
        target_ma20 = df_30d[df_30d['trade_date'] == target_date]['ma20'].iloc[0]
        prev_ma5 = df_30d[df_30d['trade_date'] < target_date]['ma5'].iloc[-1] if len(
            df_30d[df_30d['trade_date'] < target_date]) > 0 else np.nan
        prev_ma20 = df_30d[df_30d['trade_date'] < target_date]['ma20'].iloc[-1] if len(
            df_30d[df_30d['trade_date'] < target_date]) > 0 else np.nan
        ma5_slope = (target_ma5 - prev_ma5) / prev_ma5 if not np.isnan(prev_ma5) and prev_ma5 != 0 else 0
        ma_cross = (target_ma5 > target_ma20) and (prev_ma5 <= prev_ma20) and (ma5_slope > 0.015) if not np.isnan(
            prev_ma5) and not np.isnan(prev_ma20) else False

        # 6. 成交量放大：最近5天平均成交量>前20天3.5倍
        recent_vol = df_30d.tail(5)['vol'].mean()
        prev_vol = df_30d.iloc[-20:-5]['vol'].mean() if len(df_30d) >= 20 else 0
        vol_increase = recent_vol > prev_vol * 3.5

        # 7. 成交额放大：最近5天平均成交额>前20天3.5倍
        recent_amount = df_30d.tail(5)['amount'].mean()
        prev_amount = df_30d.iloc[-20:-5]['amount'].mean() if len(df_30d) >= 20 else 0
        amount_increase = recent_amount > prev_amount * 3.5

        # 8. 价格突破：突破60天高点+7天站稳
        df_60d = df.copy()
        max_high_60d = df_60d['high'].max()
        price_breakout = target_row['close'] > max_high_60d and df_30d.tail(7)['close'].min() > max_high_60d if len(
            df_30d) >= 7 else False

        # 9. RSI：60-80
        df_30d['rsi'] = compute_rsi(df_30d['close'])
        target_rsi = df_30d[df_30d['trade_date'] == target_date]['rsi'].iloc[0]
        rsi_condition = 60 <= target_rsi <= 80

        # 10. MACD金叉
        df_30d['macd'], df_30d['signal'] = compute_macd(df_30d['close'])
        target_macd = df_30d[df_30d['trade_date'] == target_date]['macd'].iloc[0]
        target_signal = df_30d[df_30d['trade_date'] == target_date]['signal'].iloc[0]
        prev_macd = df_30d[df_30d['trade_date'] < target_date]['macd'].iloc[-1] if len(
            df_30d[df_30d['trade_date'] < target_date]) > 0 else np.nan
        prev_signal = df_30d[df_30d['trade_date'] < target_date]['signal'].iloc[-1] if len(
            df_30d[df_30d['trade_date'] < target_date]) > 0 else np.nan
        macd_cross = (target_macd > target_signal) and (prev_macd <= prev_signal) if not np.isnan(
            prev_macd) and not np.isnan(prev_signal) else False

        # 11. 短期动能：5天涨幅>20%，无显著回调
        recent_5d_return = (target_row['close'] / df_30d.tail(6)['close'].iloc[0] - 1) * 100 if len(df_30d) >= 6 else 0
        recent_low = df_30d.tail(5)['low'].min()
        prev_close = df_30d.tail(6)['close'].iloc[0] if len(df_30d) >= 6 else 0
        no_pullback = recent_low > prev_close * 0.92 if prev_close > 0 else False
        strong_momentum = recent_5d_return > 20 and no_pullback

        # 12. 布林带突破：收盘价突破20日布林带上轨
        df_30d['bb_upper'] = compute_bollinger_bands(df_30d['close'])
        bb_breakout = target_row['close'] > df_30d[df_30d['trade_date'] == target_date]['bb_upper'].iloc[0]

        # 13. 量比：目标日量比>2
        avg_vol_20d = df_30d.iloc[-20:-1]['vol'].mean() if len(df_30d) >= 20 else 0
        vol_ratio = target_row['vol'] / avg_vol_20d if avg_vol_20d > 0 else 0
        vol_ratio_condition = vol_ratio > 2

        # 14. ATR：高波动性（ATR>5%均价）
        df_30d['atr'] = compute_atr(df_30d)
        target_atr = df_30d[df_30d['trade_date'] == target_date]['atr'].iloc[0]
        avg_price = df_30d['close'].rolling(window=20).mean().iloc[-1]
        atr_condition = target_atr / avg_price > 0.05 if avg_price > 0 else False

        # 综合筛选条件
        predict_reason = []
        if ma_cross:
            predict_reason.append("MA5上穿MA20+高斜率")
        if vol_increase:
            predict_reason.append("成交量放大3.5倍")
        if amount_increase:
            predict_reason.append("成交额放大3.5倍")
        if price_breakout:
            predict_reason.append("突破60天高点+7天站稳")
        if rsi_condition:
            predict_reason.append(f"RSI={target_rsi:.2f}")
        if macd_cross:
            predict_reason.append("MACD金叉")
        if strong_momentum:
            predict_reason.append(f"5天涨幅={recent_5d_return:.2f}%+无显著回调")
        if bb_breakout:
            predict_reason.append("布林带上轨突破")
        if vol_ratio_condition:
            predict_reason.append(f"量比={vol_ratio:.2f}")
        if atr_condition:
            predict_reason.append(f"ATR={target_atr / avg_price:.2%}")

        # 计算符合条件的个数
        condition_count = sum(
            [ma_cross, vol_increase, amount_increase, price_breakout, rsi_condition, macd_cross, strong_momentum,
             bb_breakout, vol_ratio_condition, atr_condition])

        # 要求至少6个条件
        if condition_count >= 5:
            logger.info(
                f"{target_row['stock_name']} (ts_code: {ts_code}) 入选，符合条件数: {condition_count}，原因: {', '.join(predict_reason)}")
            selected_stocks.append({
                'ts_code': ts_code,
                'stock_name': target_row['stock_name'],
                'trade_date': target_row['trade_date'],
                'close': target_row['close'],
                'amount': target_row['amount'],
                'predict_reason': ', '.join(predict_reason),
                'condition_count': condition_count
            })

    selected_df = pd.DataFrame(selected_stocks)

    if not selected_df.empty:
        # 按condition_count降序排序，condition_count相同按amount降序
        selected_df = selected_df.sort_values(by=['condition_count', 'amount'], ascending=[False, False])
        # 选取Top 5
        selected_df = selected_df.head(5)
        logger.warning(f"筛选出 {len(selected_df)} 只符合策略的Top 5股票（日期：{target_date}）")
        selected_stock_names = selected_df['stock_name'].tolist()
        logger.warning(f"选中的Top 5股票: {selected_stock_names}")
    else:
        logger.warning(f"在 {target_date} 未找到符合条件的股票")

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
    return common.backtesting(selected_stocks, target_date, eval_days=5, sell_out_fall_threshold=-2)


def main():
    # 1. 加载股票池
    filtered_codes = common.load_stock_pool_symbol()
    results = {}
    distinct_trade_date = db.mysql_localhost(sql=f"""
        select distinct trade_date FROM stock_daily
        where trade_date >= '20250501'
        and trade_date < '20250630'
        order by trade_date
    """, fetch=True)
    for target_date in distinct_trade_date:
        target_date = target_date['trade_date']
        target_date_result = start(target_date, filtered_codes)
        results[target_date] = target_date_result

    # for target_date in ["20250715"]:
    # # for target_date in ["20250701","20250702","20250703",]:
    # #     # target_date = '20250701'
    #     result = main(target_date, stock_pool)
    #     results[target_date] = result
    common.backtesting_print(results)

    account.print_account_info()


if __name__ == "__main__":
    main()
