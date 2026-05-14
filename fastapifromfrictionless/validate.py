"""Schema validation for fastapifromfrictionless generators."""

import logging
import os
from os import PathLike

logger = logging.getLogger(__name__)


def validate_schemas(folder: str | PathLike) -> list[str]:
    """Check a folder of ``*.schema.yaml`` files for code-generation compatibility.

    Returns a list of human-readable error strings.  An empty list means all
    schemas are valid.  Does *not* raise — callers decide what to do with errors.

    Checks performed
    ----------------
    - Folder exists and contains at least one ``*.schema.yaml``
    - Each schema file loads without error (frictionless validates types, PKs, etc.)
    - Foreign key references point to an existing schema in the folder (cross-schema
      consistency that frictionless cannot verify on its own)
    """
    import frictionless

    errors: list[str] = []

    if not os.path.isdir(folder):
        errors.append(f"Schema folder does not exist: {folder!r}")
        return errors

    schema_files = sorted(f for f in os.listdir(folder) if f.endswith("schema.yaml"))
    if not schema_files:
        errors.append(f"No *.schema.yaml files found in {folder!r}")
        return errors

    known_resources = {f.replace(".schema.yaml", "").lower() for f in schema_files}
    loaded: dict[str, frictionless.Schema] = {}

    for filename in schema_files:
        filepath = os.path.join(folder, filename)
        label = filename

        try:
            schema = frictionless.Schema(filepath)
            loaded[filename] = schema
        except Exception as exc:
            errors.append(f"[{label}] Failed to load schema: {exc}")

    # Cross-schema FK reference check (only for schemas that loaded successfully)
    for filename, schema in loaded.items():
        label = filename
        for fk in schema.foreign_keys:
            ref_resource = fk.get("reference", {}).get("resource", "")
            if ref_resource and ref_resource.lower() not in known_resources:
                errors.append(
                    f"[{label}] Foreign key references unknown resource '{ref_resource}'. "
                    f"Known resources: {sorted(known_resources)}"
                )

    return errors


def assert_schemas_valid(folder: str | PathLike) -> None:
    """Validate schemas and raise ``ValueError`` listing all problems if any are found."""
    errors = validate_schemas(folder)
    if errors:
        msg = f"Schema validation failed for {folder!r} with {len(errors)} error(s):\n"
        msg += "\n".join(f"  • {e}" for e in errors)
        raise ValueError(msg)
    logger.info(f"All schemas in {folder!r} passed validation.")
