__version__ = "0.2.18"

import logging

logger = logging.getLogger(__name__)

from .load import *
from .logging_config import configure_logging

# Generator classes require jinja2/frictionless ([generate] extra). Guard so
# the base package is importable in runtime environments without those deps.
try:
    from .app import app
    from .database import database
    from .model import models
    from .schema_context import SchemaContext
    from .validate import assert_schemas_valid, validate_schemas
except ImportError:
    pass
