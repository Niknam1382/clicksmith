"""Logging setup shared by the GUI and the CLI."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from . import paths

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(*, console: bool = False, level: int = logging.INFO) -> None:
    root = logging.getLogger("clicksmith")
    if root.handlers:
        return
    root.setLevel(level)
    try:
        handler = RotatingFileHandler(
            paths.logs_dir() / "clicksmith.log",
            maxBytes=512_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
    except OSError:
        pass  # read-only location: keep running without a log file
    if console and sys.stdout is not None:
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        root.addHandler(stream)
