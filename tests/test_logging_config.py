"""Tests for configure_logging."""

import logging

import pytest

from fastapifromfrictionless.logging_config import configure_logging

PKG = "fastapifromfrictionless"


def teardown_function():
    """Reset the package logger after each test."""
    pkg = logging.getLogger(PKG)
    pkg.handlers.clear()
    pkg.setLevel(logging.WARNING)
    pkg.propagate = True


def test_sets_info_level_by_default():
    configure_logging()
    assert logging.getLogger(PKG).level == logging.INFO


def test_sets_debug_level():
    configure_logging("DEBUG")
    assert logging.getLogger(PKG).level == logging.DEBUG


def test_sets_level_by_integer():
    configure_logging(logging.ERROR)
    assert logging.getLogger(PKG).level == logging.ERROR


def test_adds_stream_handler():
    configure_logging()
    handlers = logging.getLogger(PKG).handlers
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.StreamHandler)


def test_repeated_calls_replace_handler():
    configure_logging("DEBUG")
    configure_logging("INFO")
    assert len(logging.getLogger(PKG).handlers) == 1
    assert logging.getLogger(PKG).level == logging.INFO


def test_propagate_disabled():
    configure_logging()
    assert logging.getLogger(PKG).propagate is False


def test_invalid_level_raises():
    with pytest.raises(ValueError, match="Unknown log level"):
        configure_logging("VERBOSE")


def test_case_insensitive_level():
    configure_logging("debug")
    assert logging.getLogger(PKG).level == logging.DEBUG
