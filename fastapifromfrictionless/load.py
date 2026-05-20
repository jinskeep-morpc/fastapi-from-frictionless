"""Backward-compatibility shim. Import from runtime.* or scaffolding instead."""

from .runtime import (
    create_package,
    dump_to_excel,
    empty_excel,
    get_model,
    requests_bulk_post,
    requests_get_all,
    requests_post,
    requests_update,
    update_api_from_package,
)
from .scaffolding import build_database

__all__ = [
    "build_database",
    "create_package",
    "dump_to_excel",
    "empty_excel",
    "get_model",
    "requests_bulk_post",
    "requests_get_all",
    "requests_post",
    "requests_update",
    "update_api_from_package",
]
