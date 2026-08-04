import time
import traceback

import pandas as pd
from loguru import logger
from mysql.connector.errors import InterfaceError, OperationalError

from utils import mysql_base, redis_base

redis_con_localhost = redis_base.redis_con_localhost

# 初始化连接池
mysql_localhost_pool = mysql_base.load_mysql_localhost_pool()
engine = mysql_base.engine

# MySQL 服务重启、空闲连接超时等情况对应的常见断连错误码
MYSQL_DISCONNECT_ERROR_CODES = {2006, 2013, 2055}
MYSQL_MAX_RETRIES = 3
MYSQL_RETRY_INTERVAL_SECONDS = 5


def mysql_localhost(sql=None, params: tuple = None, fetch: bool = False, commit: bool = False):
    """执行本地 MySQL 语句，断连时自动获取新连接后有限重试。"""
    for attempt in range(1, MYSQL_MAX_RETRIES + 1):
        cnx = None
        cursor = None
        try:
            # 不长期持有池中连接，避免复用已经被 MySQL 回收的连接。
            cnx = mysql_localhost_pool.get_connection()
            cursor = cnx.cursor(dictionary=True, buffered=False)

            if params is not None:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            if fetch:
                result = []
                while True:
                    rows = cursor.fetchmany(100000)
                    if not rows:
                        break
                    result.extend(rows)
                return result

            if commit:
                cnx.commit()
                return cursor.rowcount
            return None
        except Exception as e:
            if cnx is not None:
                try:
                    cnx.rollback()
                except Exception:
                    # 连接已经断开时，回滚本身也可能失败。
                    pass

            error_code = getattr(e, "errno", None)
            is_disconnect_error = (
                error_code in MYSQL_DISCONNECT_ERROR_CODES
                or isinstance(e, (InterfaceError, OperationalError))
            )

            logger.error(f"MySQL 执行失败（第 {attempt}/{MYSQL_MAX_RETRIES} 次）")
            logger.error(sql)
            logger.error(e)

            if not is_disconnect_error or attempt == MYSQL_MAX_RETRIES:
                logger.error(traceback.format_exc())
                raise

            logger.warning(
                f"MySQL 连接已中断，{MYSQL_RETRY_INTERVAL_SECONDS} 秒后使用新连接重试"
            )
            time.sleep(MYSQL_RETRY_INTERVAL_SECONDS)
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if cnx is not None:
                try:
                    # 池连接的 close() 会把连接归还连接池。
                    cnx.close()
                except Exception:
                    pass


def load_data_infile(db_engine, df, table_name):
    """使用LOAD DATA INFILE（最高效）"""
    # # 保存为CSV
    # temp_file_path = f"{config.project_path}\\data\\temp_{table_name}.csv"
    # logger.info(f"保存为CSV {table_name} {temp_file_path}")
    # df.to_csv(temp_file_path, index=False, header=False)
    # logger.info(f"保存为CSV {table_name} 成功")
    #
    # # 执行LOAD DATA INFILE
    # logger.info(f"执行LOAD DATA INFILE {table_name}")
    # load_sql = f"""
    # LOAD DATA LOCAL INFILE '{temp_file_path}'
    # INTO TABLE {table_name}
    # FIELDS TERMINATED BY ','
    # LINES TERMINATED BY '\n'
    # """
    # with db_engine.connect() as conn:
    #     conn.execute(load_sql)

    # cnx = mysql_localhost_pool.get_connection()
    # cursor = cnx.cursor()
    #
    # # 执行LOAD DATA LOCAL INFILE
    # load_sql = f"""
    # LOAD DATA LOCAL INFILE '{temp_file_path}'
    # INTO TABLE {table_name}
    # FIELDS TERMINATED BY ','
    # LINES TERMINATED BY '\n'
    # """
    #
    # cursor.execute(load_sql)
    # cnx.commit()
    logger.info(f"执行LOAD DATA INFILE {table_name} 成功")


def smart_insert_to_mysql(df, table_name, dn_engine, unique_columns, batch_size=10000, query_exists=True):
    """
    智能插入：存在则不插入，不存在则插入
    """
    try:
        if query_exists:
            # 读取现有的唯一键值
            unique_query = f"SELECT {', '.join(unique_columns)} FROM {table_name}"
            existing_df = pd.read_sql(unique_query, con=dn_engine)

            if not existing_df.empty:
                # 创建唯一标识符
                df['unique_id'] = df[unique_columns].astype(str).agg('_'.join, axis=1)
                existing_df['unique_id'] = existing_df[unique_columns].astype(str).agg('_'.join, axis=1)

                # 过滤出新数据
                new_df = df[~df['unique_id'].isin(existing_df['unique_id'])]
                new_df = new_df.drop('unique_id', axis=1)
            else:
                new_df = df
        else:
            new_df = df

        # 批量插入
        if not new_df.empty:
            # load_data_infile(dn_engine, new_df, table_name)
            total_inserted = 0
            for i in range(0, len(new_df), batch_size):
                batch_df = new_df.iloc[i:i + batch_size]
                batch_df.to_sql(table_name, con=dn_engine, if_exists='append', index=False,
                                method='multi'  # 启用批量插入
                                )
                total_inserted += len(batch_df)
                logger.info(f"已写入 {total_inserted} 新增 {len(new_df)} 总数 {len(df)}")

            logger.info(f"已写入 {total_inserted} 条新记录 总数 {len(df)}")
            return total_inserted
        else:
            logger.info("没有需要插入的新记录")
            return 0

    except Exception as e:
        logger.error(f"插入失败: {e}")
        logger.error(f"插入失败: {traceback.format_exc()}")
        logger.error(f"睡眠60秒后重试插入")
        time.sleep(60)
        smart_insert_to_mysql(df, table_name, dn_engine, unique_columns, batch_size=batch_size, query_exists=query_exists)
