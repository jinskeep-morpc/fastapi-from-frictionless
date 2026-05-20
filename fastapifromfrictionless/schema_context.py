"""Cached view over a folder of frictionless schemas.

Loads each ``*.schema.yaml`` exactly once and exposes the lookups that the
code generators (``model.py``, ``app.py``) repeat per schema.
"""

import logging
import os
from os import PathLike

import frictionless

from .validate import assert_schemas_valid

logger = logging.getLogger(__name__)


class SchemaContext:
    def __init__(self, folder: str | PathLike):
        assert_schemas_valid(folder)
        self.folder: str = str(folder)
        self.filenames: list[str] = sorted(
            f for f in os.listdir(self.folder) if f.endswith("schema.yaml")
        )
        self._schemas: dict[str, frictionless.Schema] = {
            fn: frictionless.Schema(os.path.join(self.folder, fn)) for fn in self.filenames
        }

    def name_of(self, filename: str) -> str:
        return filename.split(".")[0].replace("-", " ").title().replace(" ", "")

    def schema_of(self, filename: str) -> frictionless.Schema:
        return self._schemas[filename]

    def foreign_keys_of(self, filename: str) -> list[str]:
        return [x["fields"][0] for x in self.schema_of(filename).foreign_keys]

    def relationships_of(self, filename: str) -> list[str]:
        target = self.name_of(filename).lower()
        relationships: list[str] = []
        for other in self.filenames:
            if other == filename:
                continue
            other_schema = self.schema_of(other)
            for fk in other_schema.foreign_keys:
                if fk["reference"]["resource"] == target:
                    relationships.append(self.name_of(other))
                    break
        return relationships

    def is_link_table(self, filename: str) -> bool:
        schema = self.schema_of(filename)
        return len(schema.foreign_keys) == 2 and len(schema.primary_key) == 2

    def primary_key_of(self, filename: str) -> str:
        return self.schema_of(filename).primary_key[0]
