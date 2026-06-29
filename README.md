# BotTG — Autonomous AI Content Platform

Telegram bot that automatically curates AI-related content from 11 web sources, scores it via LLM, and publishes posts to a Telegram channel.

## Architecture

```
Parsers (11 sources) → CPU Prefilter → LLM Scoring → DB → Adaptive Publisher → LLM Generation → Triple Review → Telegram Channel
```

### Data Sources
Habr, ProductHunt, GitHub Trending, HackerNews, FlowGPT, awesome-chatgpt-prompts, Reddit (ChatGPT, OpenAI, PromptEngineering), theresanaiforthat, futuretools

### Pipeline Stages
1. **Parsing** — 11 web scrapers run in parallel (ThreadPoolExecutor)
2. **CPU Pre-filter** — removes junk locally (CJK, short titles, non-AI content)
3. **LLM Theme Sieve** — fast Yes/No relevance check via DeepSeek
4. **LLM Scoring** — 5-dimension scoring (B2C, utility, savability, repostability, practical)
5. **Adaptive Publishing** — decides whether to publish based on quality, time, and category balance
6. **LLM Post Generation** — generates Telegram post using learned style profile
7. **Triple Review** — editor, reader, and admin perspectives validate the post
8. **Publishing** — sends to Telegram channel with feedback buttons

## Setup

### Environment Variables (.env)
```bash
BOT_TOKEN=your_telegram_bot_token
ADMIN_BOT_TOKEN=your_admin_telegram_bot_token
CHANNEL_ID=@your_channel

ROUTERAI_API_KEY=your_api_key
ROUTERAI_BASE_URL=https://routerai.ru/api/v1
ROUTERAI_MODEL=deepseek/deepseek-v4-pro
PROMPTAPP_PATH=C:\Users\your_user\PycharmProjects\promptapp

DB_HOST=localhost
DB_PORT=5432
DB_NAME=ai_channel_bot
DB_USER=postgres
DB_PASSWORD=your_password

# Optional: comma-separated Telegram user IDs (empty = all authorized)
ALLOWED_USERS=
```

`PROMPTAPP_PATH` is optional unless you use topic prompt generation commands.

### Local Run
```bash
pip install -r requirements.txt
python scoring_service.py
python main.py
python admin_bot.py
```

### Docker
```bash
docker-compose up --build
```

This starts:
- `bot` - main content bot
- `admin-bot` - admin control bot
- `scoring-service` - FastAPI scoring API on port `8001`
- `db` - PostgreSQL

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show help |
| `/addstyle` | Start style learning (forward posts) |
| `/done` | Save forwarded posts and extract style profile |
| `/style` | Show current style profile |
| `/stats` | Show 7-day publication statistics |

## Testing

```bash
pip install -r requirements.txt
pytest -v
pytest --cov=. --cov-report=term-missing
```

## Project Structure

```
BotTG/
├── main.py              — Entry point, bot commands, scheduler
├── database.py          — PostgreSQL async layer (asyncpg)
├── llm_generator.py     — LLM pipeline: scoring, generation, review
├── parsers.py           — 11 web scrapers
├── config.py            — Environment variable loader
├── test_parsers.py      — Parser unit tests (mocked)
├── test_llm_generator.py — LLM pipeline unit tests
├── test_database.py     — Database unit tests
├── test_main.py         — Bot commands and logic tests
├── Dockerfile           — Container build
├── docker-compose.yml   — Bot + PostgreSQL
└── requirements.txt     — Dependencies
```
