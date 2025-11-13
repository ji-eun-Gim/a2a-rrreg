from flask import Blueprint

# Expose a blueprint for API routes
api_bp = Blueprint('api_bp', __name__, url_prefix='/api')

# Import route modules to attach endpoints
from . import verify_jwt  # noqa: E402,F401
from . import create_agent  # noqa: E402,F401
from . import verify_jws  # noqa: E402,F401
from . import update_agent  # noqa: E402,F401
from . import delete_agent  # noqa: E402,F401
from . import search_agents  # noqa: E402,F401
from . import agents_basic  # noqa: E402,F401
from . import logs_api  # noqa: E402,F401
