import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


@dataclass(frozen=True)
class FrontendCommand:
    args: list[str]
    cwd: Path
    env: dict[str, str] | None
    creation_flags: int = 0


class FrontendProcess:
    def __init__(self):
        self.process: subprocess.Popen | None = None

    @staticmethod
    def build_command(project_root: Path | str, port: int = 8990) -> FrontendCommand:
        root = Path(project_root).resolve()
        front_dir = root / "front"
        if not front_dir.is_dir():
            raise RuntimeError(f"Frontend directory does not exist: {front_dir}")

        if os.name == "nt":
            command = FrontendProcess._build_windows_command(front_dir)
        else:
            npm_path = shutil.which("npm")
            if not npm_path:
                raise RuntimeError("Node.js/npm was not found on PATH")
            command = FrontendCommand(args=[npm_path, "run", "dev"], cwd=front_dir, env=None)

        if port != 8990:
            command.args.extend(["--", "--port", str(port)])
        return command

    @staticmethod
    def _build_windows_command(front_dir: Path) -> FrontendCommand:
        npm_path = shutil.which("npm.cmd")
        if not npm_path:
            npm_path = str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs" / "npm.cmd")
        node_dir = Path(npm_path).parent
        node_path = node_dir / "node.exe"
        npm_cli_path = node_dir / "node_modules" / "npm" / "bin" / "npm-cli.js"
        if not node_path.is_file() or not npm_cli_path.is_file():
            raise RuntimeError("Node.js/npm installation is incomplete or unavailable")

        process_env = os.environ.copy()
        process_env["PATH"] = str(node_dir) + os.pathsep + process_env.get("PATH", "")
        return FrontendCommand(
            args=[str(node_path), str(npm_cli_path), "run", "dev"],
            cwd=front_dir,
            env=process_env,
            creation_flags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def start(self, project_root: Path | str, port: int = 8990) -> subprocess.Popen:
        if self.process is not None and self.process.poll() is None:
            return self.process

        command = self.build_command(project_root, port=port)
        self.process = subprocess.Popen(
            command.args,
            cwd=command.cwd,
            env=command.env,
            shell=False,
            creationflags=command.creation_flags,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
        )
        logger.info("Frontend development server started with PID {}", self.process.pid)
        return self.process

    def stream_output(self) -> None:
        if self.process is None or self.process.stdout is None:
            return
        for line in self.process.stdout:
            logger.info(line.rstrip())

    def stop(self, timeout: float = 5.0) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=timeout)
