import importlib

import dotenv
import pytest


ENV_KEYS = (
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DATABASE",
    "TUSHARE_TOKENS",
    "DEEPSEEK_API_KEY",
    "TDX_ROOT",
)


def _reload_config(monkeypatch, **values):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *_args, **_kwargs: False)
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    import config

    return importlib.reload(config)


def test_config_reads_environment_and_parses_token_list(monkeypatch):
    config = _reload_config(
        monkeypatch,
        MYSQL_HOST="db.internal",
        MYSQL_PORT="4406",
        MYSQL_USER="stock_user",
        MYSQL_PASSWORD="secret-password",
        MYSQL_DATABASE="stocks",
        TUSHARE_TOKENS=" token-a,token-b, ,",
        DEEPSEEK_API_KEY="sk-test",
        TDX_ROOT=r"D:\tdx",
    )

    assert config.mysql_localhost_host == "db.internal"
    assert config.mysql_localhost_port == 4406
    assert config.mysql_localhost_user == "stock_user"
    assert config.mysql_localhost_password == "secret-password"
    assert config.mysql_localhost_database == "stocks"
    assert config.ts_token == "token-a"
    assert config.ts_token_list == ["token-a", "token-b"]
    assert config.deepseek_api_key == "sk-test"
    assert config.tdx_root == r"D:\tdx"


def test_optional_integrations_can_be_unconfigured(monkeypatch):
    config = _reload_config(
        monkeypatch,
        MYSQL_HOST="localhost",
        MYSQL_PORT="3306",
        MYSQL_USER="root",
        MYSQL_PASSWORD="root",
        MYSQL_DATABASE="stock_trading_lab",
    )

    assert config.ts_token == ""
    assert config.ts_token_list == []
    assert config.deepseek_api_key == ""
    assert config.tdx_root == ""


@pytest.mark.parametrize(
    "missing_key",
    ["MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"],
)
def test_mysql_environment_is_required(monkeypatch, missing_key):
    values = {
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "root",
        "MYSQL_PASSWORD": "root",
        "MYSQL_DATABASE": "stock_trading_lab",
    }
    values.pop(missing_key)

    with pytest.raises(RuntimeError, match=missing_key):
        _reload_config(monkeypatch, **values)


def test_mysql_port_must_be_an_integer(monkeypatch):
    with pytest.raises(RuntimeError, match="MYSQL_PORT"):
        _reload_config(
            monkeypatch,
            MYSQL_HOST="localhost",
            MYSQL_PORT="not-a-port",
            MYSQL_USER="root",
            MYSQL_PASSWORD="root",
            MYSQL_DATABASE="stock_trading_lab",
        )
