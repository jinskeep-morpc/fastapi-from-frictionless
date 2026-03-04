# build the database.py file for sqlmodel
import logging
from os import PathLike

logger = logging.getLogger(__name__)

class database():
    _database_logger = logging.getLogger(__name__).getChild(__qualname__)
    def __init__(self, filepath):

        self.logger = logging.getLogger(__name__).getChild(self.__class__.__name__).getChild(self.NAME)

        self.logger.info(f"Building database from schema {filepath}")
        self.database = self.build(filepath=filepath)

    def build(self, filepath: str | PathLike):
        database_string = f"""
        from sqlmodel import SQLModel, create_engine

        sqlite_filename = '{filepath}'
        sqlite_url = f"sqlite:///{{sqlite_filename}}"

        connect_args = {{'check_same_thread': False}}
        engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)

        def create_db_and_tables():
            SQLModel.metadata.create_all(engine)
        """
        return database_string

    def save(self, filepath: str | PathLike):

        self.logger.info(f"Saving database file to {filepath}")
        with open(filepath, 'w') as file:
            file.write(self.database)