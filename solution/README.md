# A2A Solution

플라스크(Flask) 기반 에이전트 레지스트리와 Vite 프런트엔드로 구성된 예제 서비스입니다. JSON 스토어에 에이전트 카드(Agent Card)를 보관하고, 정책·서명 검증과 관리자 인증을 거쳐 CRUD API를 제공합니다.

## 폴더 구조

| 경로 | 설명 |
| --- | --- |
| `app/` | Flask 백엔드 코드 (`solution/app/main.py` 가 진입점) |
| `frontend/` | Vite + React 웹 UI (선택 사항) |
| `data/` | 실행 시 사용하는 JSON 스토리지 (`agents.json`, `log.json`) |
| `tests/` | Pytest 기반 백엔드 테스트 |
| `Dockerfile`, `docker-compose.yml` | 컨테이너 실행 예시 |

## 요구 사항

- Python 3.10+
- Node 18+ (웹 UI가 필요할 경우)
- pip, npm

## 빠른 시작

```bash
# 1) 가상환경 생성 및 패키지 설치
python -m venv .venv
source .venv/bin/activate             # Windows: .\.venv\Scripts\Activate.ps1
pip install -r solution/requirements.txt

# 2) 백엔드 실행 (기본: http://127.0.0.1:3000)
python -m solution.app.main

# 3) (옵션) 프런트엔드 실행
(cd solution/frontend && npm install && npm run dev)
```

## 환경 변수 요약

| 키 | 기본값 | 설명 |
| --- | --- | --- |
| `AGENT_DOMAIN_WHITELIST` | `localhost` 포함 | 정책 검사 도메인 화이트리스트 (쉼표 구분) |
| `AGENT_IP_WHITELIST` | 없음 | 정책 검사 IP 화이트리스트 (쉼표 구분, CIDR 허용) |
| `EXTENSION_MAX_*` | `6/64/1024/2000` | 확장 필드 깊이/배열/문자열/노드 제한 |
| `SOLUTION_TENANTS`, `SOLUTION_TENANTS_JSON` | 기본 2개 | 테넌트 선택 목록 정의 |
| `AGENT_CARD_MAX_BYTES` | `2000` | 업로드 가능한 Agent Card 최대 바이트 |

`.env` 파일을 `solution/.env` 위치에 두면 대부분의 값이 자동으로 로드됩니다.

## 데이터 저장 방식

- `solution/data/agents.json`: 등록된 에이전트 메타데이터를 배열로 보관합니다. CRUD API가 모두 이 파일을 통해 데이터를 읽고 저장합니다.
- `solution/data/log.json`: `append_log()` 유틸리티를 통해 추가되는 활동 로그. `SOLUTION_DATA_ROOT`가 설정되면 해당 경로 아래 `data/` 를 사용합니다.
- 초기 실행 시 `repo.ensure_seed()`가 기본 데이터를 생성합니다. 테스트나 다른 환경에서 디렉터리를 바꾸고 싶다면 `SOLUTION_DATA_ROOT` 로 오버라이드하세요.

## API 개요

모든 보호된 엔드포인트는 JWT + 관리자 권한을 요구합니다 (`require_jwt`, `require_admin`). 일부 주요 엔드포인트는 다음과 같습니다.

| 메서드/경로 | 설명 |
| --- | --- |
| `POST /api/create-agent` | 에이전트 카드 등록 (자동 서명 포함) |
| `POST /api/update-agent` | 기존 카드 수정 및 재서명 |
| `POST /api/delete-agent` | 에이전트 소프트 삭제 |
| `GET /api/agents` | 전체 목록 조회 (관리자) |
| `POST /api/agents` | 간단 등록 API |
| `GET /api/agents/search` | JWT 테넌트 기반 검색 (Active 상태만) |
| `GET/POST /api/logs` | 로그 조회/추가 |
| `POST /api/jws/sign-card` | 관리자 전용 JWS 서명 위임 |
| `POST /api/jws/verify` | JWS 검증 프록시 |
| `POST /api/jws/resign-card` | signatures 배열을 단일 서명으로 재작성 |
| `GET /api/verify-jwt`, `/api/verify-admin` | 토큰/관리자 검증 헬스체크 |

## 커스터마이징 가이드

코어 기능은 `solution/app/core/` 아래에 모듈별로 분리되어 있어 쉽게 커스터마이징할 수 있습니다.

- **로깅 (`core/logging.py`)**: `append_log()`를 수정해 다른 스토리지(CloudWatch, DB)로 전송하거나 `SOLUTION_MAX_LOG_ENTRIES` 로 보존 정책을 조절할 수 있습니다.
- **정책 (`core/policy.py`)**: 도메인/IP 화이트리스트와 extension 제한은 환경 변수로 조정하고, 추가 정책을 구현하려면 `PolicyEvaluator`를 확장하면 됩니다.
- **인증 (`core/auth.py`)**: USERME 호출이나 관리자 판별 로직을 다른 서비스/필터로 교체 가능합니다.
- **저장소 (`core/repo.py`)**: 현재는 JSON 파일이지만, 함수 구현만 교체하면 DB/외부 API를 사용할 수 있습니다.
- **테넌트 (`core/tenants.py`)**: `SOLUTION_TENANTS(_JSON)` 환경 변수를 통해 대상 테넌트 목록을 손쉽게 바꿀 수 있습니다.
- **검증 (`core/validators.py`, `core/signatures.py`)**: 스키마, 최대 바이트, JWS 구조검사 등을 조직 정책에 맞게 조절하세요.

README 수준에서 필요한 사용자 설정은 API와 core 레이어의 의존 관계만 확인하면 되며, API 함수는 대부분 core 모듈을 thin wrapper로 사용합니다.

필요한 내용이 README에 없거나 추가 가이드가 필요하면 `solution/app/core/` 각 모듈의 주석을 참고하세요. 모두 한글 주석으로 정리돼 있어 개별 기능을 찾기 쉽습니다.

## Docker

Build and start the app + Redis with Docker Compose:

```sh
docker compose up -d --build
```

- App listens on http://localhost:3000.
- Uses `.env` for settings; Compose also wires `REDIS_URL` to the bundled Redis.
- Data under `/app/data` is kept in the `app_data` volume; Redis persistence lives in `redis_data`.
- View logs with `docker compose logs -f app`.
