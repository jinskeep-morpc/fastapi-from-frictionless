"""Tests for dump_to_excel in load.py."""

import os
import textwrap
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from fastapifromfrictionless.load import dump_to_excel


@pytest.fixture()
def schema_folder(tmp_path):
    """A temporary schema folder with two minimal schemas."""
    (tmp_path / "location.schema.yaml").write_text(
        textwrap.dedent("""\
        fields:
          - name: address
            type: string
          - name: zipcode
            type: string
    """)
    )
    (tmp_path / "sensor.schema.yaml").write_text(
        textwrap.dedent("""\
        fields:
          - name: name
            type: string
          - name: model
            type: string
    """)
    )
    return tmp_path


def _mock_get_all(df_map):
    """Return a requests_get_all side_effect that returns per-endpoint DataFrames."""

    def _inner(session, server_url, endpoint):
        if endpoint in df_map:
            return df_map[endpoint]
        raise RuntimeError(f"Unexpected endpoint: {endpoint}")

    return _inner


@patch("fastapifromfrictionless.runtime.excel.requests_get_all")
def test_dump_writes_data_rows(mock_get, schema_folder, tmp_path):
    mock_get.side_effect = _mock_get_all(
        {
            "location": pd.DataFrame([{"address": "123 Main St", "zipcode": "43215"}]),
            "sensor": pd.DataFrame([{"name": "AQ-1", "model": "PurpleAir"}]),
        }
    )
    out = tmp_path / "out.xlsx"
    dump_to_excel("http://localhost:8000", schema_folder, out)

    assert out.exists()
    sheets = pd.read_excel(out, sheet_name=None)
    assert set(sheets.keys()) == {"location", "sensor"}
    assert list(sheets["location"].columns) == ["address", "zipcode"]
    assert sheets["location"].iloc[0]["address"] == "123 Main St"
    assert sheets["sensor"].iloc[0]["name"] == "AQ-1"


@patch("fastapifromfrictionless.runtime.excel.requests_get_all")
def test_dump_empty_api_writes_headers_only(mock_get, schema_folder, tmp_path):
    mock_get.side_effect = _mock_get_all(
        {
            "location": pd.DataFrame(columns=["address", "zipcode"]),
            "sensor": pd.DataFrame(columns=["name", "model"]),
        }
    )
    out = tmp_path / "empty.xlsx"
    dump_to_excel("http://localhost:8000", schema_folder, out)

    sheets = pd.read_excel(out, sheet_name=None)
    assert list(sheets["location"].columns) == ["address", "zipcode"]
    assert len(sheets["location"]) == 0


@patch("fastapifromfrictionless.runtime.excel.requests_get_all")
def test_dump_endpoint_error_writes_empty_sheet(mock_get, schema_folder, tmp_path):
    """A failing endpoint should not abort the whole export — write an empty sheet."""

    def _raise(session, server_url, endpoint):
        if endpoint == "sensor":
            raise RuntimeError("connection refused")
        return pd.DataFrame([{"address": "1 Ohio St", "zipcode": "43215"}])

    mock_get.side_effect = _raise
    out = tmp_path / "partial.xlsx"
    dump_to_excel("http://localhost:8000", schema_folder, out)

    sheets = pd.read_excel(out, sheet_name=None)
    assert len(sheets["location"]) == 1
    assert len(sheets["sensor"]) == 0


@patch("fastapifromfrictionless.runtime.excel.requests_get_all")
def test_dump_column_order_matches_schema(mock_get, schema_folder, tmp_path):
    """Columns in the output must follow schema field order, not API response order."""
    mock_get.side_effect = _mock_get_all(
        {
            "location": pd.DataFrame([{"zipcode": "43215", "address": "1 Ohio St"}]),
            "sensor": pd.DataFrame([{"model": "PurpleAir", "name": "AQ-1"}]),
        }
    )
    out = tmp_path / "ordered.xlsx"
    dump_to_excel("http://localhost:8000", schema_folder, out)

    sheets = pd.read_excel(out, sheet_name=None)
    assert list(sheets["location"].columns) == ["address", "zipcode"]
    assert list(sheets["sensor"].columns) == ["name", "model"]
