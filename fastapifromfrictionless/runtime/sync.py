import logging

import fastapi
import frictionless
from pydantic import ValidationError
from requests import Session

from .http import requests_bulk_post, requests_get_all, requests_update

logger = logging.getLogger(__name__)


def get_model(name: str, type: str, models_module=None):
    from sqlmodel.main import SQLModelMetaclass

    if models_module is None:
        import models

        models_module = models

    target = f"{name.capitalize()}{type.capitalize()}"
    matched_model = None
    for attr in dir(models_module):
        if attr.casefold() == target.casefold():
            matched_model = getattr(models_module, attr)
            break

    if matched_model is not None and isinstance(matched_model, SQLModelMetaclass):
        return matched_model

    logger.error(f"No models for {target}.")
    raise ValueError(f"No models for {target}.")


def update_api_from_package(api_url, package_file, skip=[], api_key: str = "", models_module=None):
    resources = frictionless.Package(package_file).resources
    resource_names = [x.name for x in resources]
    logger.info(f"Updating data from {package_file} for {resource_names}")

    session = Session()
    if api_key:
        session.headers.update({"x-api-key": api_key})

    for resource in resources:
        if resource.name in skip:
            continue
        table_name = resource.name.replace("-", "").lower()

        logger.info(f"Getting all data for {table_name}")
        try:
            current_all = requests_get_all(session, server_url=api_url, endpoint=table_name)
        except fastapi.exceptions.RequestValidationError as e:
            logger.error(f"{resource} not valid table at {api_url}")
            raise fastapi.exceptions.RequestValidationError(e)
        except fastapi.HTTPException as e:
            logger.error(f"HTTP Error {e}")
            raise fastapi.HTTPException

        if len(current_all) == 0:
            current_index = []
            logger.warning(f"No data in {table_name}, using empty index.")
        else:
            current_index = current_all[current_all.columns[0]].to_list()
            logger.info(f"{len(current_index)} {table_name}s in data.")

        logger.info(f"Loading or updating each row in {table_name}")
        loaded_rows = []
        updated_rows = []
        unchanged_rows = []
        new_payloads: list = []

        with resource as resource:
            for row in resource.row_stream:
                row_pk = [x for x in row.values()][0]
                logger.debug(f"row: {row}")
                if row_pk is None:
                    break
                modelcreate = get_model(table_name, "create", models_module=models_module)
                try:
                    model = modelcreate(**row)
                except ValidationError as e:
                    logger.error(f"Invalid value in row {row_pk}: {e}")
                    raise ValidationError

                if row_pk not in current_index:
                    new_payloads.append(model.model_dump(mode="json"))
                    loaded_rows.append(row_pk)

                if row_pk in current_index:
                    current_row = current_all.loc[current_all[current_all.columns[0]] == row_pk]
                    current_row = current_row.loc[[x for x in current_row.index][0]].to_dict()
                    changed = any(current_row.get(k) != v for k, v in row.items())

                    if changed:
                        logger.debug(f"{row_pk} in database but changed. Updating...")
                        modelupdate = get_model(table_name, "update", models_module=models_module)
                        model = modelupdate(**row)
                        requests_update(
                            session, server_url=api_url, endpoint=table_name, pk=row_pk, model=model
                        )
                        updated_rows.append(row_pk)
                    else:
                        logger.debug(f"{row_pk} unchanged. Skipping...")
                        unchanged_rows.append(row_pk)

        if new_payloads:
            logger.debug(f"Bulk posting {len(new_payloads)} rows to {table_name}")
            requests_bulk_post(
                session,
                server_url=api_url,
                endpoint=table_name,
                rows=new_payloads,
                api_key=api_key,
            )

        logger.info(
            f"{resource.name.capitalize()} | Rows posted: {len(loaded_rows)}. Rows updated: {len(updated_rows)}. Rows unchanged: {len(unchanged_rows)}"
        )
        logger.debug(
            f"{resource.name.capitalize()}\nPosted: {loaded_rows}\nUpdated: {updated_rows}\nUnchanged: {unchanged_rows}"
        )
