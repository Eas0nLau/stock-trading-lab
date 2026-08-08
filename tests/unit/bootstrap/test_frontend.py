from pathlib import Path

import pytest

from stock_lab.bootstrap.frontend import FrontendProcess


def create_windows_node_layout(tmp_path):
    node_dir = tmp_path / "node"
    npm_cli = node_dir / "node_modules" / "npm" / "bin" / "npm-cli.js"
    npm_cli.parent.mkdir(parents=True)
    (node_dir / "node.exe").touch()
    (node_dir / "npm.cmd").touch()
    npm_cli.touch()
    return node_dir


def test_frontend_command_uses_repository_front_directory(monkeypatch, tmp_path):
    front_dir = tmp_path / "front"
    front_dir.mkdir()
    node_dir = create_windows_node_layout(tmp_path)
    monkeypatch.setattr(
        "stock_lab.bootstrap.frontend.shutil.which",
        lambda _name: str(node_dir / "npm.cmd"),
    )

    command = FrontendProcess.build_command(tmp_path)

    assert command.cwd == front_dir
    assert command.args[-2:] == ["run", "dev"]
    assert Path(command.args[0]).name == "node.exe"


def test_missing_npm_raises_clear_error(monkeypatch, tmp_path):
    (tmp_path / "front").mkdir()
    monkeypatch.setattr("stock_lab.bootstrap.frontend.shutil.which", lambda _name: None)
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "missing-program-files"))

    with pytest.raises(RuntimeError, match="Node.js|npm"):
        FrontendProcess.build_command(tmp_path)


def test_missing_front_directory_raises_clear_error(tmp_path):
    with pytest.raises(RuntimeError, match="front"):
        FrontendProcess.build_command(tmp_path)
