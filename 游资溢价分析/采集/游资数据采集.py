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
    'Referer': 'http://data.10jqka.com.cn/market/lhbyyb/orgcode/6d1a09895eef9da7/',
    'Connection': 'keep-alive'
}

营业部_list = db.mysql_localhost(f"""
    SELECT x.* FROM t_龙虎榜_营业部_全部 x
""", fetch=True)
columns = ['data_id', '营业部id', '营业部名称', '日期', '股票简称', '股票代码', '上榜原因', '涨跌幅', '买入额', '卖出额', '买卖净额', '所属板块']
data_list = []
for 营业部 in tqdm(营业部_list):
    营业部id = 营业部['营业部id']
    营业部名称 = 营业部['营业部名称']
    Referer = f'http://data.10jqka.com.cn/market/lhbyyb/orgcode/{营业部id}/'
    headers['Referer'] = Referer
    logger.info(f"{营业部id} {营业部名称} {Referer}")
    max_page = None
    for page in tqdm(range(1, 100)):
        pass
        redis_key = f"股票:游资数据采集:{营业部['营业部id']}:{page}"
        if db.redis_con_localhost.exists(redis_key):
            response_text = db.redis_con_localhost.get(redis_key)
        else:
            response = requests.get(
                f"http://data.10jqka.com.cn/ifmarket/lhbhistory/orgcode/{营业部['营业部id']}/field/ENDDATE/order/desc/page/{page}/",
                headers=headers)
            response_text = response.text
            db.redis_con_localhost.set(redis_key, response_text)
        soup = BeautifulSoup(response_text, 'lxml')
        if page == 1:
            try:
                page_info = soup.find('span', class_='page_info').text
                max_page = int(page_info.split("/")[1])
            except:
                max_page = 2
                pass
        if page > max_page:
            break
        logger.info(f"{营业部id} {营业部名称} {page}/{max_page}")
        trs = soup.find('table', class_='m-table m-table-nosort').find_all('tr')
        for tr in trs[1:]:
            tds = tr.find_all('td')
            日期 = tds[0].text.replace("-", "")
            股票代码 = tds[1].find('a').attrs['href'].split("/code/")[1].split("/")[0]
            上榜原因 = tds[2].text
            info = {
                'data_id': f"{营业部id}_{日期}_{股票代码}_{上榜原因}",
                '营业部id': 营业部id,
                '营业部名称': 营业部名称,
                '日期': 日期,
                '股票简称': tds[1].text.strip(),
                '股票代码': 股票代码,
                '上榜原因': tds[2].text,
                '涨跌幅': tds[3].text,
                '买入额': tds[4].text,
                '卖出额': tds[5].text,
                '买卖净额': tds[6].text,
                '所属板块': tds[7].text,
            }
            data_list.append(info.values())
            pass
    # if len(data_list) > 10000:
    #     break
# 将列表转换为DataFrame
df = pd.DataFrame(data_list, columns=columns)
inserted_count = db.smart_insert_to_mysql(df, 't_龙虎榜_营业部_上榜历史数据', db.engine, ['data_id'])
logger.info("success")
