import logging
import os

from ._templates import env as _env
from .schema_context import SchemaContext

logger = logging.getLogger(__name__)


class app:
    _app_logger = logger.getChild(__qualname__)

    def __init__(self, folder: str | os.PathLike | SchemaContext):
        """
        Create a app.py file based on all frictionless schemas in a folder.

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
        self.schema_paths = self._ctx.filenames

    def build(self):
        self.endpoints = []
        for filename in self.schema_paths:
            endpoint = self.build_endpoint(filename)
            self.endpoints.append(endpoint)

        return self

    def build_endpoint(self, filename):
        ctx = self._ctx
        name = ctx.name_of(filename)
        foreign_keys = ctx.foreign_keys_of(filename)
        relationships = ctx.relationships_of(filename)

        has_relations = len(foreign_keys) > 0 or len(relationships) > 0
        has_fk = len(foreign_keys) > 0
        pk = ctx.primary_key_of(filename)
        name_lower = name.lower()
        list_response_model = f"{name}PublicWithAll" if has_relations else f"{name}Public"
        get_response_model = f"{name}PublicWithAll" if has_relations else f"{name}Public"

        template = _env.get_template("endpoint_block.py.jinja2")
        return template.render(
            name=name,
            name_lower=name_lower,
            pk=pk,
            has_fk=has_fk,
            has_relations=has_relations,
            list_response_model=list_response_model,
            get_response_model=get_response_model,
        )

    def save(self, filepath: str | os.PathLike):
        header = _env.get_template("app_header.py.jinja2").render()
        with open(filepath, "w") as file:
            file.write(header + "".join(self.endpoints))
