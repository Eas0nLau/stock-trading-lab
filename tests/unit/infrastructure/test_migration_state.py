import pytest

from stock_lab.infrastructure.database.migration_state import assert_no_incomplete_migration


@pytest.mark.parametrize("status", ["running", "failed"])
def test_incomplete_migration_state_is_rejected(status):
    query = lambda *_args, **_kwargs: [{"status": status}]

    with pytest.raises(RuntimeError, match=f"incomplete: {status}"):
        assert_no_incomplete_migration(query=query)


def test_succeeded_or_absent_migration_state_is_accepted():
    assert_no_incomplete_migration(query=lambda *_args, **_kwargs: [{"status": "succeeded"}])
    assert_no_incomplete_migration(query=lambda *_args, **_kwargs: [])
