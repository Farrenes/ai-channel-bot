# BotTG Scoring Module Design

Date: 2026-06-27
Status: approved-for-implementation

## Goal

Добавить в проект отдельный универсальный модуль скоринга контента, который:

1. оценивает найденные материалы до генерации;
2. оценивает несколько вариантов Telegram-поста;
3. выбирает лучший вариант перед review/publish;
4. даёт объяснение результата и рекомендации на переписывание;
5. сохраняет результат в БД и остаётся совместимым с текущим API `/score`.

## Constraints

- `n8n` остаётся оркестратором.
- Бизнес-логика живёт в Python.
- Текущий `services/scoring.py` нельзя ломать резко: он остаётся совместимым фасадом.
- Старый pipeline и `scripts/smoke_test.py` должны продолжать работать.
- LLM scoring должен иметь deterministic fallback.

## Target Architecture

Новый канонический слой:

- `app/scoring/models.py`
- `app/scoring/config.py`
- `app/scoring/penalties.py`
- `app/scoring/explanations.py`
- `app/scoring/llm_analyzer.py`
- `app/scoring/scorer.py`

Слой совместимости:

- `services/scoring.py` остаётся public service для `/score`
- `api/routes/scoring.py` сохраняет envelope-контракт
- генерация может вызывать новый scorer для best-of-N выбора

## Functional Scope

### Input

`ContentScoreInput` должен поддерживать:

- текст;
- заголовок;
- источник;
- нишу;
- target audience;
- признаки формата поста;
- тип поста.

### Output

`ContentScoreResult` должен возвращать:

- `base_score`
- `penalty_score`
- `total_score`
- `decision`
- breakdown факторов
- breakdown штрафов
- сильные стороны
- слабые стороны
- рекомендации на улучшение
- рекомендуемый формат публикации

### Decision Rules

- `>= 78`: `publish`
- `58..77`: `improve`
- `< 58`: `reject`

## Scoring Logic

Итоговый score:

- positive factors через `SCORING_WEIGHTS`
- penalty factors через `PENALTY_WEIGHTS`
- `total_score = clamp(base_score - penalty_score, 0, 100)`

LLM слой нужен только для извлечения факторов и не должен быть обязательным для работы scorer.

## Integration Points

1. `/score`
   - старый endpoint продолжает работать;
   - при этом использует новый scorer для richer contract.

2. Generation best-of-N
   - генерация создаёт несколько вариантов;
   - scorer выбирает лучший;
   - для `improve` допускается до 2 итераций rewrite.

3. Persistence
   - `content_scores` для результатов скоринга;
   - `post_metrics` для последующей аналитики и обратной связи.

## Risk Controls

- weak opening penalty обязателен;
- Telegram format fit должен влиять и как positive factor, и как penalty;
- unsupported claims и duplicate/rewritten low-value должны штрафоваться отдельно;
- при отсутствии LLM использовать heuristic fallback.

## Agent Split

1. Architecture/compatibility:
   - main agent
2. Core scoring module:
   - worker
3. DB + tests:
   - worker
4. Integration with generation/service facade:
   - main agent

## Verification Target

Минимум:

- unit tests scorer/penalties/opening/decision;
- smoke-test pipeline;
- compile/import check для новых модулей;
- проверка совместимости `/score`.
