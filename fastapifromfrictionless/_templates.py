"""Shared Jinja2 environment for the code generators."""

from pathlib import Path

import jinja2

_TEMPLATES_DIR = Path(__file__).parent / "templates"

env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    variable_start_string="<<",
    variable_end_string=">>",
    block_start_string="<%",
    block_end_string="%>",
    comment_start_string="<#",
    comment_end_string="#>",
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)
