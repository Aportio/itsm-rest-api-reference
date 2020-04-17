"""
Run file for the Aportio ITSM-API reference implementation.
"""

# Import app variable from our app package, since Flask expects to see this here.
from itsm_api import app

app.run(debug=True)

# app.run(debug=False, host='0.0.0.0')
