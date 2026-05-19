"""Tests for the bulk POST endpoint (issue #112)."""

import textwrap
from unittest.mock import MagicMock, patch

import pytest

from fastapifromfrictionless import app
from fastapifromfrictionless.load import requests_bulk_post


def write_schema(tmp_path, name, content):
    (tmp_path / f"{name}.schema.yaml").write_text(textwrap.dedent(content))


@pytest.fixture()
def simple_folder(tmp_path):
    write_schema(
        tmp_path,
        "location",
        """\
        fields:
          - name: id
            type: integer
          - name: address
            type: string
        primaryKey:
          - id
    """,
    )
    return tmp_path


def _output(folder):
    a = app(str(folder)).build()
    return "".join(a.endpoints)


# ---------------------------------------------------------------------------
# Generated endpoint
# ---------------------------------------------------------------------------


def test_bulk_post_route_generated(simple_folder):
    out = _output(simple_folder)
    assert "@app.post('/locations/bulk'" in out


def test_bulk_post_function_name(simple_folder):
    out = _output(simple_folder)
    assert "def create_locations_bulk" in out


def test_bulk_post_accepts_list_of_create(simple_folder):
    out = _output(simple_folder)
    assert "items: list[LocationCreate]" in out


def test_bulk_post_returns_list_of_public(simple_folder):
    out = _output(simple_folder)
    assert "response_model=list[LocationPublic]" in out


def test_bulk_post_uses_add_all(simple_folder):
    out = _output(simple_folder)
    assert "session.add_all(db_items)" in out


def test_bulk_post_commits_once(simple_folder):
    out = _output(simple_folder)
    # Locate the bulk function and count commits within its block
    start = out.index("def create_locations_bulk")
    # The next function starts at the next "@app." after this def
    after_def = out[start:]
    end_marker = after_def.index("@app.", 10)
    bulk_block = after_def[:end_marker]
    assert bulk_block.count("session.commit()") == 1


# ---------------------------------------------------------------------------
# requests_bulk_post helper
# ---------------------------------------------------------------------------


def test_requests_bulk_post_posts_to_bulk_endpoint():
    fake_session = MagicMock()
    fake_response = MagicMock()
    fake_response.json.return_value = [{"id": 1}, {"id": 2}]
    fake_session.post.return_value = fake_response

    result = requests_bulk_post(
        fake_session,
        server_url="http://localhost:8000",
        endpoint="location",
        rows=[{"id": 1, "address": "a"}, {"id": 2, "address": "b"}],
    )

    fake_session.post.assert_called_once()
    args, kwargs = fake_session.post.call_args
    assert args[0] == "http://localhost:8000/locations/bulk"
    assert kwargs["json"] == [{"id": 1, "address": "a"}, {"id": 2, "address": "b"}]
    assert result == [{"id": 1}, {"id": 2}]


def test_requests_bulk_post_sends_api_key_header():
    fake_session = MagicMock()
    fake_response = MagicMock()
    fake_response.json.return_value = []
    fake_session.post.return_value = fake_response

    requests_bulk_post(
        fake_session,
        server_url="http://localhost:8000",
        endpoint="location",
        rows=[],
        api_key="secret",
    )

    _, kwargs = fake_session.post.call_args
    assert kwargs["headers"] == {"X-API-Key": "secret"}


def test_requests_bulk_post_strips_trailing_slash():
    fake_session = MagicMock()
    fake_response = MagicMock()
    fake_response.json.return_value = []
    fake_session.post.return_value = fake_response

    requests_bulk_post(
        fake_session,
        server_url="http://localhost:8000/",
        endpoint="location",
        rows=[],
    )

    args, _ = fake_session.post.call_args
    assert args[0] == "http://localhost:8000/locations/bulk"


def test_requests_bulk_post_creates_session_when_none():
    fake_response = MagicMock()
    fake_response.json.return_value = []
    with patch("requests.Session") as session_cls:
        session_cls.return_value.post.return_value = fake_response
        requests_bulk_post(
            None,
            server_url="http://localhost:8000",
            endpoint="location",
            rows=[],
        )
        session_cls.assert_called_once()


def test_requests_bulk_post_raises_on_http_error():
    fake_session = MagicMock()
    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = RuntimeError("boom")
    fake_session.post.return_value = fake_response

    with pytest.raises(RuntimeError):
        requests_bulk_post(
            fake_session,
            server_url="http://localhost:8000",
            endpoint="location",
            rows=[{"id": 1}],
        )
    fake_response.close.assert_called_once()
