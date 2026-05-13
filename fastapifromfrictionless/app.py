import logging
import os
from pathlib import Path

import jinja2

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    variable_start_string="<<",
    variable_end_string=">>",
    block_start_string="<%",
    block_end_string="%>",
    comment_start_string="<#",
    comment_end_string="#>",
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


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
        self.logger = (
            logging.getLogger(__name__).getChild(self.__class__.__name__).getChild(str(folder))
        )

        if not os.path.exists(folder):
            self.logger.error(f"{folder} does not exist.")
            raise ValueError
        else:
            self.folder: str = str(folder)

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

        has_relations = len(foreign_keys) > 0 or len(relationships) > 0
        has_fk = len(foreign_keys) > 0
        pk = schema.primary_key[0]
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
