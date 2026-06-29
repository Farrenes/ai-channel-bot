---
title: BotTG Architecture Audit
date: 2026-06-27
status: draft
---

# BotTG Architecture Audit

Краткий срез текущей структуры проекта под MVP в логике:
`n8n` = оркестрация, `Python/FastAPI` = бизнес-логика, `PostgreSQL` = состояние, `Telegram` = канал вывода.

## 1) Существующие модули и назначение

| Модуль | Назначение | Комментарий |
|---|---|---|
| `main.py` | Основной Telegram-бот: сбор контента, выбор идеи, генерация, публикация, feedback, scheduler | Сейчас это самый перегруженный модуль |
| `admin_bot.py` | Админ-бот: управление темами, источниками, prompt generation, style workflow, stats | Дублирует часть команд и логики `main.py` |
| `database.py` | Async PostgreSQL-слой, таблицы, CRUD по идеям, постам, стилю, feedback | Здесь же есть инициализация схемы |
| `scoring_service.py` | FastAPI `/health` и `/score` для фильтрации/LLM scoring | Это отдельный сервис, уже близкий к целевой границе |
| `scoring/` | `prefilter`, `llm_scorer`, `engine`, `constants` | Локальная scoring-логика и правила |
| `llm_generator.py` | Генерация поста, style extraction, triple review, rewrite, deep research | Вся LLM-постобработка и проверки |
| `parsers.py` | RSS/HTML парсеры 11 источников | Сетевой scraping-контур с rate limit и sleep |
| `topic_config.py` | CRUD тем, источников, каналов, prompt links | Ядро конфигурации тем |
| `topic_prompt_manager.py` | Генерация и кэш prompt'ов через `promptapp` | Внешняя зависимость для prompt engineering |
| `config.py` | Загрузка env и валидация обязательных переменных | Также задает `NO_PROXY` |
| `run_all.py` | Локальный combined-runner для content bot и admin bot | Полезен как dev-утилита, не как целевой runtime |
| `Dockerfile`, `Dockerfile.scoring`, `docker-compose.yml` | Контейнеризация основного бота, scoring-сервиса и PostgreSQL | Нормальная операционная обвязка |
| `test_*.py` | Моковые тесты для основных модулей | Хорошая база для регрессии MVP |

## 2) Что можно переиспользовать для MVP

- `scoring_service.py` и `scoring/prefilter.py`: уже выделен отдельный HTTP-сервис для оценки кандидатов.
- `database.py`: готовый слой состояния для идей, постов, стиля, feedback и topic config.
- `topic_config.py` + `topic_prompt_manager.py`: уже есть модель тем и prompt lifecycle.
- `parsers.py`: готовый пул источников и паттерн добавления новых парсеров.
- `llm_generator.py`: можно переиспользовать как backend для generation/review/style API.
- `main.py`:
  - логику выбора идеи;
  - time-bucket/category balancing;
  - механику feedback-кнопок;
  - правила публикации.
- `test_*.py`: использовать как базу для стабилизации границ при выносе сервисов.

## 3) Что нужно добавить

- Явные API-обертки под целевую архитектуру:
  - `POST /topics`
  - `POST /sources/validate`
  - `POST /sources/fetch`
  - `POST /items/prefilter`
  - `POST /ideas/select`
  - `POST /context/build`
  - `POST /generation/post`
  - `POST /review/post`
  - `POST /review/rewrite`
  - `POST /telegram/publish`
  - `POST /feedback`
- Явный слой оркестрации в `n8n`:
  - schedule;
  - retries;
  - branching;
  - error handling;
  - SLA/limit control.
- Отдельные контракты для:
  - idempotent publish;
  - run metadata;
  - execution status;
  - audit log.
- Выделение health/status endpoints для всех сервисов, не только scoring.
- Если MVP требует роста, добавить очередь/ретраи на уровне оркестратора, а не в Telegram-боте.

## 4) Риски и нежелательные зоны изменения

- `main.py` и `admin_bot.py` уже содержат слишком много ролей. Рефакторить их без границ легко ломает весь runtime.
- `database.py` делает DDL на старте. Это удобно, но опасно для production-миграций.
- `scoring_service.py` сейчас и оценивает, и пишет в БД. Это скрытый side effect и источник дублей.
- `llm_generator.py` завязан на внешний LLM API и на БД профиля стиля.
- `parsers.py` активно ходит в сеть и местами использует `sleep`, `rate_limit`, нестабильный HTML scraping.
- `topic_prompt_manager.py` зависит от внешнего `promptapp`; без него prompt workflow падает.
- `scoring_engine.py` выглядит как legacy/дублирующий модуль. Его лучше не развивать как новый путь.
- Не стоит одновременно менять контракт БД, формат идей и генерацию поста: это три точки, где легко нарушить совместимость.

## 5) Рекомендуемый порядок реализации MVP

1. Зафиксировать границы сервисов: `Python/FastAPI` как business layer, `n8n` как orchestrator, `PostgreSQL` как state.
2. Оставить `scoring_service.py` первым стабильным HTTP-сервисом и вынести из него неявные side effects.
3. Формализовать `topics` и `sources` как API-контракты поверх `topic_config.py`.
4. Вынести `parsers.py` за HTTP-границу как отдельный fetch step.
5. Вынести `generate/review/rewrite/context` из `llm_generator.py` в отдельные endpoint'ы.
6. Оставить `main.py` только как runtime Telegram-канала или заменить его thin webhook/publisher-слоем.
7. После этого собирать n8n workflow: fetch -> prefilter -> score -> select -> build context -> generate -> review -> publish -> feedback.

## 6) Side effects и где n8n не должен жить

### Side effects сейчас

- `main.py`: polling, scheduler, Telegram send/edit, публикация в канал, update статусов в БД.
- `admin_bot.py`: polling, админ-команды, запись тем/источников/prompt state, генерация prompt'ов.
- `scoring_service.py`: внешний LLM вызов, запись scored ideas в БД.
- `llm_generator.py`: внешний LLM вызов, чтение/запись style profile, review/rewrite.
- `parsers.py`: HTTP scraping, rate limiting, sleep.
- `database.py`: создание таблиц/индексов при старте.
- `topic_prompt_manager.py`: вызов внешнего `promptapp` и сохранение prompt'ов.
- `config.py`: загрузка env и изменение `NO_PROXY`.

### Где n8n не должен жить

- Не в `main.py` и не в `admin_bot.py`: эти файлы должны оставаться runtime-обвязкой, а не местом для оркестрационной логики.
- Не внутри `database.py`: n8n не должен прятать в себе DDL, CRUD и схему состояния.
- Не внутри `parsers.py`: scraping-логика должна оставаться Python-кодом за endpoint'ом, а не коллекцией n8n-нод.
- Не внутри `llm_generator.py`/`scoring_service.py`: n8n должен вызывать их как сервисы, а не переиспределять их правила node-by-node.
- Не в `scoring_engine.py`: это не хороший дом для новой архитектуры, а скорее временный/legacy слой.

## Итог

Для MVP уже есть почти все ключевые кирпичи: парсеры, scoring, генерация, стиль, темы, PostgreSQL и Telegram-вывод. Самый большой долг сейчас не в функциональности, а в смешении ролей внутри `main.py`, `admin_bot.py` и `scoring_service.py`. Следующий безопасный шаг - закрепить сервисные границы и заставить `n8n` быть только оркестратором.
