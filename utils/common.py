import time
import traceback
import config
from datetime import datetime, timedelta
from functools import wraps

import pandas as pd
import plotly.graph_objects as go
import tushare as ts
from loguru import logger
from plotly.subplots import make_subplots
from sqlalchemy import text
from utils import db, account

# 初始化 Tushare
# ts.set_token(config.ts_token)  # 替换为你的 token
#
pro_list = []
for ts_token in config.ts_token_list:
    pro_list.append(ts.pro_api(ts_token))
pro = pro_list[0]

stock_basic_csv_path = f'{config.project_path}/data/stock_basic.csv'


def fetch_stock_basic():
    """
    获取沪深 A 股列表并保存到 CSV
    参数:
        csv_path: 输出 CSV 文件路径
    返回:
        DataFrame: A 股基本信息
    """
    try:
        logger.info(f"从 API 获取 A 股列表 开始")
        stock_basic = pro.stock_basic(
            exchange='',
            list_status='L',
            fields='ts_code,symbol,name,area,industry,market,list_date,list_status'
        )
        logger.info(f"从 API 获取 A 股列表 完成，数量：{len(stock_basic)}")
        stock_basic.to_csv(stock_basic_csv_path, index=False, encoding='utf-8-sig')
        return stock_basic
    except Exception as e:
        logger.error(f"从 API 获取 A 股列表 异常: {e}")
        logger.error(traceback.format_exc())
        return pd.DataFrame()


def filter_stock_basic():
    """
    过滤股票池，仅保留主板、非退市、非 ST 股票
    参数:
        stock_basic: A 股基本信息 DataFrame
    返回:
        DataFrame: 过滤后的股票池
    """

    try:
        try:
            logger.info(f"从 API 获取 A 股列表 开始")
            stock_basic = pro.stock_basic(
                exchange='',
                list_status='L',
                fields='ts_code,symbol,name,area,industry,market,list_date,list_status'
            )
            logger.info(f"从 API 获取 A 股列表 完成，数量：{len(stock_basic)}")
            stock_basic.to_csv(stock_basic_csv_path, index=False, encoding='utf-8-sig')
        except Exception as e:
            logger.error(f"从 API 获取 A 股列表 异常: {e}")
            logger.info(f"从 API 加载 A 股列表失败，开始 读取CSV缓存")
            stock_basic = pd.read_csv(stock_basic_csv_path, encoding='utf-8-sig')
            logger.info(f"从 CSV 加载 A 股列表成功，数量：{len(stock_basic)}")
        logger.info(f"开始过滤股票，排除ST")
        # 过滤条件
        filtered_pool = stock_basic
        # filtered_pool = stock_basic[
        #     # (stock_basic['market'] == '主板') &  # 仅主板
        #     # (~stock_basic['name'].str.contains(r'ST|\*ST', case=False, na=False))  # 排除 ST/*ST
        #     ~stock_basic['name'].str.contains(r'ST|\*ST', case=False, na=False)  # 排除 ST/*ST
        #     ]
        logger.info(f"过滤后股票池数量：{len(filtered_pool)}")
        return filtered_pool
    except Exception as e:
        logger.error(f"过滤股票池失败: {e}")
        logger.error(traceback.format_exc())
        return pd.DataFrame()


def load_stock_pool():
    """
    从 MySQL 加载过滤后的股票池
    参数:
        stock_basic: 股票池表名
    返回:
        DataFrame: 过滤后的股票池
    """
    try:
        stock_pool = pd.read_sql(f"SELECT ts_code FROM stock_basic", db.engine)
        # logger.info(f"加载股票池，数量：{len(stock_pool)}")
        filtered_codes = stock_pool['ts_code'].tolist()
        return filtered_codes
    except Exception as e:
        logger.error(f"加载股票池失败：{e}")
        exit()


def load_stock_pool_symbol():
    """
    从 MySQL 加载过滤后的股票池
    参数:
        stock_basic: 股票池表名
    返回:
        DataFrame: 过滤后的股票池
    """
    try:
        stock_pool = pd.read_sql(f"SELECT symbol FROM stock_basic where market='主板'", db.engine)
        # logger.info(f"加载股票池，数量：{len(stock_pool)}")
        filtered_codes = stock_pool['symbol'].tolist()
        return filtered_codes
    except Exception as e:
        logger.error(f"加载股票池失败：{e}")
        exit()


def load_stock_symbol_ts_code_dict():
    try:
        stock_pool = pd.read_sql(f"SELECT symbol,ts_code FROM stock_basic", db.engine)
        # logger.info(f"加载股票池，数量：{len(stock_pool)}")
        return stock_pool.set_index('symbol')['ts_code'].to_dict()
    except Exception as e:
        logger.error(f"加载股票池失败：{e}")
        exit()


