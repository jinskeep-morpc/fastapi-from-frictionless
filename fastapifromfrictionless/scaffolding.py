import logging

logger = logging.getLogger(__name__)


def build_database(schema_folder, db_filename):
    """Build model.py, app.py, database.py, and __init__.py from frictionless schemas.

    Parameters
    ----------
    schema_folder : str
        The location of the schemas.
    db_filename : str
        The name of the database file.
    """
    from fastapifromfrictionless import app, database, models

    models(schema_folder).build().save("models.py")
    app(schema_folder).build().save("app.py")
    database(schema_folder).build(db_filename).save("database.py")
    open("__init__.py", "w").close()
