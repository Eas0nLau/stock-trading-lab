# uv Project Setup Design

## Goal

Make `pyproject.toml` and `uv.lock` the authoritative Python environment definition before changing application behavior.

## Project Metadata

- Project name: `stock-trading-lab`
- Initial local version: `0.1.0`
- Python requirement: `>=3.12,<3.13`
- The repository is an application rather than an installable Python package, so uv package installation is disabled.

## Dependency Model

All existing pinned requirements will move into PEP 621 metadata while preserving their versions. The unavailable `DrissionPage==4.1.1.2` pin will be replaced with the verified available patch release `DrissionPage==4.1.1.4`.

Runtime libraries will live in `project.dependencies`. Development-only tools will live in the `dev` dependency group:

- `pytest`
- `pytest-timeout`
- `pandas-stubs`
- `pip-chill`

`uv.lock` will lock the complete transitive environment. `uv sync` will create the repository `.venv` from that lock.

## requirements.txt Compatibility

After the uv environment resolves successfully, `requirements.txt` will be regenerated as UTF-8 from the uv lock. This keeps a conventional pip installation entry point without maintaining a second independent dependency list.

## Workflow

1. Create `pyproject.toml` with project metadata, pinned runtime dependencies, the dev dependency group, and `tool.uv.package = false`.
2. Run `uv lock` and require successful dependency resolution.
3. Run `uv sync` and verify the `.venv` uses Python 3.12.
4. Export the lock to `requirements.txt` in UTF-8.
5. Verify imports for the backend core modules and database clients.
6. Proceed to the separately approved optional-task implementation.

## Success Criteria

- `uv lock` completes without dependency conflicts.
- `uv sync` installs the locked environment into `.venv`.
- `uv run python --version` reports Python 3.12.
- The exported requirements contain DrissionPage 4.1.1.4 and are parseable as UTF-8.
- MySQL, Redis, and real-time API modules import successfully from the project environment.