def backtesting(selected_stocks, target_date, eval_days=3, sell_out_fall_threshold=0.5):
    """
    评估选股在 buy_date 入选后第 1 天到第 N 天的盈利百分比、胜率和平均盈利率
    参数:
        selected_stocks: 选中的股票 DataFrame（ts_code, stock_name, trade_date, close）
        target_date: 目标日期（格式：YYYYMMDD）
        daily_table: 日线数据表名
        eval_days: 统计天数（例如 2、5、7）
        sell_out_fall_threshold: 止损比
    返回:
        DataFrame: 包含下一交易日结果（ts_code, stock_name, entry_date, entry_price, next_date, next_close, return, win）
    """
    next_date_end = (datetime.strptime(str(target_date), "%Y%m%d") + timedelta(days=eval_days + 30)).strftime(
        '%Y%m%d')  # 缓冲 30 天

    stock_name_list = selected_stocks['stock_name'].tolist()
    query = f"""
        SELECT ts_code, trade_date, close, stock_name, open, pre_close, high, low
        FROM stock_daily
        WHERE ts_code IN {str(tuple([int(i) for i in selected_stocks['ts_code'].tolist()])).replace(",)", ")")}
        AND trade_date >= {target_date}
        AND trade_date <= {next_date_end}
        order by trade_date
    """
    next_day_data = pd.read_sql(query, db.engine)
    # buy_date = next_day_data['trade_date'].min()
    # 入选后的交易日期
    after_purchase_date_list = list(set(next_day_data['trade_date'].tolist()))
    if len(after_purchase_date_list) <= 1:
        msg = f"{target_date} 入选后可统计的交易日期为空 {stock_name_list} "
        logger.warning(msg)
        return {
            'msg': msg
        }
    # 去重并排序 从小到大
    after_purchase_date_list = sorted(list(set(after_purchase_date_list)))
    if target_date in after_purchase_date_list:
        after_purchase_date_list.remove(target_date)

    buy_date = after_purchase_date_list[0]

    stock_name_yield_rate_dict = {}
    day_avg_yield_rate = {}
    eval_days += 1
    for stock_name in stock_name_list:
        stock_name_yield_rate_dict[stock_name] = {}
        stock_name_df = next_day_data[next_day_data['stock_name'] == stock_name]
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
        if pre_close > open_price:
            logger.error(f"{stock_name} 低开不买")
            continue
        target_date_high = stock_name_df[stock_name_df['trade_date'] == target_date].iloc[0]['high']
        if target_date_high > open_price:
            logger.error(f"{stock_name} 未开在昨日最高点之上不买")
            continue
        buy_date_yield_rate = None
        buy_date_open_price = None
        is_一字板涨停 = False
        if open_price == close_price == high_price == low_price:
            is_一字板涨停 = True
            logger.error(f"{stock_name} {stock_name_buy_date} 一字板涨停 买不进 跳过")
            continue
        else:
            buy_date_yield_rate = (close_price - open_price) / open_price * 100
            buy_date_open_price = open_price
            logger.warning(
                f"{stock_name} {stock_name_buy_date} 以开盘价 {open_price} 买入，当天收盘收益率：{buy_date_yield_rate:.2f}%")

        days_count = 1
        # 如果入选后当天收盘为亏损，入选后第一天直接以开盘价卖出
        sell_out = False
        sell_out_day = None
        if is_一字板涨停 is False and buy_date_yield_rate and buy_date_yield_rate < sell_out_fall_threshold:
            sell_out = True
            sell_out_day = days_count
            logger.error(
                f"{stock_name} {stock_name_buy_date} 入选后当天收盘收益率：{buy_date_yield_rate:.2f}% 小于{sell_out_fall_threshold:.2f}% 不及预期，则下一交易日直接以开盘价卖出")
        for after_purchase_date in after_purchase_date_list:
            day_avg_yield_rate_key = f"入选后第{days_count}天,平均收益率"
            yield_rate = 0

            if stock_name_df[stock_name_df['trade_date'] == after_purchase_date].empty:
                logger.error(f"{stock_name} {after_purchase_date} 入选后可统计的交易日期为空")
                if day_avg_yield_rate_key not in day_avg_yield_rate:
                    day_avg_yield_rate[day_avg_yield_rate_key] = yield_rate
                else:
                    day_avg_yield_rate[day_avg_yield_rate_key] += yield_rate
                continue
            open_price = stock_name_df[stock_name_df['trade_date'] == after_purchase_date].iloc[0]['open']
            pre_close = stock_name_df[stock_name_df['trade_date'] == after_purchase_date].iloc[0]['pre_close']
            close_price = stock_name_df[stock_name_df['trade_date'] == after_purchase_date].iloc[0]['close']
            high_price = stock_name_df[stock_name_df['trade_date'] == after_purchase_date].iloc[0]['high']
            low_price = stock_name_df[stock_name_df['trade_date'] == after_purchase_date].iloc[0]['low']
            is_一字板涨停 = False
            if buy_date_open_price:
                yield_rate = (open_price - buy_date_open_price) / buy_date_open_price * 100
            elif open_price == close_price == high_price == low_price:
                is_一字板涨停 = True
                logger.error(f"{stock_name} {after_purchase_date} 一字板涨停 买不进")
                yield_rate = 0
            else:
                yield_rate = (close_price - open_price) / open_price * 100
                buy_date_open_price = open_price
                stock_name_buy_date = after_purchase_date
                logger.error(
                    f"{stock_name} {stock_name_buy_date} 开板 以开盘价 {open_price} 买入，当天收盘收益率：{yield_rate:.2f}%")
            if sell_out and days_count == sell_out_day:
                logger.warning(
                    f"入选后第 {days_count} 天 {after_purchase_date} 开盘直接卖出 开盘价：{open_price} 收益率：{yield_rate:.2f}%")
            elif sell_out:
                logger.warning(
                    f"入选后第 {days_count} 天 {after_purchase_date} 收益率0 已卖出")
            elif stock_name_buy_date != after_purchase_date:
                logger.warning(
                    f"入选后第 {days_count} 天 {after_purchase_date} 开盘价：{open_price} 收益率：{yield_rate:.2f}%")

            if sell_out_day and days_count > sell_out_day:
                yield_rate = 0

            if day_avg_yield_rate_key not in day_avg_yield_rate:
                day_avg_yield_rate[day_avg_yield_rate_key] = yield_rate
            else:
                day_avg_yield_rate[day_avg_yield_rate_key] += yield_rate

            stock_name_yield_rate_dict[stock_name][f"入选后第{days_count}天,收益率"] = f"{yield_rate:.2f}%"

            days_count += 1
            if days_count >= eval_days:
                break

            pre_close_price = stock_name_df[stock_name_df['trade_date'] == after_purchase_date].iloc[0]['pre_close']
            close_price = stock_name_df[stock_name_df['trade_date'] == after_purchase_date].iloc[0]['close']
            pre_close_yield_rate = (close_price - pre_close_price) / pre_close_price * 100
            if sell_out is False and stock_name_buy_date != after_purchase_date and pre_close_yield_rate < sell_out_fall_threshold:
                sell_out = True
                sell_out_day = days_count
                logger.error(
                    f"入选后第 {days_count} 天 {after_purchase_date} 入选后当天收盘收益率：{pre_close_yield_rate:.2f}% 小于{sell_out_fall_threshold:.2f}% 不及预期，则下一交易日直接以开盘价卖出")
            if sell_out is False and stock_name_buy_date != after_purchase_date and pre_close > open_price:
                sell_out = True
                sell_out_day = days_count
                logger.error(
                    f"入选后第 {days_count} 天 {after_purchase_date} 入选后当天收盘收益率：{pre_close_yield_rate:.2f}% 低开 不及预期，则下一交易日直接以开盘价卖出")

    # 平均收益率计算
    for _day in day_avg_yield_rate.keys():
        day_avg_yield_rate[_day] = day_avg_yield_rate[_day] / len(stock_name_list)
        logger.warning(f"{stock_name_list} {_day} {day_avg_yield_rate[_day]:.2f}%")
    pass
    return {
        'stock_name_list': stock_name_list,
        'stock_name_yield_rate_dict': stock_name_yield_rate_dict,
        'day_avg_yield_rate': day_avg_yield_rate,
    }


