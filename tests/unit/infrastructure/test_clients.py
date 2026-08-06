from types import SimpleNamespace

from stock_lab.infrastructure.cache.redis_client import create_redis_client
from stock_lab.infrastructure.database.mysql import LazyMysqlPool, MysqlResources


def fake_settings():
    return SimpleNamespace(
        redis=SimpleNamespace(host="cache.internal", port=6381, database=2),
        mysql=SimpleNamespace(
            host="db.internal",
            port=4406,
            user="stock_user",
            password="secret",
            database="stocks",
        ),
    )


def test_redis_factory_builds_client_without_ping():
    client = create_redis_client(fake_settings())

    assert client.connection_pool.connection_kwargs["host"] == "cache.internal"
    assert client.connection_pool.connection_kwargs["port"] == 6381
    assert client.connection_pool.connection_kwargs["db"] == 2


def test_mysql_resources_builds_connection_url_without_connecting():
    resources = MysqlResources.from_settings(fake_settings())

    assert resources.url == "mysql+pymysql://stock_user:secret@db.internal:4406/stocks?charset=utf8mb4&local_infile=1"
    assert resources.engine is None
    assert resources.pool is None


def test_lazy_mysql_pool_only_creates_pool_on_first_connection():
    class FakeResources:
        calls = 0

        def get_pool(self):
            self.calls += 1
            return SimpleNamespace(get_connection=lambda: "connection")

    resources = FakeResources()
    lazy_pool = LazyMysqlPool(resources)

    assert resources.calls == 0
    assert lazy_pool.get_connection() == "connection"
    assert resources.calls == 1
