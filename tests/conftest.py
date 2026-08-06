import os


TEST_ENV_DEFAULTS = {
    "MYSQL_HOST": "127.0.0.1",
    "MYSQL_PORT": "3306",
    "MYSQL_USER": "test_user",
    "MYSQL_PASSWORD": "test_password",
    "MYSQL_DATABASE": "stock_trading_lab_test",
}

for name, value in TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(name, value)
