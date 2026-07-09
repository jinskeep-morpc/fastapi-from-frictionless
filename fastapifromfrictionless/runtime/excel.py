import logging
import os
import pathlib
from contextlib import chdir
from datetime import datetime

import frictionless
import pandas as pd
from frictionless.formats import ExcelControl
from frictionless.resources import TableResource

from .http import requests_get_all

logger = logging.getLogger(__name__)


def empty_excel(schema_folder, output_filepath):
    schemas = [file for file in os.listdir(schema_folder) if file.endswith("schema.yaml")]

    with pd.ExcelWriter(output_filepath, engine="xlsxwriter") as writer:
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
            schema_descriptor = frictionless.Schema.from_descriptor(
                str(schema_folder / schema)
            ).to_descriptor()
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
    api_url: str,
    schema_folder: str | os.PathLike,
    output_filepath: str | os.PathLike,
    api_key: str = "",
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
    from requests import Session

    schemas = sorted(f for f in os.listdir(schema_folder) if f.endswith("schema.yaml"))
    session = Session()
    if api_key:
        session.headers.update({"x-api-key": api_key})

    with pd.ExcelWriter(output_filepath, engine="xlsxwriter") as writer:
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

            for col in columns:
                if col not in df.columns:
                    df[col] = None
            df = df[columns]

            df.to_excel(writer, sheet_name=name, index=False)
            logger.info(f"  {len(df)} rows written to sheet '{name}'")

        for sheet in writer.sheets:
            writer.sheets[sheet].autofit()

    session.close()