def backtesting_print(results):
    logger.warning(f"-------------------------------------------------------------------------------------------------")
    logger.warning(
        f"----------------------------------    开始打印回测结果    ------------------------------------------")
    logger.warning(f"-------------------------------------------------------------------------------------------------")
    success_count = 0
    day_avg_yield_rate = {}
    for target_date in results.keys():
        logger.warning(f"日期：{target_date}")
        target_date_result = results[target_date]
        if target_date_result and 'msg' not in target_date_result:
            success_count += 1
            logger.warning(f"选中股票：{target_date_result['stock_name_list']}")
            for stock_name in target_date_result['stock_name_yield_rate_dict']:
                if target_date_result['stock_name_yield_rate_dict'][stock_name]:
                    logger.warning(f"{stock_name}：{target_date_result['stock_name_yield_rate_dict'][stock_name]}")
            for _day in target_date_result['day_avg_yield_rate'].keys():
                logger.warning(
                    f"{target_date_result['stock_name_list']} {_day} {target_date_result['day_avg_yield_rate'][_day]:.2f}")
                if _day not in day_avg_yield_rate:
                    day_avg_yield_rate[_day] = target_date_result['day_avg_yield_rate'][_day]
                else:
                    day_avg_yield_rate[_day] += target_date_result['day_avg_yield_rate'][_day]
        elif 'msg' in target_date_result:
            logger.warning(target_date_result['msg'])
        else:
            logger.warning(f"返回值异常：{target_date_result}")
        pass
    logger.warning(f"在 {len(results.keys())} 个交易日中，回测成功 {success_count} 日。")
    for _day in day_avg_yield_rate.keys():
        day_avg_yield_rate[_day] = day_avg_yield_rate[_day] / success_count
        logger.warning(f"平均 {_day} {day_avg_yield_rate[_day]:.2f}")


