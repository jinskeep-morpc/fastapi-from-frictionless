# fastapifromfrictionless.model
# Tools for building SQLmodels from Frictionless Schemas

## Setup logger
import logging
logger = logging.getLogger(__name__)

from os import PathLike

type_map = {
    "string": {
        "default": "str",
        "email": "EmailStr",
        "uri": "AnyUrl",
        "binary": "bytes",
        "uuid": "UUID"
    },
    "number": {
        "default": "float"
    },
    "integer": {
        "default": "int"
    },
    "boolean": {
        "default": "bool"
    },
    "object": {
        "default": "Json[Any]"
    },
    "array": {
        "default": "List[Any]"
    },
    "datetime": {
        "default": "datetime"
    },
    "date": {
        "default": "date"
    },
    "time": {
        "default": "time"
    },
    "year": {
        "default": "int"
    },
    "duration": {
        "default": "timedelta"
    },
    "geopoint": {
        "default": "Geometry('POINT')"
    },
    "geojson": {
        "default": "Geometry('GEOMETRY')"
    }
}

class models():
    _models_logger = logging.getLogger(__name__).getChild(__qualname__)
    def __init__(self, folder: str | PathLike):
        """
        Create a models.py file based on all frictionless schemas in a folder.

        parameters:
        -----------
        folder : str | Pathlike
            The location of the schema files
        
        """
        import os

        self.logger = logging.getLogger(__name__).getChild(self.__class__.__name__).getChild(folder)

        self.header = """
from typing import Optional, List
from uuid import UUID
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel
from datetime import date, datetime, timezone, time, timedelta
from pydantic import EmailStr, AnyUrl, Json
from geoalchemy2.types import Geometry

def utcnow():
    '''Returns the current time in UTC.'''
    return datetime.now(timezone.utc)

class TimestampMixin: # https://www.davidmuraya.com/blog/reusable-sqlmodel-mixins/
    '''A mixin to add created_at and updated_at timestamp fields to a model.'''

    created_at: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        sa_column_kwargs={"onupdate": utcnow},
        sa_type=DateTime(timezone=True)
    )
"""
        # Validate folder
        if not os.path.exists(folder):
            logger.error(f"{folder} not a valid path.")
        else:
            self.folder = folder
        
        # Read schemas from folder
        self.schemas = [x for x in os.listdir(folder) if x.endswith('schema.yaml')]
        logger.info(f"Building models for schemas from {folder}: {" .".join(self.schemas)}")

    def build(self):
        self.models = []
        for filename in self.schemas:
            self.logger.info(f"Building model for {filename}")
            model = self.build_model(self.folder, filename)
            self.models.append(model)

        return self

    def build_model(self, folder, filename: str) -> str:
        """Build the individual models (base, table, create, update, public, and public with relationships) for a schema
        
        parameters:
        -----------
        folder: str
            the folder where the schema is saved. 
        filename: str
            the full filename of the schema.
        """

        import os
        import frictionless

        filepath = os.path.join(folder, filename)

        # Store the base name of the schema as the name of the model.
        name = filename.split('.')[0].replace('-', ' ').title().replace(' ', '')

        # Validate path
        if not os.path.exists(filepath):
            self.logger.error(f"{filepath} does not exist.")

        # Load the schema
        try:
            schema = frictionless.Schema(filepath)
        except Exception as e:
            self.logger.error(f"{e}")

        # Store the foreign keys from the schema to get references to other tables.
        foreign_keys = [x['fields'][0] for x in schema.foreign_keys]
        self.logger.info(f"Schema {name} foreign keys {foreign_keys}")

        # Check other schemas to see if they reference this schema
        relationships = []
        for other_filename in self.schemas:
            if other_filename != filename:
                other_filepath = os.path.join(folder, other_filename)
                other_name = other_filename.split('.')[0].replace('-', ' ').title().replace(' ', '')
                other_schema = frictionless.Schema(other_filepath)
                if len(other_schema.foreign_keys) > 0:
                    for fk in other_schema.foreign_keys:
                        if fk['reference']['resource'] == name.lower():
                            self.logger.debug(f"{name} is referenced by {other_name}")
                            relationships.append(other_name)
                        else:
                            self.logger.debug(f"{name} not reference by {other_name}")
        if len(relationships) == 0 :
            self.logger.info(f'{name} not referenced by other schemas.')
        else:
            self.logger.info(f"{name} is referenced by {relationships}")

        # Check if primary key is 'id'. These will be build in SQLmodel to be auto-incrementing. 
        auto_id = "id" in schema.primary_key
        if auto_id:
            self.logger.info(f"Primary key is 'id'. Will add to table model with autoincrement.")

        # Check if schema is for a many-to-many link table
        if (len(foreign_keys) == 2) & (len(schema.primary_key)==2):
            link_table = True
            self.logger.info(f"{name} is a many-to-many link table.")
        else:
            link_table = False

        # Build the base model
        basemodel_fields = []

        # For each field in the scheme create a string for the model.
        for field in schema.field_names:
            field = schema.get_field(field)
            
            # Skip id, will include in table model.
            if (field.name == 'id') & (auto_id == True):
                continue
            else:
                # Build strong from schema attributes. 
                field_string = ""
                field_string += f"{field.name}: "
                field_string += f"{type_map[field.type][field.format]}"  

                # Check if field is required by looking at the constraints descriptor.
                if not 'required' in field.constraints:
                    field_string += " | None"
                    required = False
                else:
                    required = True

                # Check if the field is a primary key
                if field.name in schema.primary_key:
                    field_string += " = Field(primary_key = True)"
                
                # Check if the field is a foreign key
                if field.name in foreign_keys:
                    if " = Field(primary_key = True)" in field_string:
                        field_string  = f"{field_string.rstrip(')')}, foreign_key='{field.name.replace('_', '.')}')"
                    else:
                        field_string += f" = Field({"default=None, " if required else ""}foreign_key='{field.name.replace('_', '.')}')"

                self.logger.info(f"{field} converted to {field_string}")
                basemodel_fields.append(field_string)

        basemodel_string = f"""class {name}Base(SQLModel):
    {"\n    ".join(basemodel_fields)}
"""
        self.logger.debug(f"{basemodel_string}")

        # Build table model
        tablemodel_string = f"""class {name}({name}Base, TimestampMixin, table=True):
"""
        # If primary key is 'id' add to table.
        if auto_id == True:
            tablemodel_string += "    id: int | None = Field(default=None, primary_key=True)\n"

        # If schema is referenced by other schemas add to table
        if len(relationships) > 0:
            for relationship in relationships:
                tablemodel_string += f"    {relationship.lower()}s: list['{relationship}'] | None = Relationship(back_populates='{name.lower()}s')\n"

        # If schema references other schemas add to table.
        if len(foreign_keys) > 0:
            for fk in foreign_keys:
                tablemodel_string += f"    {fk.split('_')[0]}s: list['{fk.split('_')[0].capitalize()}'] | None = Relationship(back_populates='{name.lower()}s')\n" 
        if (auto_id == False) & (len(relationships) == 0) & (len(foreign_keys) == 0):
            tablemodel_string += '    pass\n'

        self.logger.info(f"{tablemodel_string}")

        # Build Create model
        createmodel_string = f"""class {name}Create({name}Base):
    pass
"""
        self.logger.debug(f"{createmodel_string}")

        # Build update model
        updatemodel_string = f"""class {name}Update({name}Base):\n"""
        for field in basemodel_fields:
            # Remove everything except datatype and None
            if " = " in field:
                field = field.split(" = ")[0]
            if not ' | None' in field:
                updatemodel_string += f"    {field} | None\n" # Add optional if not present
            else:
                updatemodel_string +=  f"    {field}\n"

        self.logger.debug(f"{updatemodel_string}")


        # Build public model
        publicmodel_string = f"""class {name}Public({name}Base):{"\n    id: int" if auto_id == True else ''}
    created_at: datetime 
    updated_at: datetime
"""
        self.logger.debug(f"{publicmodel_string}")

        # Build public with relationships model for models with foreign keys to facilitate queries
        relationshipsmodel_string = f""
        if (len(foreign_keys) > 0) | (len(relationships) > 0):
            relationshipsmodel_string += f"""class {name}PublicWithAll({name}Public):\n"""
            for fk in foreign_keys:
                relationshipsmodel_string += f"    {fk.split("_")[0]}s: Optional[List['{fk.split('_')[0].capitalize()}Public']] | None = None\n"
            for relationship in relationships:
                if relationship.startswith('Link'):
                    joined = relationship.replace('Link', "").replace(name, "").replace('-', "")
                    relationshipsmodel_string += f"    {relationship.lower()}s: Optional[List['{relationship}PublicWith{joined}']] | None = None\n"
                else:
                    relationshipsmodel_string += f"    {relationship.lower()}s: Optional[List['{relationship}Public']] | None = None\n"

        if link_table:
            for fk in foreign_keys:
                relationshipsmodel_string += f"""\nclass {name}PublicWith{fk.split('_')[0].capitalize()}({name}Public):\n"""
                relationshipsmodel_string += f"    {fk.split("_")[0]}s: Optional[List['{fk.split('_')[0].capitalize()}Public']] | None = None\n\n"
                    
        self.logger.debug(f"{relationshipsmodel_string}")

        return f"""
## {name} models
{basemodel_string}
{tablemodel_string}
{createmodel_string}
{updatemodel_string}
{publicmodel_string}
{relationshipsmodel_string}
    """

    def save(self, path: str | PathLike):
        with open(path, 'w') as file:
            file_string = "".join([self.header] + self.models)
            file.write(file_string)
            logger.info(f"models saved to {path}")
