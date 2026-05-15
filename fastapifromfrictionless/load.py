import logging
import pathlib
import stat

from pydantic import ValidationError
from requests import HTTPError, JSONDecodeError, Session

logger = logging.getLogger(__name__)

import os

import fastapi
import pandas as pd


def build_database(schema_folder, db_filename):
    """
    Builds model.py, app.py, database.py, and __init__.py files to start a FastAPI instance based on frictionless schemas.

    Parameters
    ----------
    schema_folder : str
        The location of the schemas
    db_filename : str
        The name of the database.
    """

    from fastapifromfrictionless import app, database, models

    models(schema_folder).build().save("models.py")

    app(schema_folder).build().save("app.py")

    database(schema_folder).build(db_filename).save("database.py")

    open("__init__.py", "w").close()


def empty_excel(schema_folder, output_filepath):
    import os

    import frictionless
    import pandas as pd

    schemas = [file for file in os.listdir(schema_folder) if file.endswith("schema.yaml")]

    with pd.ExcelWriter(output_filepath) as writer:
        logger.info(
            f"Writing empty excel file ({output_filepath}) based on schemas in {schema_folder}."
        )
        for schema in schemas:
            name = schema.replace(".schema.yaml", "")
            schema = frictionless.Schema(os.path.join(schema_folder, schema))
            fields = schema.field_names
            logger.info(f"Creating table: {name} Fields: {fields}")
            df = pd.DataFrame(data=[], columns=fields)
            df.to_excel(writer, sheet_name=name, index=False)
        for sheet in writer.sheets:
            writer.sheets[sheet].autofit()


def create_package(folder: str | os.PathLike, filename: str | os.PathLike, validate: bool = True):
    import os
    from contextlib import chdir
    from datetime import datetime

    import frictionless
    from frictionless.formats import ExcelControl
    from frictionless.resources import TableResource

    stem = pathlib.Path(filename).stem
    # chdir to the Excel file's directory so frictionless can reference it by
    # basename (relative path). Absolute paths are rejected by frictionless as
    # "unsafe" during package.validate(). Schema files and the output YAML are
    # accessed via absolute paths constructed from the resolved schema folder.
    excel_dir = pathlib.Path(filename).resolve().parent
    local_filename = pathlib.Path(filename).name
    schema_folder = pathlib.Path(folder).resolve()

    with chdir(excel_dir):
        schemas = [x for x in os.listdir(schema_folder) if x.endswith("schema.yaml")]
        resources: list = []

        for schema in schemas:
            logger.info(f"appending {schema} to package")
            schema_name = schema.replace(".schema.yaml", "")
            # Strip foreign keys before standalone infer — frictionless requires the
            # full package context to resolve cross-resource FK references.
            schema_descriptor = frictionless.Schema.from_descriptor(str(schema_folder / schema)).to_descriptor()
            schema_descriptor.pop("foreignKeys", None)
            resource = TableResource(
                name=schema_name,
                path=local_filename,
                control=ExcelControl(sheet=schema_name),
                schema=frictionless.Schema.from_descriptor(schema_descriptor),
                dialect=frictionless.Dialect(skip_blank_rows=True),
            )
            resource.infer(stats=True)
            resources.append(resource)

        package = frictionless.Package(
            name=stem,
            resources=resources,
            version="0.0.1",
            created=datetime.now().isoformat(),
        )

        package_yaml_path = str(schema_folder / (stem + ".package.yaml"))
        logger.info(f"Saving package to {package_yaml_path}")
        package.to_yaml(package_yaml_path)

        if validate:
            valid = package.validate()
            if valid.valid:
                logger.info(f"{package_yaml_path} is a valid package.")
            else:
                logger.error(f"{package_yaml_path} is an invalid package. Report below:\n{valid}")
                raise RuntimeError

    return package


def dump_to_excel(
    api_url: str, schema_folder: str | os.PathLike, output_filepath: str | os.PathLike, api_key: str = ""
):
    """Fetch all records from each API endpoint and write them to an Excel workbook.

    One sheet per schema, columns ordered to match schema field names.  If an
    endpoint returns no rows the sheet is still created with the correct headers
    so the file can be re-ingested by ``update_api_from_package`` without errors.

    Parameters
    ----------
    api_url:
        Base URL of the running FastAPI app (e.g. ``"http://localhost:8000"``).
    schema_folder:
        Directory containing ``*.schema.yaml`` files.
    output_filepath:
        Destination path for the ``.xlsx`` file.
    """
    import frictionless
    from requests import Session

    schemas = sorted(f for f in os.listdir(schema_folder) if f.endswith("schema.yaml"))
    session = Session()
    if api_key:
        session.headers.update({"x-api-key": api_key})

    with pd.ExcelWriter(output_filepath) as writer:
        logger.info(f"Dumping API data to {output_filepath}")
        for schema_file in schemas:
            name = schema_file.replace(".schema.yaml", "")
            endpoint = name.replace("-", "").lower()
            schema = frictionless.Schema(os.path.join(schema_folder, schema_file))
            columns = schema.field_names

            logger.info(f"Fetching {endpoint}")
            try:
                df = requests_get_all(session, server_url=api_url, endpoint=endpoint)
            except Exception as e:
                logger.error(f"Could not fetch {endpoint}: {e}")
                df = pd.DataFrame(columns=columns)

            # Reorder/filter to match schema column order; fill missing columns with NaN
            for col in columns:
                if col not in df.columns:
                    df[col] = None
            df = df[columns]

            df.to_excel(writer, sheet_name=name, index=False)
            logger.info(f"  {len(df)} rows written to sheet '{name}'")

        for sheet in writer.sheets:
            writer.sheets[sheet].autofit()

    session.close()


