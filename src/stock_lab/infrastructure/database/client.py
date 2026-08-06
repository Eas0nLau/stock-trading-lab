from dataclasses import dataclass

from stock_lab.config import get_settings

from .mysql import MysqlResources


@dataclass
class DatabaseClient:
    resources: MysqlResources

    @property
    def engine(self):
        return self.resources.get_engine()

    def query(self, sql=None, params=None, fetch=False, commit=False):
        connection = self.resources.get_pool().get_connection()
        cursor = connection.cursor(dictionary=True, buffered=False)
        try:
            cursor.execute(sql, tuple(params or ()))
            if fetch:
                rows = []
                while batch := cursor.fetchmany(100000):
                    rows.extend(batch)
                return rows
            if commit:
                connection.commit()
                return cursor.rowcount
            return None
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()


def create_database_client(settings=None):
    return DatabaseClient(MysqlResources.from_settings(settings or get_settings()))
