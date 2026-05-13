"""Tests for validate.py schema validation."""
import textwrap

import pytest

from fastapifromfrictionless.validate import assert_schemas_valid, validate_schemas


def write_schema(tmp_path, name, content):
    (tmp_path / f"{name}.schema.yaml").write_text(textwrap.dedent(content))


# ---------------------------------------------------------------------------
# validate_schemas — returns errors, never raises
# ---------------------------------------------------------------------------

def test_missing_folder_returns_error():
    errors = validate_schemas("/nonexistent/path/xyz")
    assert any("does not exist" in e for e in errors)


def test_empty_folder_returns_error(tmp_path):
    errors = validate_schemas(tmp_path)
    assert any("No *.schema.yaml" in e for e in errors)


def test_valid_schema_returns_no_errors(tmp_path):
    write_schema(tmp_path, "location", """\
        fields:
          - name: id
            type: integer
          - name: address
            type: string
            constraints:
              required: true
        primaryKey:
          - id
    """)
    assert validate_schemas(tmp_path) == []


def test_unsupported_field_type_returns_error(tmp_path):
    """Frictionless rejects unknown types at load time; error surfaces via load failure."""
    write_schema(tmp_path, "item", """\
        fields:
          - name: id
            type: integer
          - name: coords
            type: wkt
    """)
    errors = validate_schemas(tmp_path)
    assert len(errors) == 1
    assert "Failed to load schema" in errors[0]
    assert "wkt" in errors[0]


def test_missing_primary_key_field_returns_error(tmp_path):
    """Frictionless rejects PKs that don't match defined fields at load time."""
    write_schema(tmp_path, "item", """\
        fields:
          - name: name
            type: string
        primaryKey:
          - ghost_field
    """)
    errors = validate_schemas(tmp_path)
    assert len(errors) == 1
    assert "Failed to load schema" in errors[0]
    assert "ghost_field" in errors[0]


def test_foreign_key_to_unknown_resource_returns_error(tmp_path):
    write_schema(tmp_path, "deployment", """\
        fields:
          - name: id
            type: integer
          - name: location_id
            type: integer
        primaryKey:
          - id
        foreignKeys:
          - fields: [location_id]
            reference:
              resource: nonexistent
              fields: [id]
    """)
    errors = validate_schemas(tmp_path)
    assert any("nonexistent" in e and "unknown resource" in e for e in errors)


def test_foreign_key_to_known_resource_passes(tmp_path):
    write_schema(tmp_path, "location", """\
        fields:
          - name: id
            type: integer
        primaryKey:
          - id
    """)
    write_schema(tmp_path, "deployment", """\
        fields:
          - name: id
            type: integer
          - name: location_id
            type: integer
        primaryKey:
          - id
        foreignKeys:
          - fields: [location_id]
            reference:
              resource: location
              fields: [id]
    """)
    assert validate_schemas(tmp_path) == []


def test_errors_collected_across_all_schemas(tmp_path):
    """All schemas are checked; a broken schema doesn't abort the rest."""
    write_schema(tmp_path, "good", """\
        fields:
          - name: id
            type: integer
        primaryKey:
          - id
    """)
    write_schema(tmp_path, "bad_a", """\
        fields:
          - name: x
            type: wkt
    """)
    write_schema(tmp_path, "bad_b", """\
        fields:
          - name: x
            type: blob
    """)
    errors = validate_schemas(tmp_path)
    # Two load failures, one per bad schema
    assert len(errors) == 2
    labels = [e.split("]")[0].lstrip("[") for e in errors]
    assert "bad_a.schema.yaml" in labels
    assert "bad_b.schema.yaml" in labels


# ---------------------------------------------------------------------------
# assert_schemas_valid — raises ValueError on failure
# ---------------------------------------------------------------------------

def test_assert_raises_on_invalid(tmp_path):
    write_schema(tmp_path, "bad", """\
        fields:
          - name: x
            type: wkt
    """)
    with pytest.raises(ValueError, match="Schema validation failed"):
        assert_schemas_valid(tmp_path)


def test_assert_passes_on_valid(tmp_path):
    write_schema(tmp_path, "good", """\
        fields:
          - name: id
            type: integer
        primaryKey:
          - id
    """)
    assert_schemas_valid(tmp_path)  # should not raise
