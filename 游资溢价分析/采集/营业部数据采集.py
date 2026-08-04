import pandas as pd
import requests
from bs4 import BeautifulSoup
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

columns = ['营业部id', '营业部名称']
data_list = []
营业部id_set = set()
for page in tqdm(range(1, 11)):
    pass
    type_list = [1, 2, 3]
    for type in type_list:
        desc_asc = ['desc', 'asc']
        for desc_asc in desc_asc:
            tab_list = ['sbcs', 'zjsl', 'btcz']
            for tab in tab_list:
                if tab == 'sbcs':
                    field_list = ['sbcs', 'dyzj', 'nnsbcs', 'nnmrcs', 'nngmcgl']
                if tab == 'zjsl':
                    field_list = ['zgcz', 'zgczje', 'zgmrje', 'dyzj', 'ljmrje']
                if tab == 'btcz':
                    field_list = ['xsjs', 'zjgpcs', 'zjcgl']
                for field in field_list:
                    response = requests.get(
                        f"http://data.10jqka.com.cn/ifmarket/lhbyyb/type/{type}/tab/{tab}/field/{field}/sort/{desc_asc}/page/{page}/",
                        headers=headers)
                    soup = BeautifulSoup(response.text, 'lxml')
                    trs = soup.find('table', class_='m-table').find_all('tr')
                    for tr in trs[1:]:
                        tds = tr.find_all('td')
                        info = {
                            '营业部id': tds[1].find('a').attrs['href'].split("code/")[1].split("/")[0],
                            '营业部名称': tds[1].find('a').attrs['title'],
                        }
                        if info['营业部id'] not in 营业部id_set:
                            data_list.append(info.values())
                            营业部id_set.add(info['营业部id'])
                        if tab == 'btcz':
                            info = {
                                '营业部id': tds[3].find('a').attrs['href'].split("code/")[1].split("/")[0],
                                '营业部名称': tds[3].find('a').attrs['title'],
                            }
                            if info['营业部id'] not in 营业部id_set:
                                data_list.append(info.values())
                                营业部id_set.add(info['营业部id'])
                        pass
# 将列表转换为DataFrame
df = pd.DataFrame(data_list, columns=columns)
inserted_count = db.smart_insert_to_mysql(df, 't_龙虎榜_营业部_全部', db.engine, ['营业部id'])