def get_model(name: str, type: str):
    import models
    from sqlmodel.main import SQLModelMetaclass

    name = f"{name.capitalize()}{type.capitalize()}"
    all_models = dir(models)
    for model in all_models:
        if model.casefold() == name.casefold():
            matched_model = getattr(models, model)

    if isinstance(matched_model, SQLModelMetaclass):
        return matched_model
    else:
        logger.error(f"No models for {name}.")
        raise ValueError


def requests_post(
    session: Session | None, server_url: str | os.PathLike, endpoint: str, model
) -> pd.DataFrame:
    import os

    import pandas as pd
    import requests

    if session is None:
        session = requests.Session()
    logger.debug(f"Posting {model.model_dump_json()} to {server_url}/{endpoint}.")
    r = session.post(f"{os.path.join(server_url, endpoint)}", data=model.model_dump_json())
    logger.debug(r.content.decode("utf-8", errors="replace"))
    r.raise_for_status()
    json = r.json()
    r.close()

    return json


def requests_get_all(
    session: Session | None, server_url: str | os.PathLike, endpoint: str
) -> pd.DataFrame:
    import os

    import pandas as pd
    import requests

    if session is None:
        session = requests.Session()
    url = f"{os.path.join(server_url, endpoint, 'all')}"
    logger.debug(f"Getting all from at {url}")
    json = []
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
        r.close()

    return pd.DataFrame.from_dict(json)


def requests_update(
    session: Session | None, server_url: str | os.PathLike, endpoint: str, pk, model
) -> pd.DataFrame:
    import os

    import pandas as pd
    import requests

    if session is None:
        session = requests.Session()
    logger.debug(f"Updating {pk} at {server_url}/{endpoint} to {model.model_dump_json()}")
    r = session.patch(f"{os.path.join(server_url, endpoint, pk)}", data=model.model_dump_json())
    r.raise_for_status()
    json = r.json()
    r.close()

    return json


def update_api_from_package(api_url, package_file, skip=[], api_key: str = ""):
    import frictionless
    import pandas as pd
    from requests import Session

    # Load sheet names
    resources = frictionless.Package(package_file).resources
    resource_names = [x.name for x in resources]
    logger.info(f"Updating data from {package_file} for {resource_names}")

    session = Session()
    if api_key:
        session.headers.update({"x-api-key": api_key})

    # For each sheet..
    for resource in resources:
        if resource.name in skip:
            continue
        table_name = resource.name.replace("-", "").lower()
        # Get current state of data on api
        logger.info(f"Getting all data for {table_name}")
        try:
            current_all = requests_get_all(session, server_url=api_url, endpoint=table_name)
        except fastapi.exceptions.RequestValidationError as e:
            logger.error(f"{resource} not valid table at {api_url}")
            raise fastapi.exceptions.RequestValidationError(e)
        except fastapi.HTTPException as e:
            logger.error(f"HTTP Error {e}")
            raise fastapi.HTTPException

        # Extract index from current data
        if len(current_all) == 0:
            current_index = []  # empty set if no data in api
            logger.warning(f"No data in {table_name}, using empty index.")
        else:
            current_index = current_all[current_all.columns[0]].to_list()
            logger.info(f"{len(current_index)} {table_name}s in data.")

        # For each row in table
        logger.info(f"Loading or updating each row in {table_name}")
        loaded_rows = []
        updated_rows = []
        unchanged_rows = []

        # Open resource and stream rows
        with resource as resource:
            for row in resource.row_stream:
                row_pk = [x for x in row.values()][0]  # the first row value (primary key)
                logger.debug(f"row: {row}")
                if row_pk is None:
                    break
                # Convert that row into a model
                modelcreate = get_model(table_name, "create")  # fetch the model
                try:
                    model = modelcreate(**row)  # create model
                except ValidationError as e:
                    logger.error(f"Invalid value in row {row_pk}: {e}")
                    raise ValidationError

                # Check if the row exists in the current api table
                if row_pk not in current_index:
                    # if not, post to api
                    logger.debug(f"Posting row: {row}")
                    requests_post(session, server_url=api_url, endpoint=table_name, model=model)
                    loaded_rows.append(row_pk)

                if row_pk in current_index:
                    # if it is, check if it is the same
                    current_row = current_all.loc[current_all[current_all.columns[0]] == row_pk]
                    current_row = current_row.loc[[x for x in current_row.index][0]].to_dict()

                    for k, v in row.items():
                        changed = False
                        if current_row[k] == v:
                            continue
                        else:
                            changed = True

                    # if it is changed, update.
                    if changed:
                        logger.debug(f"{row_pk} in database but changed. Updating...")
                        modelupdate = get_model(table_name, "update")
                        model = modelupdate(**row)
                        requests_update(
                            session, server_url=api_url, endpoint=table_name, pk=row_pk, model=model
                        )
                        updated_rows.append(row_pk)
                    else:
                        logger.debug(f"{row_pk} unchanged. Skipping...")
                        unchanged_rows.append(row_pk)

        logger.info(
            f"{resource.name.capitalize()} | Rows posted: {len(loaded_rows)}. Rows updated: {len(updated_rows)}. Rows unchanged: {len(unchanged_rows)}"
        )
        logger.debug(
            f"{resource.name.capitalize()}\nPosted: {loaded_rows}\nUpdated: {updated_rows}\nUnchanged: {unchanged_rows}"
        )
