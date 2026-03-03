
from sqlmodel import SQLModel, create_engine

sqlite_filename = 'test.db'
sqlite_url = f"sqlite:///{sqlite_filename}"

connect_args = {'check_same_thread': False}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
