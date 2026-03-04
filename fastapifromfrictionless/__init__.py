__version__ = "0.0.01"

import logging
logger = logging.getLogger(__name__)

from app import app
from model import models
from database import database

