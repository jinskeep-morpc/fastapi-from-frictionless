"""Generate ui.py, the CRUD UI wiring for a project.

The generated file is deliberately thin: a resource descriptor plus a call to
:func:`fastapifromfrictionless.web.build_ui_router`. View logic and templates
live in the package so they can be fixed without regenerating every project.
"""

import logging
import os

from ._templates import env as _env
from .schema_context import SchemaContext

logger = logging.getLogger(__name__)


class ui:
    def __init__(self, folder: str | os.PathLike | SchemaContext, skip: list[str] | None = None):
        """
        parameters
        ----------
        folder : str | PathLike | SchemaContext
            Location of the schema files, or a pre-built SchemaContext.
        skip : list[str] | None
            Resource names to omit, e.g. a readings table too large to browse.
        """
        self._ctx = folder if isinstance(folder, SchemaContext) else SchemaContext(folder)
        self.folder = self._ctx.folder
        self.skip = set(skip or [])
        self.schema_paths = self._ctx.filenames

    def build(self) -> "ui":
        ctx = self._ctx
        self.resources = []
        for filename in self.schema_paths:
            name = ctx.name_of(filename)
            slug = filename.replace(".schema.yaml", "")
            if slug in self.skip or name in self.skip:
                logger.info(f"Skipping UI for {slug}")
                continue
            schema = ctx.schema_of(filename)
            foreign_keys = {
                fk["fields"][0]: f"{fk['reference']['resource'].replace('-', '')}."
                f"{fk['reference']['fields'][0] if isinstance(fk['reference']['fields'], list) else fk['reference']['fields']}"
                for fk in schema.foreign_keys
            }
            sensitive = set(ctx.sensitive_fields_of(filename))
            fields = []
            for field_name in schema.field_names:
                field = schema.get_field(field_name)
                fields.append(
                    {
                        "name": field.name,
                        "type": field.type,
                        "required": "required" in field.constraints,
                        "fk": foreign_keys.get(field.name),
                        "sensitive": field.name in sensitive,
                    }
                )
            self.resources.append(
                {
                    "slug": slug,
                    "name": name,
                    "label": slug.replace("-", " ").replace("_", " ").title(),
                    "pk": list(schema.primary_key),
                    "fields": fields,
                }
            )
        return self

    def save(self, filepath: str | os.PathLike):
        rendered = _env.get_template("ui.py.jinja2").render(resources=self.resources)
        with open(filepath, "w") as file:
            file.write(rendered)
        logger.info(f"ui saved to {filepath}")
