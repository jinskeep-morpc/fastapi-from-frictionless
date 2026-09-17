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
    "any": {"default": "str"},
}

# Frictionless geo types map to a geoalchemy2 column rather than a plain annotation.
# The value is the geometry type passed to Geometry(); the Python annotation is `Any`
# because geoalchemy2 exposes no static type for the column.
geo_type_map = {
    "geopoint": "POINT",
    "geojson": "GEOMETRY",
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

        # The referenced table and column come from the foreign key declaration.
        # Deriving them by turning underscores into dots, as this used to, gave
        # owner_id -> 'owner.id' for a column pointing at contact, and
        # site_contact_id -> 'site.contact.id', neither of which exists. The table
        # name is the related model's name lowercased, which is what SQLModel uses.
        fk_targets = {
            d["column"]: f"{d['related'].lower()}.{d['ref_field']}"
            for d in ctx.fk_details_of(filename)
        }

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
        basemodel_fields: list[tuple[str, str]] = []
        for field_name in schema.field_names:
            field = schema.get_field(field_name)

            if (field.name == "id") and auto_id:
                continue

            # A primary key is already unique; a second constraint would be redundant.
            unique = bool(field.constraints.get("unique")) and field.name not in schema.primary_key

            if field.type in geo_type_map:
                geometry = f"Geometry('{geo_type_map[field.type]}')"
                uniq_arg = ", unique=True" if unique else ""
                if "required" in field.constraints:
                    field_string = (
                        f"{field.name}: Any = "
                        f"Field(sa_column=Column({geometry}, nullable=False{uniq_arg}))"
                    )
                else:
                    field_string = (
                        f"{field.name}: Any | None = "
                        f"Field(default=None, sa_column=Column({geometry}{uniq_arg}))"
                    )
                self.logger.info(f"{field} converted to {field_string}")
                basemodel_fields.append((field.name, field_string))
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
                    field_string = (
                        f"{field_string.rstrip(')')}, "
                        f"foreign_key='{fk_targets[field.name]}', index=True)"
                    )
                else:
                    field_string += (
                        f" = Field({'default=None, ' if required else ''}"
                        f"foreign_key='{fk_targets[field.name]}', index=True)"
                    )

            if unique:
                if " = Field(" in field_string:
                    field_string = f"{field_string.rstrip(')')}, unique=True)"
                else:
                    field_string += " = Field(unique=True)"

            self.logger.info(f"{field} converted to {field_string}")
            basemodel_fields.append((field.name, field_string))

        # Geo fields need a pydantic serializer on the base model: the annotation is
        # Any, so a WKBElement read back from the database has nothing to dump it. See #167.
        geo_fields = [f for f in schema.field_names if schema.get_field(f).type in geo_type_map]
        if geo_fields:
            self.logger.info(f"{name} geo fields needing a serializer: {geo_fields}")

        # Sensitive fields are held out of the base model so XPublic, which every
        # read route returns, cannot carry them. They are declared on the table
        # model (they are real columns), on XCreate and XUpdate (they are
        # writable), and on XAdmin (readable behind the admin routes).
        sensitive = set(ctx.sensitive_fields_of(filename))
        if sensitive:
            self.logger.info(f"{name} sensitive fields: {sorted(sensitive)}")

        def _optional(fs):
            ann = fs.split(" = ")[0] if " = " in fs else fs
            return ann if " | None" in ann else f"{ann} | None"

        base_pairs = [(n, fs) for n, fs in basemodel_fields if n not in sensitive]
        sens_pairs = [(n, fs) for n, fs in basemodel_fields if n in sensitive]

        basemodel_fields_str = "\n    ".join(fs for _, fs in base_pairs)
        table_extra_str = "\n    ".join(fs for _, fs in sens_pairs)
        writable_extra_str = "\n    ".join(f"{_optional(fs)} = None" for _, fs in sens_pairs)

        update_fields_str = "\n".join(f"    {_optional(fs)}" for _, fs in basemodel_fields)

        # The related class comes from reference.resource, the attribute from the
        # column. Deriving both from the column prefix, as this used to, generated
        # Optional['Owner'] for an owner_id pointing at contact -- a class that
        # does not exist -- and allowed only one reference per resource per table.
        fk_models = []
        for d in ctx.fk_details_of(filename):
            reverse = f"{name.lower()}s"
            fk_models.append(
                {
                    "field": d["column"],
                    "prefix": d["attr"],
                    "related": d["related"],
                    "back_populates": f"{d['attr']}_{reverse}" if d["ambiguous"] else reverse,
                    "fk_ref": f"[{name}.{d['column']}]" if d["ambiguous"] else None,
                }
            )

        rel_models = []
        for r in ctx.reverse_fks_of(filename):
            is_link = r["name"].startswith("Link")
            joined = (
                r["name"].replace("Link", "").replace(name, "").replace("-", "") if is_link else ""
            )
            rel_models.append({**r, "is_link": is_link, "joined": joined})

        template = _env.get_template("model_block.py.jinja2")
        result = template.render(
            name=name,
            auto_id=auto_id,
            link_table=link_table,
            basemodel_fields_str=basemodel_fields_str,
            table_extra_str=table_extra_str,
            writable_extra_str=writable_extra_str,
            has_sensitive=bool(sens_pairs),
            update_fields_str=update_fields_str,
            foreign_keys=foreign_keys,
            relationships=relationships,
            fk_models=fk_models,
            rel_models=rel_models,
            geo_fields=geo_fields,
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