def get_next_date(target_date):
    query = f"""
       SELECT 日期
       FROM akshare_sh000001
       WHERE 日期 > {target_date}
       order by 日期
       limit 1 
    """
    sh_range_data = db.mysql_localhost(sql=query, fetch=True)
    if sh_range_data:
        return sh_range_data[0]['日期']
    else:
        return None


def check_指数开盘(target_date):
    range_date = (datetime.strptime(str(target_date), "%Y%m%d") - timedelta(days=15)).strftime('%Y%m%d')  # 缓冲 30 天
    # 获取上证指数信息
    query = f"""
       SELECT 开盘, 收盘
       FROM akshare_sh000001
       WHERE 日期 >= {range_date}
       AND 日期 <= {target_date}
       order by 日期
    """
    sh_range_data = pd.read_sql(query, db.engine)
    _昨日指数收盘价 = sh_range_data.iloc[-2]['收盘']
    _今日指数开盘价 = sh_range_data.iloc[-1]['开盘']
    if _今日指数开盘价 < _昨日指数收盘价:
        logger.error(
            f"指数未开在昨日收盘价之上，不进行买入操作。_昨日指数收盘价：{_昨日指数收盘价}，_今日指数开盘价：{_今日指数开盘价}")
        account.next_date_pre_selection_stocks = {
            'selected_stocks': None,
            'target_date': None,
        }
        return True
    return False


def plotly_init(start_date, end_date):
    range_date = (datetime.strptime(str(start_date), "%Y%m%d") - timedelta(days=15)).strftime('%Y%m%d')
    index_list = db.mysql_localhost(sql=f"""
        SELECT 日期, 收盘, 涨跌幅
        FROM akshare_sh000001
        WHERE 日期 >= {range_date}
        AND 日期 <= {end_date}
        order by 日期
    """, fetch=True)
    index_value = {item["日期"]: item["收盘"] for item in index_list}
    index_change = {item["日期"]: item["涨跌幅"] for item in index_list}
    init_date = None
    for index_row in index_list:
        if index_row['日期'] < start_date:
            init_date = index_row['日期']
            continue
        break
    plotly_data = [{'date': str(init_date),
                    'index_value': index_value[init_date],
                    'index_change': index_change[init_date],
                    'account_value': float(account.available_amount + account.market_value),
                    'account_change': account.profit_loss,
                    }]
    return plotly_data, index_value, index_change


