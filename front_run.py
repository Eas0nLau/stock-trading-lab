"""Legacy frontend development-server entry point."""

from pathlib import Path

from loguru import logger

from stock_lab.bootstrap.frontend import FrontendProcess


_frontend_process = FrontendProcess()


def run():
    try:
        process = _frontend_process.start(Path(__file__).resolve().parent)
        _frontend_process.stream_output()
        return process
    except RuntimeError as error:
        logger.error("Unable to start frontend: {}", error)
        return None


def stop():
    _frontend_process.stop()
