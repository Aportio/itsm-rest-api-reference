"""
Run file for the Aportio ITSM-API reference implementation.
"""

# Import app variable from our app package, since Flask expects to see this here.
from itsm_api       import app
from itsm_api.views import init_db

init_db()

app.run(debug=app.config['DEBUG'], host='0.0.0.0')

