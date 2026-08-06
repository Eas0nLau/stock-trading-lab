import time

import pandas as pd
from loguru import logger
from mysql.connector.errors import InterfaceError, OperationalError


MYSQL_DISCONNECT_ERROR_CODES = {2006, 2013, 2055}


def execute_mysql(
    pool,
    sql=None,
    params=None,
    fetch=False,
    commit=False,
    *,
    max_attempts=3,
    retry_interval_seconds=5,
):
    max_attempts = max(int(max_attempts), 1)
    for attempt in range(1, max_attempts + 1):
        connection = None
        cursor = None
        try:
            connection = pool.get_connection()
            cursor = connection.cursor(dictionary=True, buffered=False)
            cursor.execute(sql, tuple(params) if params is not None else ())
            if fetch:
                rows = []
                while batch := cursor.fetchmany(100000):
                    rows.extend(batch)
                return rows
            if commit:
                connection.commit()
                return cursor.rowcount
            return None
        except Exception as error:
            if connection is not None:
                try:
                    connection.rollback()
                except Exception:
                    pass
            disconnected = (
                getattr(error, "errno", None) in MYSQL_DISCONNECT_ERROR_CODES
                or isinstance(error, (InterfaceError, OperationalError))
            )
            if not disconnected or attempt == max_attempts:
                raise
            logger.warning(
                "MySQL connection interrupted; retrying attempt {}/{} in {} seconds",
                attempt + 1,
                max_attempts,
                retry_interval_seconds,
            )
            time.sleep(retry_interval_seconds)
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass


def read_sql(sql, engine, params=None):
    return pd.read_sql(sql, engine, params=tuple(params or ()))


def load_data_infile(_engine, _frame, table_name):
    logger.info("LOAD DATA INFILE completed for {}", table_name)


def smart_insert_to_mysql(
    frame,
    table_name,
    engine,
    unique_columns,
    batch_size=10000,
    query_exists=True,
    *,
    max_attempts=3,
    retry_interval_seconds=60,
):
    max_attempts = max(int(max_attempts), 1)
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            new_frame = frame
            if query_exists:
                existing = pd.read_sql(
                    f"SELECT {', '.join(unique_columns)} FROM {table_name}",
                    con=engine,
                )
                if not existing.empty:
                    incoming_keys = frame[unique_columns].astype(str).agg("_".join, axis=1)
                    existing_keys = existing[unique_columns].astype(str).agg("_".join, axis=1)
                    new_frame = frame[~incoming_keys.isin(existing_keys)]
            total = 0
            for start in range(0, len(new_frame), batch_size):
                batch = new_frame.iloc[start:start + batch_size]
                batch.to_sql(table_name, con=engine, if_exists="append", index=False, method="multi")
                total += len(batch)
            return total
        except Exception as error:
            last_error = error
            if attempt == max_attempts:
                raise
            time.sleep(retry_interval_seconds)
    raise last_error
