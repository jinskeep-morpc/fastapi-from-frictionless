import logging
import sys

_DEFAULT_FMT = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%dT%H:%M:%S"

_pkg_logger = logging.getLogger("fastapifromfrictionless")


def configure_logging(
    level: str | int = "INFO",
    fmt: str = _DEFAULT_FMT,
    datefmt: str = _DEFAULT_DATEFMT,
) -> None:
    """Configure the fastapifromfrictionless package logger.

    Sets the log level, clears any existing handlers, and attaches a
    StreamHandler to stderr. Sets propagate=False so that the package's
    log records do not bubble up to the root logger.
    """
    if isinstance(level, str):
        numeric = logging.getLevelName(level.upper())
        if not isinstance(numeric, int):
            raise ValueError(f"Unknown log level: {level!r}")
        level = numeric

    _pkg_logger.handlers.clear()
    _pkg_logger.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    _pkg_logger.addHandler(handler)
    _pkg_logger.propagate = False
