# Environment-Driven Service Configuration Design

## Goal

Remove deployment-specific MySQL, Redis, backend, frontend, and local service addresses from active project code. Use the project-root `.env` as the single operator-owned configuration source while keeping secrets out of Git.

## Scope

- MySQL connection and Docker port/database settings.
- Redis connection, Windows service name, Docker port, and persistence directory.
- FastAPI bind host and port.
- Vite bind host, port, and backend proxy target.
- Frontend process launcher and browser initialization URL.
- Windows startup script service names.
- Removal of the empty Analysis navigation entry and component.
- A repository text/EOL policy that prevents false dirty worktrees on Windows.

External provider URLs for EastMoney, Tonghuashun, Jiuyan, DeepSeek, and other market-data services remain outside this change.

## Configuration Contract

The root `.env.example` documents these deployment variables:

```dotenv
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=change-me
MYSQL_DATABASE=stock_trading_lab
MYSQL_SERVICE_NAME=MySQL80

REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DATABASE=0
REDIS_SERVICE_NAME=Redis
REDIS_DATA_DIR=./data

APP_HOST=0.0.0.0
APP_PORT=8527
FRONTEND_HOST=0.0.0.0
FRONTEND_PORT=9527
FRONTEND_PROXY_TARGET=http://127.0.0.1:8527
INIT_URL=http://localhost:9527
```

The ignored local `.env` receives the same non-secret variables using the currently running local services and ports. Existing MySQL credentials and integration secrets are preserved unchanged.

## Python Configuration

`stock_lab.config.Settings` owns typed server and Windows-service values. Ports are positive integers; required MySQL values remain required. `app.py`, `front_run.py`, and `FrontendProcess` consume `Settings` instead of literals. Compatibility exports remain unchanged unless a new export is needed by an existing caller.

`APP_HOST` controls the Uvicorn bind address. `FRONTEND_HOST` controls Vite binding. Public browser navigation remains controlled separately by `INIT_URL` so bind addresses such as `0.0.0.0` are never used as browser destinations.

## Vite And Frontend

`front/vite.config.js` loads the root `.env` with Vite's `loadEnv`. It validates numeric frontend ports and uses `FRONTEND_PROXY_TARGET` for `/api`. The Python frontend launcher passes the configured port and host explicitly, so direct Vite startup and Python-managed startup share the same values.

The empty `Analysis.vue` route is not a functional feature. Its header button, import, dispatch branch, and component file are removed rather than replaced with a placeholder.

## Docker And Startup

MySQL and Redis compose files substitute root environment values for host-exposed ports and database names. Redis persistence uses `REDIS_DATA_DIR`; `./data` is the documented local default. Compose files do not contain drive-letter paths.

`启动项目.ps1` parses non-secret service-name variables from the root `.env` before checking Windows services. Defaults are retained only for service names when older local `.env` files omit them.

## Repository Hygiene

`.gitattributes` defines text files as LF in the repository while leaving existing Git LFS binary rules unchanged. The implementation must not create a broad content-normalization commit; only files intentionally edited by this change are staged.

## Testing

- Settings tests cover all new variables, defaults, and invalid ports.
- Frontend process tests verify configured host/port arguments.
- Static contracts verify Vite and compose files contain environment substitutions and no local drive path.
- Frontend contracts verify the Analysis entry and component are absent.
- Run `npm test`, `npm run build`, and the complete Python suite.
- Verify live MySQL and Redis connectivity using the local `.env` without printing credentials.

Docker runtime validation is conditional on the Docker CLI being available. YAML/static compose contracts remain mandatory when Docker is absent.
