import time

from loguru import logger
from mysql.connector.errors import DatabaseError
from mysql.connector.pooling import MySQLConnectionPool
from sqlalchemy import create_engine

import config

connect_error_sleep_times = 5

connection_string = (
    f"mysql+pymysql://{config.mysql_localhost_user}:{config.mysql_localhost_password}@{config.mysql_localhost_host}:{config.mysql_localhost_port}/{config.mysql_localhost_database}"
    '?charset=utf8mb4'
    '&local_infile=1'
)
engine = create_engine(connection_string)


def load_mysql_localhost_pool():
    while True:
        try:
            # logger.info(f"mysql_localhost_pool 加载开始")
            # 初始化连接池
            mysql_localhost_pool = MySQLConnectionPool(pool_name="localhost",
                                                       pool_size=10,
                                                       **{
                                                           "port": config.mysql_localhost_port,
                                                           "host": config.mysql_localhost_host,
                                                           "user": config.mysql_localhost_user,
                                                           "password": config.mysql_localhost_password,
                                                           "database": config.mysql_localhost_database
                                                       })
            # logger.info(f"mysql_localhost_pool 加载成功")
            return mysql_localhost_pool
        except DatabaseError as e:
            logger.error(f"mysql_localhost_pool 连接失败: {e}")
            logger.error(f"睡眠：{connect_error_sleep_times}秒后重试")
            time.sleep(connect_error_sleep_times)
        except Exception as e:
            logger.error(f"mysql_localhost_pool 初始化失败: {e}")
            logger.error(f"睡眠：{connect_error_sleep_times}秒后重试")
            time.sleep(connect_error_sleep_times)
