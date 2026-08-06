"""Compatibility entry point for the official premarket-summary job."""

from stock_lab.jobs.premarket_summary import run_premarket_summary


def 韭研公社盘前纪要采集(date, **kwargs):
    return run_premarket_summary(date, **kwargs)
