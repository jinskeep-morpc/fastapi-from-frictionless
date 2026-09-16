import logging

logger = logging.getLogger(__name__)


def build_database(schema_folder, db_filename, with_ui: bool = False, skip_ui=None):
    """Build model.py, app.py, database.py, and __init__.py from frictionless schemas.

    Parameters
    ----------
    schema_folder : str
        The location of the schemas.
    db_filename : str
        The name of the database file.
    with_ui : bool
        Also generate ui.py, a browser CRUD interface over the same schemas.
    skip_ui : list[str] | None
        Resources to omit from the UI, e.g. a table too large to browse.
    """
    from fastapifromfrictionless import app, database, models
    from fastapifromfrictionless.uigen import ui

    models(schema_folder).build().save("models.py")
    app(schema_folder, with_ui=with_ui).build().save("app.py")
    if with_ui:
        ui(schema_folder, skip=skip_ui).build().save("ui.py")
    database(schema_folder).build(db_filename).save("database.py")
    open("__init__.py", "w").close()
