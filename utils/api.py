import baostock as bs
from loguru import logger


def bs_login():
    lg = bs.login()
    if lg.error_code == '0':
        logger.info("baostock登录成功")
    else:
        logger.error("baostock登录失败")
        # exit()


bs_login()
