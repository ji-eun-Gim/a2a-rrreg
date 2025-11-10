# A2A Solution (Flask + WebUI)

- app: Flask backend (serves API + static)
- webui: npm (Vite) frontend
- data: JSON storage (agents.json, log.json)

## Dev

python -m venv .venv
# Windows: . .venv/Scripts/Activate.ps1
# Unix: source .venv/bin/activate
pip install -r solution/requirements.txt
python -m solution.app.main  # runs on :3000

