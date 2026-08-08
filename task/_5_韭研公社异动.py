from stock_lab.modules.market_data.jiuyan import (
    IncompleteJiuyanResponse,
    collect_jiuyan_actions,
    format_page_date,
    parse_response,
    wait_for_request_slot,
)


def 等待请求频率():
    return wait_for_request_slot()


def 格式化页面日期(date):
    return format_page_date(date)


def 解析异动响应(response, date):
    return parse_response(response, date)


def 韭研公社异动采集(date):
    return collect_jiuyan_actions(date)
