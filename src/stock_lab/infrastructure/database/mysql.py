from dataclasses import dataclass


@dataclass
class MysqlResources:
    url: str
    connection_options: dict
    engine: object | None = None
    pool: object | None = None

    @classmethod
    def from_settings(cls, settings) -> "MysqlResources":
        mysql = settings.mysql
        url = (
            f"mysql+pymysql://{mysql.user}:{mysql.password}@"
            f"{mysql.host}:{mysql.port}/{mysql.database}"
            "?charset=utf8mb4&local_infile=1"
        )
        return cls(
            url=url,
            connection_options={
                "host": mysql.host,
                "port": mysql.port,
                "user": mysql.user,
                "password": mysql.password,
                "database": mysql.database,
            },
        )

    def get_engine(self):
        if self.engine is None:
            from sqlalchemy import create_engine

            self.engine = create_engine(self.url)
        return self.engine

    def get_pool(self):
        if self.pool is None:
            from mysql.connector.pooling import MySQLConnectionPool

            self.pool = MySQLConnectionPool(
                pool_name="stock_lab",
                pool_size=10,
                **self.connection_options,
            )
        return self.pool


class LazyMysqlPool:
    def __init__(self, resources: MysqlResources):
        self._resources = resources

    def get_connection(self):
        return self._resources.get_pool().get_connection()
