# BotTG Agent Guidance

Read these first:

- `docs/PROJECT_BRIEF.md`
- `docs/PROJECT_HANDOFF.md`
- `docs/DECISIONS.md`

Run commands:

- `pip install -r requirements.txt`
- `uvicorn api.main:app --host 0.0.0.0 --port 8000`
- `python scoring_service.py`
- `python main.py`
- `python admin_bot.py`
- `pytest -v`

Read first:

- `api/`
- `services/`
- `migrations/`
- `database.py`
- `main.py`
- `admin_bot.py`

Do not break:

- topic profile contract
- billing idempotency
- publish idempotency
- asyncpg/PostgreSQL state model
- existing Telegram bot commands
- n8n-as-orchestrator boundary

Notes:

- `n8n` should call API endpoints, not own business logic
- `main.py` and `admin_bot.py` overlap; keep changes scoped
- if git state is needed, verify it explicitly in the shell because it may be unavailable in some sessions

