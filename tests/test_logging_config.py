"""Unit tests for configure_logging."""

import logging
import sys

import pytest

from fastapifromfrictionless import configure_logging

PKG = "fastapifromfrictionless"


def test_default_level_is_info():
    configure_logging()
    assert logging.getLogger(PKG).level == logging.INFO


def test_debug_level_accepted():
    configure_logging("DEBUG")
    assert logging.getLogger(PKG).level == logging.DEBUG


def test_integer_level_accepted():
    configure_logging(logging.WARNING)
    assert logging.getLogger(PKG).level == logging.WARNING


def test_exactly_one_handler_after_call():
    configure_logging()
    assert len(logging.getLogger(PKG).handlers) == 1


def test_repeated_calls_do_not_stack_handlers():
    configure_logging()
    configure_logging()
    configure_logging()
    assert len(logging.getLogger(PKG).handlers) == 1


def test_handler_writes_to_stderr():
    configure_logging()
    handler = logging.getLogger(PKG).handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stderr


def test_propagate_is_false():
    configure_logging()
    assert logging.getLogger(PKG).propagate is False


def test_unknown_level_raises():
    with pytest.raises(ValueError):
        configure_logging("NOTLEVEL")


def test_case_insensitive_level():
    configure_logging("debug")
    assert logging.getLogger(PKG).level == logging.DEBUG
