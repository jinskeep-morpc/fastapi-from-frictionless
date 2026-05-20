# build the database.py file for sqlmodel
import logging
from os import PathLike

from ._templates import env as _env

logger = logging.getLogger(__name__)


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
