import importlib

import dotenv
import pytest


REQUIRED_ENV = {
    "MYSQL_HOST": "db.internal",
    "MYSQL_PORT": "4406",
    "MYSQL_USER": "stock_user",
    "MYSQL_PASSWORD": "secret-password",
    "MYSQL_DATABASE": "stocks",
}


def set_required_env(monkeypatch, **overrides):
    values = REQUIRED_ENV | overrides
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_settings_from_env_parses_required_and_optional_values(monkeypatch):
    from stock_lab.config.settings import Settings

    set_required_env(
        monkeypatch,
        TUSHARE_TOKENS=" token-a,token-b, ,",
        DEEPSEEK_API_KEY="sk-test",
        TDX_ROOT=r"D:\tdx",
    )

    settings = Settings.from_env(load_file=False)

    assert settings.mysql.host == "db.internal"
    assert settings.mysql.port == 4406
    assert settings.mysql.user == "stock_user"
    assert settings.mysql.password == "secret-password"
    assert settings.mysql.database == "stocks"
    assert settings.tushare_tokens == ("token-a", "token-b")
    assert settings.deepseek_api_key == "sk-test"
    assert settings.tdx_root == r"D:\tdx"


def test_settings_rejects_missing_mysql_environment(monkeypatch):
    from stock_lab.config.settings import Settings

    for name in REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError, match="MYSQL_HOST"):
        Settings.from_env(load_file=False)


def test_legacy_config_projects_new_settings(monkeypatch):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *_args, **_kwargs: False)
    set_required_env(monkeypatch)

    import config

    legacy = importlib.reload(config)

    assert legacy.mysql_localhost_host == "db.internal"
    assert legacy.mysql_localhost_port == 4406
    assert legacy.mysql_localhost_user == "stock_user"
    assert legacy.mysql_localhost_database == "stocks"