def plotly_show(plotly_data, file_name):
    # 转换为 DataFrame
    df = pd.DataFrame(plotly_data)

    # 处理日期：先转为纯 int str，避免 float .0 问题，然后转换为 datetime
    df['date'] = df['date'].fillna(0).astype(int).astype(str)
    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')

    # 过滤无效日期，只保留有效日期
    df = df.dropna(subset=['date'])

    # 如果数据为空，记录日志并返回
    if df.empty:
        logger.warning(f"数据为空，无法生成图表: {file_name}")
        return

    # 创建日期字符串用于 category 轴（确保均匀间距）
    df['date_str'] = df['date'].dt.strftime('%Y%m%d')

    # 创建子图：点数和涨幅
    fig = make_subplots(rows=2, cols=1,
                        subplot_titles=("市值", "每日涨幅 (%)"),
                        shared_xaxes=True, vertical_spacing=0.1)

    # 添加点数折线图（X轴使用 date_str）
    # fig.add_trace(go.Scatter(x=df['date_str'], y=df['index_value'], name='上证指数', line=dict(color='blue')), row=1,
    #               col=1)
    fig.add_trace(go.Scatter(x=df['date_str'], y=df['account_value'], name='账户市值', line=dict(color='red')), row=1,
                  col=1)

    # 添加涨幅折线图（X轴使用 date_str）
    fig.add_trace(
        go.Scatter(x=df['date_str'], y=df['index_change'], name='上证涨幅 (%)', line=dict(color='blue', dash='dash')),
        row=2,
        col=1)
    fig.add_trace(
        go.Scatter(x=df['date_str'], y=df['account_change'], name='账户涨幅 (%)', line=dict(color='red', dash='dash')),
        row=2, col=1)

    # 更新布局
    fig.update_layout(
        title=f"上证指数与账户市值波动图_{file_name}",
        xaxis_title="日期",
        yaxis_title="市值",
        yaxis2_title="涨幅 (%)",
        showlegend=True,
        hovermode="x unified",  # 统一悬浮提示
        template="plotly_white"
    )

    # ==================== 只修改市值轴：强制显示完整整数（不带 k/M） ====================
    fig.update_yaxes(
        tickformat=',.0f',      # 显示成 100,000（带千位逗号，最清晰）
        row=1,
        col=1
    )
    # ====================================================================================

    # 设置 X 轴：类型为 category（均匀间距），只显示实际有效日期
    fig.update_xaxes(
        type='category',  # 关键：使用 category 类型，确保每个日期间距均匀
        tickvals=df['date_str'],  # 类别标签
        ticktext=df['date'].dt.strftime('%Y-%m-%d'),  # 格式化为 YYYY-MM-DD
        tickangle=45,  # 倾斜日期标签
        row=2, col=1  # 应用到共享 X 轴
    )

    # 显示图表
    fig.show()

    # 保存为 HTML 文件
    fig.write_html(f"{config.project_path}/output/上证指数与账户市值波动图_{file_name}.html")
    logger.warning(f"http://localhost:63342/stock_trading_lab/strategy/上证指数与账户市值波动图_{file_name}.html")


def process_for_strategy(start_date, end_date, func, file_name):
    filtered_codes = load_stock_pool_symbol()
    distinct_trade_date = db.mysql_localhost(sql=f"""
        select distinct trade_date FROM stock_daily
        where trade_date >= {start_date}
        and trade_date <= {end_date}
        order by trade_date
    """, fetch=True)
    plotly_data, index_value, index_change = plotly_init(start_date, end_date)
    index_change_value = plotly_data[0]['index_change']
    for target_date in distinct_trade_date:
        target_date = target_date['trade_date']
        func(*(target_date, filtered_codes))
        account.print_account_info()
        index_change_value += index_change[target_date]
        plotly_data.append({'date': target_date,
                            'index_value': index_value[target_date],
                            'index_change': index_change_value,
                            'account_value': float(account.available_amount + account.market_value),
                            'account_change': account.profit_loss,
                            })
    plotly_show(plotly_data, f"{file_name}_{start_date}_{end_date}")
    pass


def timer_statistics(func):
    """计算函数执行时间的装饰器"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        # 开始计时
        start_time = time.time()

        # 执行被装饰的函数
        result = func(*args, **kwargs)

        # 计算耗时
        end_time = time.time()
        execution_time = end_time - start_time

        # 格式化输出
        if execution_time < 60:
            time_str = f"{execution_time:.2f}秒"
        elif execution_time < 3600:
            minutes = int(execution_time // 60)
            seconds = execution_time % 60
            time_str = f"{minutes}分钟{seconds:.2f}秒"
        else:
            hours = int(execution_time // 3600)
            minutes = int((execution_time % 3600) // 60)
            seconds = execution_time % 60
            time_str = f"{hours}小时{minutes}分钟{seconds:.2f}秒"

        logger.warning(f"函数 {func.__name__} 执行耗时: {time_str}")
        return result

    return wrapper


@timer_statistics
def load_stock_daily_data(filtered_codes, start_date, target_date):
    logger.info(f"加载日线数据 开始 trade_date BETWEEN {start_date} AND {target_date}")
    query = f"""
        SELECT ts_code, trade_date, open, high, low, pre_close, close, amount, pct_chg, vol, stock_name 
        FROM stock_daily 
        WHERE ts_code IN {str(tuple(filtered_codes)).replace(",)", ")")} 
        AND trade_date BETWEEN %s AND %s
    """
    result = db.mysql_localhost(sql=query, params=(start_date, target_date), fetch=True)
    stock_daily = pd.DataFrame(result)
    logger.info(f"加载日线数据 完成 {len(stock_daily)}")
    return stock_daily


if __name__ == '__main__':
    pass
    filter_stock_basic()
