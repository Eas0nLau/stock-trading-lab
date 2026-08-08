def assert_no_incomplete_migration(*, settings=None, query=None):
    if query is None:
        from .client import create_database_client

        query = create_database_client(settings).query
    rows = query(
        "SELECT `status` FROM `migration_validations` WHERE `validation_version`=%s",
        params=("002_parity_v1",),
        fetch=True,
    )
    if rows and rows[0].get("status") != "succeeded":
        status = rows[0].get("status") or "unknown"
        raise RuntimeError(f"Migration 002 is incomplete: {status}")
