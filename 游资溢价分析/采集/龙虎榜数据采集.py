from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup
from loguru import logger
from tqdm import tqdm

from utils import db


headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36',
    'Accept': '*/*',
    'X-Requested-With': 'XMLHttpRequest',
    'Host': 'data.10jqka.com.cn',
    'Referer': 'http://data.10jqka.com.cn/market/longhu/',
    'Connection': 'keep-alive'
}


def main(date):
    distinct_trade_date = db.mysql_localhost(sql=f"""
        select distinct trade_date FROM stock_daily
        where trade_date >= {date}
        order by trade_date asc
    """, fetch=True)
    t_龙虎榜_data_list = []
    t_龙虎榜_营业部_上榜历史数据_data_list = []
    营业部_list = []
    营业部id_set = set()
    for target_date in tqdm(distinct_trade_date):
        trade_date = target_date['trade_date']
        range_date = datetime.strptime(str(trade_date), '%Y%m%d').strftime("%Y-%m-%d")
        url = f'http://data.10jqka.com.cn/ifmarket/lhbggxq/report/{range_date}/'
        logger.info(f"{url}")
        response = requests.get(
            url,
            headers=headers)
        if '今日龙虎榜暂未公布' in response.text:
            logger.error(f"{range_date} 今日龙虎榜暂未公布")
            continue
        soup = BeautifulSoup(response.text, 'lxml')
        trs = soup.find('div', class_="twrap").find('table', class_='m-table').find_all('tr')
        for tr in trs:
            pass
            tds = tr.find_all('td')
            rid = tds[2].find('a').attrs['rid']

            rid_info = soup.find('div', attrs={'rid': rid})
            p = rid_info.find('p').text
            明细 = p.split('明细：')[1]
            合计买入 = rid_info.find('p', attrs={'style': 'padding: 7px 0;'}).text.split('合计买入：')[1].split("元")[0]
            合计卖出 = rid_info.find('p', attrs={'style': 'padding: 7px 0;'}).text.split('合计卖出：')[1].split("元")[0]
            mt_table = rid_info.find_all('table', class_='m-table m-table-nosort mt10')

            买入_trs = mt_table[0].find_all('tr')
            卖出_trs = mt_table[1].find_all('tr')

            买1营业部id = None
            买1营业部 = None
            买1买入额 = None
            买1卖出额 = None
            买1净额 = None
            买2营业部id = None
            买2营业部 = None
            买2买入额 = None
            买2卖出额 = None
            买2净额 = None
            买3营业部id = None
            买3营业部 = None
            买3买入额 = None
            买3卖出额 = None
            买3净额 = None
            买4营业部id = None
            买4营业部 = None
            买4买入额 = None
            买4卖出额 = None
            买4净额 = None
            买5营业部id = None
            买5营业部 = None
            买5买入额 = None
            买5卖出额 = None
            买5净额 = None

            卖1营业部id = None
            卖1营业部 = None
            卖1买入额 = None
            卖1卖出额 = None
            卖1净额 = None
            卖2营业部id = None
            卖2营业部 = None
            卖2买入额 = None
            卖2卖出额 = None
            卖2净额 = None
            卖3营业部id = None
            卖3营业部 = None
            卖3买入额 = None
            卖3卖出额 = None
            卖3净额 = None
            卖4营业部id = None
            卖4营业部 = None
            卖4买入额 = None
            卖4卖出额 = None
            卖4净额 = None
            卖5营业部id = None
            卖5营业部 = None
            卖5买入额 = None
            卖5卖出额 = None
            卖5净额 = None
            for_index = 0
            for buy_tr in 买入_trs[1:]:
                for_index += 1
                buy_tds = buy_tr.find_all('td')
                if for_index == 1:
                    买1营业部id = buy_tds[0].find('a').attrs['href'].split("code/")[1].split("/")[0] if 'code/' in \
                                                                                                    buy_tds[0].find(
                                                                                                        'a').attrs[
                                                                                                        'href'] else None
                    买1营业部 = buy_tds[0].find('a').attrs['title']
                    买1买入额 = float(buy_tds[1].text)
                    买1卖出额 = float(buy_tds[2].text)
                    买1净额 = float(buy_tds[3].text)
                if for_index == 2:
                    买2营业部id = buy_tds[0].find('a').attrs['href'].split("code/")[1].split("/")[0] if 'code/' in \
                                                                                                    buy_tds[0].find(
                                                                                                        'a').attrs[
                                                                                                        'href'] else None
                    买2营业部 = buy_tds[0].find('a').attrs['title']
                    买2买入额 = float(buy_tds[1].text)
                    买2卖出额 = float(buy_tds[2].text)
                    买2净额 = float(buy_tds[3].text)
                if for_index == 3:
                    买3营业部id = buy_tds[0].find('a').attrs['href'].split("code/")[1].split("/")[0] if 'code/' in \
                                                                                                    buy_tds[0].find(
                                                                                                        'a').attrs[
                                                                                                        'href'] else None
                    买3营业部 = buy_tds[0].find('a').attrs['title']
                    买3买入额 = float(buy_tds[1].text)
                    买3卖出额 = float(buy_tds[2].text)
                    买3净额 = float(buy_tds[3].text)
                if for_index == 4:
                    买4营业部id = buy_tds[0].find('a').attrs['href'].split("code/")[1].split("/")[0] if 'code/' in \
                                                                                                    buy_tds[0].find(
                                                                                                        'a').attrs[
                                                                                                        'href'] else None
                    买4营业部 = buy_tds[0].find('a').attrs['title']
                    买4买入额 = float(buy_tds[1].text)
                    买4卖出额 = float(buy_tds[2].text)
                    买4净额 = float(buy_tds[3].text)
                if for_index == 5:
                    买5营业部id = buy_tds[0].find('a').attrs['href'].split("code/")[1].split("/")[0] if 'code/' in \
                                                                                                    buy_tds[0].find(
                                                                                                        'a').attrs[
                                                                                                        'href'] else None if 'code/' in \
                                                                                                                             buy_tds[
                                                                                                                                 0].find(
                                                                                                                                 'a').attrs[
                                                                                                                                 'href'] else None
                    买5营业部 = buy_tds[0].find('a').attrs['title']
                    买5买入额 = float(buy_tds[1].text)
                    买5卖出额 = float(buy_tds[2].text)
                    买5净额 = float(buy_tds[3].text)
                pass
            for_index = 0
            for sell_tr in 卖出_trs[1:]:
                for_index += 1
                sell_tds = sell_tr.find_all('td')
                if for_index == 1:
                    卖1营业部id = sell_tds[0].find('a').attrs['href'].split("code/")[1].split("/")[0] if 'code/' in \
                                                                                                     sell_tds[0].find(
                                                                                                         'a').attrs[
                                                                                                         'href'] else None
                    卖1营业部 = sell_tds[0].find('a').attrs['title']
                    卖1买入额 = float(sell_tds[1].text)
                    卖1卖出额 = float(sell_tds[2].text)
                    卖1净额 = float(sell_tds[3].text)
                if for_index == 2:
                    卖2营业部id = sell_tds[0].find('a').attrs['href'].split("code/")[1].split("/")[0] if 'code/' in \
                                                                                                     sell_tds[0].find(
                                                                                                         'a').attrs[
                                                                                                         'href'] else None
                    卖2营业部 = sell_tds[0].find('a').attrs['title']
                    卖2买入额 = float(sell_tds[1].text)
                    卖2卖出额 = float(sell_tds[2].text)
                    卖2净额 = float(sell_tds[3].text)
                if for_index == 3:
                    卖3营业部id = sell_tds[0].find('a').attrs['href'].split("code/")[1].split("/")[0] if 'code/' in \
                                                                                                     sell_tds[0].find(
                                                                                                         'a').attrs[
                                                                                                         'href'] else None
                    卖3营业部 = sell_tds[0].find('a').attrs['title']
                    卖3买入额 = float(sell_tds[1].text)
                    卖3卖出额 = float(sell_tds[2].text)
                    卖3净额 = float(sell_tds[3].text)
                if for_index == 4:
                    卖4营业部id = sell_tds[0].find('a').attrs['href'].split("code/")[1].split("/")[0] if 'code/' in \
                                                                                                     sell_tds[0].find(
                                                                                                         'a').attrs[
                                                                                                         'href'] else None
                    卖4营业部 = sell_tds[0].find('a').attrs['title']
                    卖4买入额 = float(sell_tds[1].text)
                    卖4卖出额 = float(sell_tds[2].text)
                    卖4净额 = float(sell_tds[3].text)
                if for_index == 5:
                    卖5营业部id = sell_tds[0].find('a').attrs['href'].split("code/")[1].split("/")[0] if 'code/' in \
                                                                                                     sell_tds[0].find(
                                                                                                         'a').attrs[
                                                                                                         'href'] else None
                    卖5营业部 = sell_tds[0].find('a').attrs['title']
                    卖5买入额 = float(sell_tds[1].text)
                    卖5卖出额 = float(sell_tds[2].text)
                    卖5净额 = float(sell_tds[3].text)
            pass
            info = {
                'data_id': f"{trade_date}_{rid}",
                'date': trade_date,
                'rid': rid,
                '明细': 明细,
                '日期类型': "1日" if tds[0].text.strip() == "" else tds[0].text.strip(),
                '股票代码': tds[1].text.strip(),
                '股票名称': tds[2].text.strip(),
                '现价': tds[3].text.strip(),
                '涨跌幅': tds[4].text.strip(),
                '成交金额': tds[5].text.strip(),
                '净买入额': tds[6].text.strip(),
                '合计买入': 合计买入,
                '合计卖出': 合计卖出,
                '买1营业部id': 买1营业部id,
                '买1营业部': 买1营业部,
                '买1买入额': 买1买入额,
                '买1卖出额': 买1卖出额,
                '买1净额': 买1净额,
                '买2营业部id': 买2营业部id,
                '买2营业部': 买2营业部,
                '买2买入额': 买2买入额,
                '买2卖出额': 买2卖出额,
                '买2净额': 买2净额,
                '买3营业部id': 买3营业部id,
                '买3营业部': 买3营业部,
                '买3买入额': 买3买入额,
                '买3卖出额': 买3卖出额,
                '买3净额': 买3净额,
                '买4营业部id': 买4营业部id,
                '买4营业部': 买4营业部,
                '买4买入额': 买4买入额,
                '买4卖出额': 买4卖出额,
                '买4净额': 买4净额,
                '买5营业部id': 买5营业部id,
                '买5营业部': 买5营业部,
                '买5买入额': 买5买入额,
                '买5卖出额': 买5卖出额,
                '买5净额': 买5净额,
                '卖1营业部id': 卖1营业部id,
                '卖1营业部': 卖1营业部,
                '卖1买入额': 卖1买入额,
                '卖1卖出额': 卖1卖出额,
                '卖1净额': 卖1净额,
                '卖2营业部id': 卖2营业部id,
                '卖2营业部': 卖2营业部,
                '卖2买入额': 卖2买入额,
                '卖2卖出额': 卖2卖出额,
                '卖2净额': 卖2净额,
                '卖3营业部id': 卖3营业部id,
                '卖3营业部': 卖3营业部,
                '卖3买入额': 卖3买入额,
                '卖3卖出额': 卖3卖出额,
                '卖3净额': 卖3净额,
                '卖4营业部id': 卖4营业部id,
                '卖4营业部': 卖4营业部,
                '卖4买入额': 卖4买入额,
                '卖4卖出额': 卖4卖出额,
                '卖4净额': 卖4净额,
                '卖5营业部id': 卖5营业部id,
                '卖5营业部': 卖5营业部,
                '卖5买入额': 卖5买入额,
                '卖5卖出额': 卖5卖出额,
                '卖5净额': 卖5净额,
            }

            for key in info.keys():
                if '营业部id' in key and info[key] and info[key] not in 营业部id_set:
                    营业部_info = {
                        '营业部id': info[key],
                        '营业部名称': info[key.replace("id", "")],
                    }
                    营业部_list.append(营业部_info.values())
                    营业部id_set.add(营业部_info['营业部id'])
            info['成交金额'] = float(info['成交金额'].replace("亿", "")) * 10000 if "亿" in info['成交金额'] \
                else (float(info['成交金额'].replace("万", ""))
                      if "万" in info['成交金额'] else float(info['成交金额'])
                      )
            info['净买入额'] = float(info['净买入额'].replace("亿", "")) * 10000 if "亿" in info['净买入额'] \
                else (float(info['净买入额'].replace("万", ""))
                      if "万" in info['净买入额'] else float(info['净买入额'])
                      )
            info['合计买入'] = float(info['合计买入'].replace("亿", "")) * 10000 if "亿" in info['合计买入'] \
                else (float(info['合计买入'].replace("万", ""))
                      if "万" in info['合计买入'] else float(info['合计买入'])
                      )
            info['合计卖出'] = float(info['合计卖出'].replace("亿", "")) * 10000 if "亿" in info['合计卖出'] \
                else (float(info['合计卖出'].replace("万", ""))
                      if "万" in info['合计卖出'] else float(info['合计卖出'])
                      )
            info['现价'] = float(info['现价'])
            info['涨跌幅'] = float(info['涨跌幅'].replace("%", ""))
            t_龙虎榜_data_list.append(info)
    for row in t_龙虎榜_data_list:
        日期 = row['date']
        股票代码 = row['股票代码']
        股票简称 = row['股票名称']
        明细 = row['明细']
        涨跌幅 = row['涨跌幅']
        pass
        for i in range(1, 6):
            if f'买{i}营业部id' in row and row[f'买{i}营业部id']:
                营业部id = row[f'买{i}营业部id']
                营业部名称 = row[f'买{i}营业部']
                买入额 = row[f'买{i}买入额']
                卖出额 = row[f'买{i}卖出额']
                净额 = row[f'买{i}净额']
                info = {
                    'data_id': f"{营业部id}_{日期}_{股票代码}_{明细}",
                    '营业部id': 营业部id,
                    '营业部名称': 营业部名称,
                    '日期': 日期,
                    '股票简称': 股票简称,
                    '股票代码': 股票代码,
                    '上榜原因': 明细,
                    '涨跌幅': 涨跌幅,
                    '买入额': 买入额,
                    '卖出额': 卖出额,
                    '买卖净额': 净额,
                    '所属板块': None,
                }
                t_龙虎榜_营业部_上榜历史数据_data_list.append(info.values())
            if f'卖{i}营业部id' in row and row[f'卖{i}营业部id']:
                营业部id = row[f'卖{i}营业部id']
                营业部名称 = row[f'卖{i}营业部']
                买入额 = row[f'卖{i}买入额']
                卖出额 = row[f'卖{i}卖出额']
                净额 = row[f'卖{i}净额']
                info = {
                    'data_id': f"{营业部id}_{日期}_{股票代码}_{明细}",
                    '营业部id': 营业部id,
                    '营业部名称': 营业部名称,
                    '日期': 日期,
                    '股票简称': 股票简称,
                    '股票代码': 股票代码,
                    '上榜原因': 明细,
                    '涨跌幅': 涨跌幅,
                    '买入额': 买入额,
                    '卖出额': 卖出额,
                    '买卖净额': 净额,
                    '所属板块': None,
                }
                t_龙虎榜_营业部_上榜历史数据_data_list.append(info.values())

    logger.info("t_龙虎榜 写入开始")
    columns = ['data_id', 'date', 'rid', '明细', '日期类型', '股票代码', '股票名称', '现价', '涨跌幅', '成交金额', '净买入额', '合计买入', '合计卖出',
               '买1营业部id', '买1营业部', '买1买入额', '买1卖出额', '买1净额', '买2营业部id', '买2营业部', '买2买入额', '买2卖出额', '买2净额', '买3营业部id',
               '买3营业部', '买3买入额', '买3卖出额', '买3净额', '买4营业部id', '买4营业部', '买4买入额', '买4卖出额', '买4净额', '买5营业部id', '买5营业部',
               '买5买入额',
               '买5卖出额', '买5净额', '卖1营业部id', '卖1营业部', '卖1买入额', '卖1卖出额', '卖1净额', '卖2营业部id', '卖2营业部', '卖2买入额', '卖2卖出额',
               '卖2净额',
               '卖3营业部id', '卖3营业部', '卖3买入额', '卖3卖出额', '卖3净额', '卖4营业部id', '卖4营业部', '卖4买入额', '卖4卖出额', '卖4净额', '卖5营业部id',
               '卖5营业部', '卖5买入额', '卖5卖出额', '卖5净额']
    df = pd.DataFrame(t_龙虎榜_data_list, columns=columns)
    inserted_count = db.smart_insert_to_mysql(df, 't_龙虎榜', db.engine, ['data_id'])
    logger.info(f"t_龙虎榜 写入成功 插入条数：{inserted_count}")

    logger.info("t_龙虎榜_营业部_全部 写入开始")
    columns = ['营业部id', '营业部名称']
    df = pd.DataFrame(营业部_list, columns=columns)
    inserted_count = db.smart_insert_to_mysql(df, 't_龙虎榜_营业部_全部', db.engine, ['营业部id'])
    logger.info(f"t_龙虎榜_营业部_全部 写入成功 插入条数：{inserted_count}")


    columns = ['data_id', '营业部id', '营业部名称', '日期', '股票简称', '股票代码', '上榜原因', '涨跌幅', '买入额', '卖出额', '买卖净额', '所属板块']
    logger.info("t_龙虎榜_营业部_上榜历史数据 写入开始")
    df = pd.DataFrame(t_龙虎榜_营业部_上榜历史数据_data_list, columns=columns)
    inserted_count = db.smart_insert_to_mysql(df, 't_龙虎榜_营业部_上榜历史数据', db.engine, ['data_id'])
    logger.info(f"t_龙虎榜_营业部_上榜历史数据 写入成功 插入条数：{inserted_count}")
    logger.info("success")


if __name__ == '__main__':
    # 龙虎榜数据开始时间20150301
    main(date=20150301)
