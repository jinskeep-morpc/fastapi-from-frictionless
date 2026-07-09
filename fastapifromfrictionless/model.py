# fastapifromfrictionless.model
# Tools for building SQLmodels from Frictionless Schemas

import logging
from os import PathLike

from ._templates import env as _env
from .schema_context import SchemaContext

logger = logging.getLogger(__name__)

type_map = {
    "string": {
        "default": "str",
        "email": "str",
        "uri": "AnyUrl",
        "binary": "bytes",
        "uuid": "UUID",
    },
    "number": {"default": "float"},
    "integer": {"default": "int"},
    "boolean": {"default": "bool"},
    "object": {"default": "Json[Any]"},
    "array": {"default": "List[Any]"},
    "datetime": {"default": "datetime"},
    "date": {"default": "date"},
    "time": {"default": "time"},
    "year": {"default": "int"},
    "yearmonth": {"default": "str"},
    "duration": {"default": "timedelta"},
    "geopoint": {"default": "Geometry('POINT')"},
    "geojson": {"default": "Geometry('GEOMETRY')"},
    "any": {"default": "str"},
}


class models:
    _models_logger = logging.getLogger(__name__).getChild(__qualname__)

    def __init__(self, folder: str | PathLike | SchemaContext):
        """
        Create a models.py file based on all frictionless schemas in a folder.

        parameters:
        -----------
        folder : str | PathLike | SchemaContext
            The location of the schema files, or a pre-built SchemaContext.

        """
        if isinstance(folder, SchemaContext):
            self._ctx = folder
        else:
            self._ctx = SchemaContext(folder)

        self.logger = (
            logging.getLogger(__name__).getChild(self.__class__.__name__).getChild(self._ctx.folder)
        )
        self.folder: str = self._ctx.folder
        self.schemas = self._ctx.filenames
        logger.info(f"Building models for schemas from {self.folder}: {' .'.join(self.schemas)}")

    def build(self) -> "models":
        self.models: list[str] = []
        for filename in self.schemas:
            self.logger.info(f"Building model for {filename}")
            model = self.build_model(filename)
            self.models.append(model)

        self.has_geo = any("Geometry" in m for m in self.models)
        return self

    def build_model(self, filename: str) -> str:
        """Build the individual models for a schema via Jinja2 template."""
        ctx = self._ctx
        name = ctx.name_of(filename)
        schema = ctx.schema_of(filename)

        foreign_keys = ctx.foreign_keys_of(filename)
        self.logger.info(f"Schema {name} foreign keys {foreign_keys}")

        relationships = ctx.relationships_of(filename)
        if not relationships:
            self.logger.info(f"{name} not referenced by other schemas.")
        else:
            self.logger.info(f"{name} is referenced by {relationships}")

        auto_id = ctx.primary_key_of(filename) == "id" and len(schema.primary_key) == 1
        if auto_id:
            self.logger.info("Primary key is 'id'. Will add to table model with autoincrement.")

        link_table = ctx.is_link_table(filename)
        if link_table:
            self.logger.info(f"{name} is a many-to-many link table.")

        # Build base model field strings
        basemodel_fields: list[str] = []
        for field_name in schema.field_names:
            field = schema.get_field(field_name)

            if (field.name == "id") and auto_id:
                continue

            field_string = f"{field.name}: "
            fmt_map = type_map.get(field.type, {"default": "Any"})
            field_string += fmt_map.get(field.format, fmt_map["default"])

            if "required" not in field.constraints:
                field_string += " | None"
                required = False
            else:
                required = True

            if field.name in schema.primary_key:
                field_string += " = Field(primary_key = True)"

            if field.name in foreign_keys:
                if " = Field(primary_key = True)" in field_string:
                    field_string = f"{field_string.rstrip(')')}, foreign_key='{field.name.replace('_', '.')}', index=True)"
                else:
                    field_string += f" = Field({'default=None, ' if required else ''}foreign_key='{field.name.replace('_', '.')}', index=True)"

            self.logger.info(f"{field} converted to {field_string}")
            basemodel_fields.append(field_string)

        # Precompute derived template context
        basemodel_fields_str = "\n    ".join(basemodel_fields)

        update_lines = []
        for fs in basemodel_fields:
            fs = fs.split(" = ")[0] if " = " in fs else fs
            if " | None" not in fs:
                fs += " | None"
            update_lines.append(f"    {fs}")
        update_fields_str = "\n".join(update_lines)

        fk_models = [
            {"field": fk, "prefix": fk.split("_")[0], "related": fk.split("_")[0].capitalize()}
            for fk in foreign_keys
        ]

        rel_models = []
        for rel in relationships:
            is_link = rel.startswith("Link")
            joined = rel.replace("Link", "").replace(name, "").replace("-", "") if is_link else ""
            rel_models.append(
                {"name": rel, "lower_name": rel.lower(), "is_link": is_link, "joined": joined}
            )

        template = _env.get_template("model_block.py.jinja2")
        result = template.render(
            name=name,
            auto_id=auto_id,
            link_table=link_table,
            basemodel_fields_str=basemodel_fields_str,
            update_fields_str=update_fields_str,
            foreign_keys=foreign_keys,
            relationships=relationships,
            fk_models=fk_models,
            rel_models=rel_models,
        )
        self.logger.debug(result)
        return result

    def save(self, path: str | PathLike):
        header = _env.get_template("models_header.py.jinja2").render(
            has_geo=getattr(self, "has_geo", True)
        )
        with open(path, "w") as file:
            file.write(header + "".join(self.models))
            logger.info(f"models saved to {path}")
