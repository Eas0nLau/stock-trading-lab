from stock_lab.infrastructure.database.operations import (
    execute_mysql,
    load_data_infile,
    read_sql as _read_sql,
    smart_insert_to_mysql,
)
from utils import mysql_base, redis_base


redis_con_localhost = redis_base.redis_con_localhost
mysql_localhost_pool = mysql_base.load_mysql_localhost_pool()
engine = mysql_base.engine


def mysql_localhost(sql=None, params=None, fetch=False, commit=False):
    return execute_mysql(
        mysql_localhost_pool,
        sql,
        params=params,
        fetch=fetch,
        commit=commit,
    )


def read_sql(sql, params=None):
    return _read_sql(sql, engine, params=params)
