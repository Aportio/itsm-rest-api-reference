"""
Flask application for the Aportio ITSM-API reference implementation.
"""

from flask import Flask

app = Flask(__name__)

# Apply the settings in our configuration file
app.config.from_object('config')

# We may not use the views in this module, but the way Flask structures itself, the views
# are required here. Thus, we ignore the style warning.
from itsm_api import views   # noqa: F401
