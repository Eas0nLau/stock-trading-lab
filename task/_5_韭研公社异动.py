"""Compatibility wrapper for canonical Jiuyan collection services."""

from stock_lab.jobs.jiuyan_compatibility import run_cli as _run_cli
from stock_lab.modules.market_data.jiuyan import (
    collect_jiuyan_actions as _collect_jiuyan_actions,
    format_page_date as _format_page_date,
    parse_response as _parse_response,
    wait_for_request_slot as _wait_for_request_slot,
)
from stock_lab.modules.market_data.jiuyan_exports import (
    export_jiuyan_actions as _export_jiuyan_actions,
    front_rank_summary as _front_rank_summary,
)


def 等待请求频率():
    return _wait_for_request_slot()


def 格式化页面日期(date):
    return _format_page_date(date)


def 解析异动响应(response, date):
    return _parse_response(response, date)


def 韭研公社异动采集(date):
    return _collect_jiuyan_actions(date)


def 导出韭研公社异动板块(date):
    return _export_jiuyan_actions(date)


def 日内前排(date=None):
    return _front_rank_summary(date)


def _cli(argv=None):
    return _run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(_cli())
