from flask import Blueprint

# API 라우트를 연결할 Blueprint
api_bp = Blueprint('api_bp', __name__, url_prefix='/api')

# Blueprint 등록을 위해 라우트 모듈 임포트
from . import verify_jwt  # noqa: E402,F401
from . import create_agent  # noqa: E402,F401
from . import verify_jws  # noqa: E402,F401
from . import update_agent  # noqa: E402,F401
from . import delete_agent  # noqa: E402,F401
from . import search_agents  # noqa: E402,F401
from . import agents_basic  # noqa: E402,F401
from . import logs_api  # noqa: E402,F401
from . import rulesets_api  # noqa: E402,F401
