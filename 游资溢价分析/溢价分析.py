from datetime import datetime, timedelta

from loguru import logger
from tqdm import tqdm

from utils import db


def main(start_date, latest_date):
    start_date = int(start_date)
    latest_date = int(latest_date)
    pass_names = ['深股通专用', '沪股通专用']
    买卖净额_阈值 = 2000
    平均收益率_阈值 = 2
    logger.warning(f"统计周期 {start_date} {latest_date}")
    cache = {}
    t_龙虎榜_list = db.mysql_localhost(f"""
        SELECT x.* FROM t_龙虎榜 x
        where date = {latest_date}
    """, fetch=True)
    # 买方席位
    买方席位_dict = {}
    for row in t_龙虎榜_list:
        if row['股票名称'] not in 买方席位_dict:
            买方席位_dict[row['股票名称']] = {}
        if row['明细'] not in 买方席位_dict[row['股票名称']]:
            买方席位_dict[row['股票名称']][row['明细']] = []
        买方席位_dict[row['股票名称']][row['明细']].append(row['买1营业部'])
        买方席位_dict[row['股票名称']][row['明细']].append(row['买2营业部'])
        买方席位_dict[row['股票名称']][row['明细']].append(row['买3营业部'])
        买方席位_dict[row['股票名称']][row['明细']].append(row['买4营业部'])
        买方席位_dict[row['股票名称']][row['明细']].append(row['买5营业部'])

    data_list = db.mysql_localhost(f"""
        SELECT x.* FROM t_龙虎榜_营业部_上榜历史数据 x
        where 日期 >= {start_date}
        and 日期 <= {latest_date}
        -- and 营业部名称 = '国泰海通证券股份有限公司武汉紫阳东路证券营业部'
    """, fetch=True)
    结果统计 = {}
    营业部_id_to_name = {}
    code_id_to_name = {}
    name_to_code_id = {}
    latest_date_data = []
    for data_row in tqdm(data_list):
        # if '连续' in data_row['上榜原因']:
        #     continue
        # if data_row['上榜原因'] not in ['日涨幅偏离值达7%的证券', '日换手率达20%的证券', '日振幅值达15%的证券', '日换手率达20%的证券;日振幅值达15%的证券']:
        #     continue
        if data_row['买卖净额'] < 买卖净额_阈值:
            continue
        # if data_row['涨跌幅'] < -7:
        #     continue
        pass
        营业部id = data_row['营业部id']
        营业部名称 = data_row['营业部名称']
        if 营业部名称 in pass_names:
            continue
        if 营业部id not in 结果统计:
            结果统计[营业部id] = {
                'b_count': 0,
                '平均收益率': 0,
            }
        if data_row['日期'] == latest_date \
                and data_row['股票简称'] in 买方席位_dict \
                and data_row['上榜原因'] in 买方席位_dict[data_row['股票简称']] \
                and 营业部名称 in 买方席位_dict[data_row['股票简称']][data_row['上榜原因']]:
            latest_date_data.append(data_row)
        营业部_id_to_name[营业部id] = 营业部名称
        日期 = data_row['日期']
        股票简称 = data_row['股票简称']
        股票代码 = data_row['股票代码']
        code_id_to_name[int(股票代码)] = 股票简称
        name_to_code_id[股票简称] = int(股票代码)
        # if 营业部名称 != '浙商证券股份有限公司杭州五星路证券营业部':
        #     continue
        #     logger.error(
        #         f"{营业部名称} {营业部id} {日期} {股票简称} {股票代码} {data_row['上榜原因']} {data_row['买卖净额']} {data_row['涨跌幅']}")

        range_date = (datetime.strptime(str(日期), "%Y%m%d") + timedelta(days=20)).strftime('%Y%m%d')  # 缓冲 30 天
        query = f"""
            -- SELECT ts_code, trade_date, close, stock_name, open, pre_close, high, low, pct_chg
            SELECT open
            FROM stock_daily
            WHERE ts_code = {int(股票代码)}
            AND trade_date >= {日期}
            AND trade_date <= {range_date}
            AND trade_date <= {latest_date}
            order by trade_date
        """
        if query in cache:
            stock_daily_list = cache[query]
        else:
            stock_daily_list = db.mysql_localhost(query, fetch=True)
            cache[query] = stock_daily_list
        if not stock_daily_list or len(stock_daily_list) < 3:
            continue
        买入日开盘价 = stock_daily_list[1]['open']
        # 买入日收盘价 = stock_daily_list[1]['close']
        买入后第一日收盘价 = stock_daily_list[2]['open']
        volatility = (买入后第一日收盘价 - 买入日开盘价) / 买入日开盘价 * 100
        # logger.info(f"{data_row.values()}\n"
        #             f"买入日开盘价：{买入日开盘价} 买入日收盘价：{买入日收盘价} 买入后第一日收盘价：{买入后第一日收盘价} 买入后第一日收盘卖出收益率：{volatility:2f}")

        结果统计[营业部id]['b_count'] += 1
        结果统计[营业部id]['平均收益率'] += volatility
        pass

    for key in 结果统计.keys():
        买入次数 = 结果统计[key]['b_count']
        if 买入次数 == 0:
            平均收益率 = 0
        else:
            平均收益率 = 结果统计[key]['平均收益率'] / 买入次数
        结果统计[key]['平均收益率'] = 平均收益率

    top_营业部 = {}
    # 按盈亏比从小到大排序
    sorted_stocks = sorted(结果统计.items(), key=lambda x: x[1]['平均收益率'])
    for 营业部id, 结果 in sorted_stocks:
        买入次数 = 结果['b_count']
        if 买入次数 < 3:
            continue
        平均收益率 = 结果['平均收益率']
        if 平均收益率 > 平均收益率_阈值:
            top_营业部[营业部id] = 结果
            # logger.info(f"{营业部_id_to_name[营业部id]} 买入次数:{买入次数} 平均收益率：{平均收益率:.2f}%")

    stock_code = set()
    # 计算阵容胜率
    stock_code_平均收益率 = {}
    for data_row in latest_date_data:
        if data_row['买卖净额'] < 买卖净额_阈值 \
                and data_row['股票简称'] in 买方席位_dict \
                and data_row['营业部名称'] in 买方席位_dict[data_row['股票简称']][data_row['上榜原因']]:
            continue

        if data_row['股票代码'] not in stock_code_平均收益率:
            stock_code_平均收益率[data_row['股票代码']] = {}
        if data_row['上榜原因'] not in stock_code_平均收益率[data_row['股票代码']]:
            stock_code_平均收益率[data_row['股票代码']][data_row['上榜原因']] = []
        stock_code_平均收益率[data_row['股票代码']][data_row['上榜原因']].append(
            结果统计[data_row['营业部id']]['平均收益率'])

    for 股票代码, 平均收益率_dict in stock_code_平均收益率.items():
        for 上榜原因, 平均收益率_list in 平均收益率_dict.items():
            # 因为存在多日榜，买卖方不好区分，所以根据收益率去重尽量规避重复的席位。
            平均收益率_list = list(set(平均收益率_list))
            # 计算平均收益率
            平均收益率 = sum(平均收益率_list) / len(平均收益率_list)
            # logger.info(f"{code_id_to_name[int(股票代码)]} {上榜原因} {平均收益率} 买入家数：{len(平均收益率_list)}")
            if type(stock_code_平均收益率[股票代码]) == float \
                    and 平均收益率 > stock_code_平均收益率[股票代码]:
                stock_code_平均收益率[股票代码] = 平均收益率
            elif type(stock_code_平均收益率[股票代码]) != float:
                stock_code_平均收益率[股票代码] = 平均收益率
            if len(平均收益率_list) > 2 and 平均收益率 > 平均收益率_阈值:
                stock_code.add(int(股票代码))
    单个营业部高胜率 = {}
    平均营业部高胜率 = {}
    for data_row in latest_date_data:
        if data_row['营业部id'] in top_营业部:
            if code_id_to_name[int(data_row['股票代码'])] in 单个营业部高胜率 \
                    and 单个营业部高胜率[code_id_to_name[int(data_row['股票代码'])]]['营业部最高收益率'] < \
                    结果统计[data_row['营业部id']]['平均收益率']:
                单个营业部高胜率[code_id_to_name[int(data_row['股票代码'])]] = {
                    '营业部最高收益率': 结果统计[data_row['营业部id']]['平均收益率'],
                    '营业部平均收益率': stock_code_平均收益率[data_row['股票代码']],
                    '营业部名称': f"{营业部_id_to_name[data_row['营业部id']]}"}
            if code_id_to_name[int(data_row['股票代码'])] not in 单个营业部高胜率:
                单个营业部高胜率[code_id_to_name[int(data_row['股票代码'])]] = {
                    '营业部最高收益率': 结果统计[data_row['营业部id']]['平均收益率'],
                    '营业部平均收益率': stock_code_平均收益率[data_row['股票代码']],
                    '营业部名称': f"{营业部_id_to_name[data_row['营业部id']]}"}
            # logger.warning(
            #     f"单个营业部高胜率 {code_id_to_name[int(data_row['股票代码'])]} {data_row['上榜原因']} {int(data_row['股票代码'])} 入选，营业部：{营业部_id_to_name[data_row['营业部id']]}，买入次数：{结果统计[data_row['营业部id']]['b_count']} 平均收益率：{结果统计[data_row['营业部id']]['平均收益率']} 阵容平均收益率：{stock_code_平均收益率[data_row['股票代码']]}")

    for data_row in latest_date_data:
        if int(data_row['股票代码']) in stock_code:
            平均营业部高胜率[code_id_to_name[int(data_row['股票代码'])]] = stock_code_平均收益率[data_row['股票代码']]
            # logger.warning(
            #     f"平均营业部高胜率 {code_id_to_name[int(data_row['股票代码'])]} {data_row['上榜原因']} {int(data_row['股票代码'])} 入选，营业部：{营业部_id_to_name[data_row['营业部id']]}，买入次数：{结果统计[data_row['营业部id']]['b_count']} 平均收益率：{结果统计[data_row['营业部id']]['平均收益率']} 阵容平均收益率：{stock_code_平均收益率[data_row['股票代码']]}")

    sorted_单个营业部高胜率 = dict(sorted(单个营业部高胜率.items(),
                                          key=lambda x: x[1]['营业部平均收益率'],
                                          reverse=True))
    sorted_平均营业部高胜率 = dict(sorted(平均营业部高胜率.items(), key=lambda x: x[1], reverse=True))

    logger.info(f"{latest_date} 单个营业部高胜率")
    for key, value in sorted_单个营业部高胜率.items():
        logger.info(f"{key} 营业部最高收益率：{value['营业部最高收益率']} 营业部平均收益率：{value['营业部平均收益率']} 营业部名称：{value['营业部名称']}")
    logger.info(f"{latest_date} 平均营业部高胜率")
    top_3_stock_code = []

    for key, value in sorted_平均营业部高胜率.items():
        logger.info(f"{key} 营业部平均收益率：{value}")
        top_3_stock_code.append(name_to_code_id[key])
    stock_code_str = ""
    for code in top_3_stock_code:
        stock_code_str += f"{code} {code_id_to_name[int(code)]} "
    logger.info(f"买入代码：{top_3_stock_code}")
    return top_3_stock_code


if __name__ == '__main__':
    # main(start_date=int((datetime.strptime(str(datetime.now().strftime('%Y%m%d')), "%Y%m%d") - timedelta(days=90)).strftime('%Y%m%d')), latest_date=int(datetime.now().strftime('%Y%m%d')))
    main(start_date=int((datetime.strptime(str(20260703), "%Y%m%d") - timedelta(days=90)).strftime('%Y%m%d')), latest_date=int(20260803))
