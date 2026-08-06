from pathlib import Path

import pytest

from stock_lab.infrastructure.tdx.config import TdxSettings, validate_tdx_root


def test_validate_tdx_root_requires_plugin_entrypoint(tmp_path: Path):
    (tmp_path / "PYPlugins" / "user").mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        validate_tdx_root(tmp_path)


def test_tdx_settings_normalizes_positive_refresh_interval(tmp_path: Path):
    settings = TdxSettings(root=tmp_path, refresh_interval_seconds=3)

    assert settings.root == tmp_path
    assert settings.refresh_interval_seconds == 3.0


def test_tdx_settings_rejects_non_positive_interval(tmp_path: Path):
    with pytest.raises(ValueError, match="positive"):
        TdxSettings(root=tmp_path, refresh_interval_seconds=0)
