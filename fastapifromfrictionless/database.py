# build the database.py file for sqlmodel
import logging
from os import PathLike

logger = logging.getLogger(__name__)

class database():
    _database_logger = logging.getLogger(__name__).getChild(__qualname__)
    def __init__(self, folder):

        self.folder = folder
        self.logger = logging.getLogger(__name__).getChild(self.__class__.__name__).getChild(folder)

        self.logger.info(f"Building database from schemas in folder {folder}")

    def build(self, db_filepath: str | PathLike):
        self.database = f"""
from sqlmodel import SQLModel, create_engine

sqlite_filename = '{db_filepath}'
sqlite_url = f"sqlite:///{{sqlite_filename}}"

connect_args = {{'check_same_thread': False}}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
"""
        return self

    def save(self, filepath: str | PathLike):

        self.logger.info(f"Saving database file to {filepath}")
        with open(filepath, 'w') as file:
            file.write(self.database)