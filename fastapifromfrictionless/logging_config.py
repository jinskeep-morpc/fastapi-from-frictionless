"""Logging configuration for fastapifromfrictionless."""

import logging
import sys

_DEFAULT_FMT = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logging(
    level: str | int = "INFO",
    fmt: str = _DEFAULT_FMT,
    datefmt: str = _DEFAULT_DATEFMT,
) -> None:
    """Configure logging for the fastapifromfrictionless package.

    Sets up a StreamHandler on the package root logger so callers do not need
    to configure logging themselves.  Safe to call multiple times — existing
    handlers on the package logger are replaced each call.

    Parameters
    ----------
    level:
        Log level name (``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ``"ERROR"``) or
        an integer constant from the ``logging`` module.  Defaults to ``"INFO"``.
    fmt:
        Log record format string passed to ``logging.Formatter``.
    datefmt:
        Date format string passed to ``logging.Formatter``.
    """
    if isinstance(level, str):
        numeric = _LEVELS.get(level.upper())
        if numeric is None:
            raise ValueError(f"Unknown log level {level!r}. Choose from: {list(_LEVELS)}")
    else:
        numeric = level

    pkg_logger = logging.getLogger("fastapifromfrictionless")
    pkg_logger.setLevel(numeric)

    # Replace existing handlers to avoid duplicate output on repeated calls
    pkg_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(numeric)
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    pkg_logger.addHandler(handler)

    # Prevent log records from bubbling to the root logger if it has its own
    # handlers (avoids duplicate output in applications that configure root).
    pkg_logger.propagate = False
