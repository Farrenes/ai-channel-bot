# BotTG Scoring Module Execution Plan

Date: 2026-06-27

## Objective

Внедрить отдельный scoring-модуль и интегрировать его в BotTG без поломки текущего universal MVP pipeline.

## Workstreams

### Agent 1 — Core Scoring Worker

Write scope:

- `app/scoring/**`

Tasks:

1. создать модели, веса, penalties, explanations;
2. реализовать heuristic/LLM analyzer;
3. реализовать `score_content`;
4. реализовать `generate_and_select_best_post` helper на уровне scorer.

### Agent 2 — DB and Tests Worker

Write scope:

- `migrations/**`
- `tests/scoring/**`

Tasks:

1. добавить таблицы `content_scores`, `post_metrics`;
2. покрыть scorer unit-тестами;
3. подготовить проверку decision/opening/penalties.

### Main Agent — Integration and Verification

Write scope:

- `services/scoring.py`
- `services/generation.py`
- `api/routes/scoring.py` при необходимости
- `scripts/smoke_test.py` при необходимости

Tasks:

1. адаптировать старый scoring facade к новому модулю;
2. подключить scoring к generation best-of-N;
3. сохранить совместимость текущих tests/smoke path;
4. прогнать верификацию.

## Sequence

1. Зафиксировать дизайн.
2. Запустить двух workers с непересекающимися scope.
3. Параллельно main agent готовит integration points.
4. После возврата workers провести интеграцию.
5. Прогнать тесты и smoke-test.
6. Зафиксировать статус системы.

## Success Criteria

- новый `app/scoring` существует и импортируется;
- `/score` продолжает работать;
- generation умеет выбрать лучший вариант из нескольких;
- есть explanation и improvement suggestions;
- результаты можно сохранить в БД;
- smoke pipeline проходит.
