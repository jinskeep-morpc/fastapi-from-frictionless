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

    @staticmethod
    def _attr_for(column: str, ref_field: str) -> str:
        """Relationship attribute for a foreign key column.

        The referenced field is stripped as a suffix, so ``owner_id`` -> ``owner``
        and ``sensor_name`` -> ``sensor``. This is what allows a role-named column
        to coexist with the resource it points at: the class comes from
        ``reference.resource``, only the attribute comes from the column.
        """
        suffix = f"_{ref_field}"
        return column[: -len(suffix)] if column.endswith(suffix) else column

    def fk_details_of(self, filename: str) -> list[dict]:
        """One entry per outgoing foreign key.

        ``ambiguous`` marks a resource this schema references more than once.
        SQLAlchemy cannot infer a join condition in that case, so the generated
        Relationship has to name its foreign key explicitly.
        """
        schema = self.schema_of(filename)
        per_resource: dict[str, int] = {}
        for fk in schema.foreign_keys:
            res = fk["reference"]["resource"]
            per_resource[res] = per_resource.get(res, 0) + 1

        details: list[dict] = []
        for fk in schema.foreign_keys:
            column = fk["fields"][0]
            res = fk["reference"]["resource"]
            details.append(
                {
                    "column": column,
                    "resource": res,
                    "attr": self._attr_for(column, fk["reference"]["fields"][0]),
                    "ref_field": fk["reference"]["fields"][0],
                    "related": self.name_of(f"{res}.schema.yaml"),
                    "ambiguous": per_resource[res] > 1,
                }
            )
        return details

    def reverse_fks_of(self, filename: str) -> list[dict]:
        """One entry per incoming foreign key column, not per referencing schema.

        A schema referencing this one twice needs two reverse collections, named
        after the forward attribute so they do not collide.
        """
        stem = filename.replace(".schema.yaml", "")
        out: list[dict] = []
        for other in sorted(self.filenames):
            if other == filename:
                continue
            referencing = self.name_of(other)
            base = f"{referencing.lower()}s"
            for d in self.fk_details_of(other):
                if d["resource"] != stem:
                    continue
                out.append(
                    {
                        "name": referencing,
                        "attr": f"{d['attr']}_{base}" if d["ambiguous"] else base,
                        "back_populates": d["attr"],
                        "fk_ref": f"[{referencing}.{d['column']}]" if d["ambiguous"] else None,
                    }
                )
        return out

    def sensitive_fields_of(self, filename: str) -> list[str]:
        """Fields marked ``sensitive: true``, a custom schema property.

        A sensitive field is writable but not readable by ordinary callers: it is
        kept out of the base model, so ``XPublic`` cannot carry it, and surfaced
        only on ``XAdmin`` behind the admin routes. Not OpenAPI's ``writeOnly``,
        which would hide it from everyone including an administrator.
        """
        schema = self.schema_of(filename)
        out = []
        for name in schema.field_names:
            custom = getattr(schema.get_field(name), "custom", None) or {}
            if custom.get("sensitive"):
                out.append(name)
        return out

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
