from dataclasses import dataclass

from stock_lab.config import get_settings

from .mysql import MysqlResources
from .operations import execute_mysql


@dataclass
class DatabaseClient:
    resources: MysqlResources

    @property
    def engine(self):
        return self.resources.get_engine()

    def query(self, sql=None, params=None, fetch=False, commit=False):
        return execute_mysql(
            self.resources.get_pool(),
            sql,
            params=params,
            fetch=fetch,
            commit=commit,
        )


def create_database_client(settings=None):
    return DatabaseClient(MysqlResources.from_settings(settings or get_settings()))
