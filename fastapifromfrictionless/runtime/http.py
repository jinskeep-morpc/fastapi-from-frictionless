import logging
import os

import pandas as pd
import requests
from requests import Session

logger = logging.getLogger(__name__)


def requests_post(
    session: Session | None, server_url: str | os.PathLike, endpoint: str, model
):
    if session is None:
        session = requests.Session()
    logger.debug(f"Posting {model.model_dump_json()} to {server_url}/{endpoint}.")
    r = session.post(f"{server_url.rstrip('/')}/{endpoint}", data=model.model_dump_json())
    logger.debug(r.content.decode("utf-8", errors="replace"))
    r.raise_for_status()
    json = r.json()
    r.close()
    return json


def requests_bulk_post(
    session: Session | None, server_url: str | os.PathLike, endpoint: str, rows: list, api_key: str = ""
) -> list:
    """POST a batch of rows to ``/{endpoint}s/bulk`` in a single request."""
    if session is None:
        session = requests.Session()
    url = f"{server_url.rstrip('/')}/{endpoint}s/bulk"
    headers = {"X-API-Key": api_key} if api_key else {}
    logger.debug(f"Bulk posting {len(rows)} rows to {url}.")
    r = None
    try:
        r = session.post(url, json=rows, headers=headers)
        r.raise_for_status()
        return r.json()
    finally:
        if r is not None:
            r.close()


def requests_get_all(
    session: Session | None, server_url: str | os.PathLike, endpoint: str
) -> pd.DataFrame:
    if session is None:
        session = requests.Session()
    url = f"{server_url.rstrip('/')}/{endpoint}/all"
    logger.debug(f"Getting all from at {url}")
    json = []
    r = None
    try:
        r = session.get(url)
        r.raise_for_status()
        json = r.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error: {e}")
    except requests.exceptions.JSONDecodeError as e:
        logger.error(f"Json Decoder Error: {e}")
    except Exception as e:
        logger.error(f"Other Error: {e}")
    finally:
        if r is not None:
            r.close()

    return pd.DataFrame.from_dict(json)


def requests_update(
    session: Session | None, server_url: str | os.PathLike, endpoint: str, pk, model
):
    if session is None:
        session = requests.Session()
    logger.debug(f"Updating {pk} at {server_url}/{endpoint} to {model.model_dump_json()}")
    r = session.patch(f"{server_url.rstrip('/')}/{endpoint}/{pk}", data=model.model_dump_json())
    r.raise_for_status()
    json = r.json()
    r.close()
    return json
