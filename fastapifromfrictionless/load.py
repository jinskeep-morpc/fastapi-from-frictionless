import logging

from pydantic import ValidationError
from requests import HTTPError

logger = logging.getLogger(__name__)

import os
import fastapi
import pandas as pd

def empty_excel(folder, filename):
    import frictionless
    import pandas as pd
    import os

    schemas = [file for file in os.listdir(folder) if file.endswith('schema.yaml')]

    with pd.ExcelWriter(filename) as writer:
        logger.info(f"Writing empty excel file ({filename}) based on schemas as {folder}.")
        for schema in schemas:
            name = schema.replace('.schema.yaml', '')
            schema = frictionless.Schema(os.path.join(folder, schema))
            fields = schema.field_names
            logger.info(f"Creating table: {name} Fields: {fields}")
            df = pd.DataFrame(data=[], columns=fields)
            df.set_index(schema.primary_key).to_excel(writer, sheet_name=name)
        for sheet in writer.sheets:
            writer.sheets[sheet].autofit()

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
        
def requests_post(server_url: str | os.PathLike, endpoint: str, model) -> pd.DataFrame:
    import os
    import requests
    import pandas as pd

    logger.debug(f"Posting {model.model_dump_json()} to {server_url}/{endpoint}.")
    r = requests.post(f'{os.path.join(server_url, endpoint)}', data=model.model_dump_json())
    logger.debug(f"{r.content}")
    r.raise_for_status()
    json = r.json()
    r.close()

    return json

def requests_get_all(server_url: str | os.PathLike, endpoint: str) -> pd.DataFrame:
    import os
    import requests
    import pandas as pd

    url = f'{os.path.join(server_url, endpoint, 'all')}'
    logger.debug(f"Getting all from at {url}")
    r = requests.get(url)
    r.raise_for_status()
    json = r.json()
    r.close()

    return pd.DataFrame.from_dict(json)

def requests_update(server_url: str | os.PathLike, endpoint: str, pk, model) -> pd.DataFrame:
    import os
    import requests
    import pandas as pd

    logger.debug(f"Updating {pk} at {server_url}/{endpoint} to {model.model_dump_json()}")
    r = requests.patch(f'{os.path.join(server_url, endpoint, pk)}', data=model.model_dump_json())
    r.raise_for_status()
    json = r.json()
    r.close()

    return json

def update_api_from_package(api_url, package_file):
    import pandas as pd
    import frictionless

    # Load sheet names
    resources = frictionless.Package(package_file).resources
    resource_names = [x.name for x in resources]
    logger.info(f"Updating data from {package_file} for {resource_names}")

    # For each sheet..
    for resource in resources:
        table_name = resource.name.replace('-','').lower()
        # Get current state of data on api
        logger.info(f"Getting all data for {table_name}")
        try:
            current_all = requests_get_all(server_url=api_url, endpoint=table_name)
        except fastapi.exceptions.RequestValidationError as e:
            logger.error(f"{resource} not valid table at {api_url}")
            raise fastapi.exceptions.RequestValidationError(e)
        except fastapi.HTTPException as e:
            logger.error(f"HTTP Error {e}")
            raise fastapi.HTTPException

        # Extract index from current data
        if len(current_all) == 0:
            current_index = [] # empty set if no data in api
            logger.warning(f'No data in {table_name}, using empty index.')
        else: 
            current_index = current_all[current_all.columns[0]].to_list()
            logger.info(f"{len(current_index)} {table_name}s in data.")
        
        # For each row in table
        logger.info(f"Loading or updating each row in {table_name}")
        loaded_rows = []
        updated_rows = []
        unchanged_rows = []

        # Open resource and stream rows
        resource.open()
        for row in resource.row_stream:
            row_pk = [x for x in row.values()][0]     # the first row value (primary key)       
            if row_pk == None:
                break         
            # Convert that row into a model
            modelcreate = get_model(table_name, 'create')  # fetch the model 
            try:
                model = modelcreate(**row)                # create model
            except ValidationError as e:
                logger.error(f"Invalid value in row {row_pk}: {e}")
                raise ValidationError

            # Check if the row exists in the current api table
            if row_pk not in current_index:
                # if not, post to api
                logger.debug(f"Posting row: {row}")
                response = requests_post(server_url=api_url, endpoint=table_name, model=model)
                loaded_rows.append(row_pk)

            if row_pk in current_index:
                # if it is, check if it is the same
                current_row = current_all.loc[current_all[current_all.columns[0]]==row_pk]
                current_row = current_row.loc[[x for x in current_row.index][0]].to_dict()

                for k,v in row.items():
                    changed = False
                    if current_row[k] == v:
                        continue
                    else:
                        changed = True

                # if it is changed, update.
                if changed:
                    logger.debug(f'{row_pk} in database but changed. Updating...')
                    modelupdate = get_model(table_name, 'update')
                    model = modelupdate(**row)
                    response = requests_update(server_url=api_url, endpoint=table_name, pk=row_pk, model=model)
                    updated_rows.append(row_pk)
                else:
                    logger.debug(f"{row_pk} unchanged. Skipping...")
                    unchanged_rows.append(row_pk)
        resource.close()

        logger.info(f"{resource.name.capitalize()} | Rows posted: {len(loaded_rows)}. Rows updated: {len(updated_rows)}. Rows unchanged: {len(unchanged_rows)}")
        logger.debug(f"{resource.name.capitalize()}\nPosted: {loaded_rows}\nUpdated: {updated_rows}\nUnchanged: {unchanged_rows}")


