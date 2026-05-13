import logging
import os

logger = logging.getLogger(__name__)


class app:
    _app_logger = logger.getChild(__qualname__)

    def __init__(self, folder: str | os.PathLike):
        """
        Create a app.py file based on all frictionless schemas in a folder.

        parameters:
        -----------
        folder : str | Pathlike
            The location of the schema files

        """
        import os

        import frictionless

        self.logger = (
            logging.getLogger(__name__).getChild(self.__class__.__name__).getChild(str(folder))
        )

        if not os.path.exists(folder):
            self.logger.error(f"{folder} does not exist.")
            raise ValueError
        else:
            self.folder: str = str(folder)

        self.header = """
# app.py
from fastapi import Depends, FastAPI, HTTPException, Query
import fastapi
from fastapi_querybuilder import QueryBuilder
from sqlalchemy import text
from sqlmodel import Session, select
from .database import create_db_and_tables, engine
from .models import *
from sqlalchemy.ext.asyncio import AsyncSession

# Initiate app
app = FastAPI()

# Dependencies
@app.on_event('startup')
def on_startup():
    create_db_and_tables()

def get_session():
    with Session(engine) as session:
        yield session

# @app.get('/')
# def read_schema(*, session: Session = Depends(get_session)):
#     return {name.lower()}s
"""

        self.schema_paths = [x for x in os.listdir(folder) if x.endswith("schema.yaml")]

    def build(self):
        self.endpoints = []
        for filename in self.schema_paths:
            endpoint = self.build_endpoint(filename)
            self.endpoints.append(endpoint)

        return self

    def build_endpoint(self, filename):
        import frictionless

        filepath = os.path.join(self.folder, filename)
        name = filename.split(".")[0].replace("-", " ").title().replace(" ", "")
        schema = frictionless.Schema(filepath)

        foreign_keys = [x["fields"][0] for x in schema.foreign_keys]

        relationships = []
        for other_filename in self.schema_paths:
            if other_filename != filename:
                other_filepath = os.path.join(self.folder, other_filename)
                other_name = other_filename.split(".")[0].replace("-", " ").title().replace(" ", "")
                other_schema = frictionless.Schema(other_filepath)
                if len(other_schema.foreign_keys) > 0:
                    for fk in other_schema.foreign_keys:
                        if fk["reference"]["resource"] == name.lower():
                            relationships.append(other_name)

        post_string = f"""
# {name} requests
@app.post('/{name.lower()}', response_model={name}Public)
def create_{name.lower()}(*, session: Session = Depends(get_session), {name.lower()}: {name}Create):
    {name.lower()} = {name}.model_validate({name.lower()})
    session.add({name.lower()})
    session.commit()
    session.refresh({name.lower()})
    return {name.lower()}"""

        pk = schema.primary_key[0]

        getall_string = f"""
@app.get('/{name.lower()}/all', response_model=list[{f"{name}PublicWithAll" if ((len(foreign_keys) > 0) | (len(relationships) > 0)) else f"{name}Public"}])
def read_{name.lower()}s(*, session: Session = Depends(get_session)):
    {name.lower()}s = session.exec(select({name})).all()
    return {name.lower()}s"""

        if len(foreign_keys) > 0:
            query_string = f"""
@app.get('/{name.lower()}/query', response_model=list[{name}PublicWithAll])
async def query_{name.lower()}s(*, session: AsyncSession = Depends(get_session), query=QueryBuilder({name})):
    {name.lower()}s = session.execute(query)
    return {name.lower()}s.scalars().all()"""
        else:
            query_string = ""

        get_string = f"""
@app.get('/{name.lower()}/{{{name.lower()}_{pk}}}', response_model={f"{name}PublicWithAll" if ((len(foreign_keys) > 0) | (len(relationships) > 0)) else f"{name}Public"})
def read_{name.lower()}(*, session: Session = Depends(get_session), {name.lower()}_{pk}: str):
    {name.lower()} = session.get({name}, {name.lower()}_{pk})
    if not {name.lower()}:
        raise HTTPException(status_code=404, detail='{name} not found.')
    return {name.lower()}"""

        update_string = f"""
@app.patch('/{name.lower()}/{{{name.lower()}_{pk}}}', response_model={name}Public)
def update_{name.lower()}(*, session: Session = Depends(get_session), {name.lower()}_{pk}: str, {name.lower()}: {name}Update):
    db_{name.lower()} = session.get({name}, {name.lower()}_{pk})
    if not db_{name.lower()}:
        raise HTTPException(status_code=404, detail=f'{name} {{{name.lower()}_{pk}}} not found.')
    {name.lower()}_data = {name.lower()}.model_dump(exclude_unset=True)
    db_{name.lower()}.sqlmodel_update({name.lower()}_data)
    session.add(db_{name.lower()})
    session.commit()
    session.refresh(db_{name.lower()})
    return db_{name.lower()}"""

        delete_string = f"""
@app.delete('/{name.lower()}/{{{name.lower()}_{pk}}}')
def delete_{name.lower()}(*, session: Session = Depends(get_session), {name.lower()}_{pk}: str):
    {name.lower()} = session.get({name}, {name.lower()}_{pk})
    if not {name.lower()}:
        raise HTTPException(status_code=404, detail=f'{name} {{{name.lower()}_{pk}}} not found.')
    session.delete({name.lower()})
    session.commit()
    return {{'ok': True}}"""

        endpoint_file = f"""
        {post_string}
        {getall_string}
        {get_string}
        {query_string}
        {update_string}
        {delete_string}
        """

        return endpoint_file

    def save(self, filepath: str | os.PathLike):
        with open(filepath, "w") as file:
            file.write("".join([self.header] + self.endpoints))
