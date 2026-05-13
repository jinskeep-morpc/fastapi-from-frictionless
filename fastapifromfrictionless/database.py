# build the database.py file for sqlmodel
import logging
from os import PathLike
from pathlib import Path

import jinja2

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = jinja2.Environment(
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


class database:
    _database_logger = logging.getLogger(__name__).getChild(__qualname__)

    def __init__(self, folder):
        self.folder = folder
        self.logger = logging.getLogger(__name__).getChild(self.__class__.__name__).getChild(folder)
        self.logger.info(f"Building database from schemas in folder {folder}")

    def build(self, db_filepath: str | PathLike):
        template = _env.get_template("database.py.jinja2")
        self.database = template.render(db_filepath=str(db_filepath))
        return self

    def save(self, filepath: str | PathLike):
        self.logger.info(f"Saving database file to {filepath}")
        with open(filepath, "w") as file:
            file.write(self.database)
