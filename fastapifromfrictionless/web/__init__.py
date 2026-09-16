"""Server-rendered CRUD UI for a generated app.

The generated ``ui.py`` carries only a resource descriptor and calls
:func:`build_ui_router`. Keeping the view logic and templates here means they
can be tested once and fixed without regenerating every downstream project.
"""

from .router import build_ui_app

__all__ = ["build_ui_app"]
