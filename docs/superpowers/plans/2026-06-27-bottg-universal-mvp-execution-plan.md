# BotTG Universal MVP Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** turn BotTG into a universal, n8n-orchestrated Telegram autoposting MVP with structured topic profiles, source validation, universal scoring, generation/review, idempotent publishing, and smoke-tested end-to-end flow.

**Architecture:** n8n remains the control plane only. Python/FastAPI owns business logic and validation. PostgreSQL owns canonical state and event logging. The MVP supports free-text topic intake, RSS/HTML source validation and fetch, scoring with strategy-dependent weights, generation, review, idempotent publish, and a complete event trail.

**Tech Stack:** n8n, Python, FastAPI, PostgreSQL, asyncpg, Telegram Bot API, Mermaid, Obsidian Markdown, pytest.

## Global Constraints

- n8n is only an orchestrator and must not contain core business logic.
- The product is universal, not niche-specific.
- The MVP must support free-text topic intake, RSS, simple HTML, short Telegram posts, digest posts, educational posts, review, publish idempotency, and event logging.
- High-risk topics must be restricted or require human approval.
- Publishing must be idempotent.
- Every important stage must write to `event_log`.
- Do not add non-MVP channels or complex analytics.
- Preserve compatibility with current modules unless migration requires change.

---

## File Structure

- Create: `docs/analysis/2026-06-27-bottg-architecture-audit.md`
- Create/Modify: `migrations/`
- Modify: `database.py`
- Create: `api/routes/topics.py`
- Create: `api/routes/sources.py`
- Create: `api/routes/scoring.py`
- Create: `api/routes/generation.py`
- Create: `api/routes/review.py`
- Create: `api/routes/telegram.py`
- Create: `services/topic_profile.py`
- Create: `services/source_validation.py`
- Create: `services/scoring.py`
- Create: `services/generation.py`
- Create: `services/review.py`
- Create: `services/telegram_publish.py`
- Modify: `scoring_service.py`
- Modify: `llm_generator.py`
- Create: `n8n/workflows/`
- Create: `scripts/smoke_test.py`

## Agent Split

- Agent 1: architecture audit and current-module map.
- Agent 2: database schema and migrations.
- Agent 3: topic profile API.
- Agent 4: source validation and fetch API.
- Agent 5: universal scoring contract and service split.
- Agent 6: generation and review API.
- Agent 7: publish idempotency and event log.
- Agent 8: n8n workflow templates.
- Agent 9: smoke test / end-to-end verification.

### Task 1: Architecture Audit

**Files:**
- Create: `docs/analysis/2026-06-27-bottg-architecture-audit.md`

**Interfaces:**
- Consumes: current repository modules and docs.
- Produces: file map, reuse map, risk map, and recommended next implementation order.

- [ ] **Step 1: map current modules**

Document the current state of:
- `main.py`
- `database.py`
- `llm_generator.py`
- `parsers.py`
- `scoring_service.py`
- `topic_config.py`
- `topic_prompt_manager.py`

- [ ] **Step 2: identify reuse and risks**

Capture:
- what can be reused as-is;
- what needs a thin API wrapper;
- what should not be touched unless necessary;
- where current side effects exist.

- [ ] **Step 3: verify audit output exists**

Run: `Select-String -LiteralPath "docs/analysis/2026-06-27-bottg-architecture-audit.md" -Pattern "main.py","database.py","scoring_service.py","llm_generator.py"`

Expected: all core modules mentioned.

### Task 2: Database and Migrations

**Files:**
- Create/Modify: `migrations/*`
- Modify: `database.py`

**Interfaces:**
- Consumes: architecture audit and workflow/data requirements.
- Produces: tables, indexes, enums/statuses, compatibility helpers.

- [ ] **Step 1: add schema for topic/source/candidate/post/event**

Add migrations for:
- `topic_profiles` or expanded `topic_configs`
- `content_sources`
- `source_validation_runs`
- `source_fetch_runs`
- `content_candidates`
- `generated_posts`
- `usage_counters`
- `event_log`

- [ ] **Step 2: add indexes and constraints**

Add indexes for:
- topic lookup
- source lookup
- candidate queue
- idempotent publish lookup
- event log queries

- [ ] **Step 3: preserve compatibility**

Keep current `ideas_pool`, `published_posts`, `channel_style_profile`, and `post_feedback` working during transition.

- [ ] **Step 4: verify migrations**

Run: `pytest test_database.py -v`

Expected: database tests pass or fail with a concrete migration gap only.

### Task 3: Topic Profile API

**Files:**
- Create: `api/routes/topics.py`
- Create: `services/topic_profile.py`

**Interfaces:**
- Consumes: free-text topic and optional context.
- Produces: structured topic profile with type, risk, strategy, format, language, tone, depth, and approval flag.

- [ ] **Step 1: implement `POST /topics/profile`**

Input:
- `raw_topic`
- optional sample sources
- optional channel context

Output fields:
- `raw_topic`
- `normalized_topic`
- `topic_type`
- `domain`
- `risk_level`
- `content_strategy`
- `default_post_format`
- `language`
- `tone`
- `depth`
- `allowed_source_types`
- `blocked_source_types`
- `requires_human_approval`

- [ ] **Step 2: add non-LLM fallback**

If LLM is unavailable, return a deterministic profile using rules and keyword classification.

- [ ] **Step 3: add tests**

Run: `pytest -k topic_profile -v`

Expected: profile endpoint returns a stable envelope and fallback works.

### Task 4: Source Validation API

**Files:**
- Create: `api/routes/sources.py`
- Create: `services/source_validation.py`

**Interfaces:**
- Consumes: URL, topic profile, plan code.
- Produces: source metadata, support level, parser strategy, risk flags, confirmation need.

- [ ] **Step 1: implement `POST /sources/validate`**

Classify sources into:
- `supported`
- `partially_supported`
- `unsupported`
- `suspicious`
- `high_risk`
- `blocked`

- [ ] **Step 2: implement `POST /sources/fetch`**

Support MVP fetch modes:
- RSS
- simple HTML

- [ ] **Step 3: store source metadata**

Persist:
- `source_category`
- `source_trust_level`
- `supported_level`
- `parser_strategy`
- `content_license_risk`
- `requires_confirmation`

- [ ] **Step 4: add tests**

Run: `pytest -k source_validation -v`

Expected: supported sources pass, unsupported/suspicious sources do not break the pipeline.

### Task 5: Universal Scoring

**Files:**
- Modify: `scoring_service.py`
- Create: `services/scoring.py`

**Interfaces:**
- Consumes: content candidates and topic/content strategy.
- Produces: universal score contract and optional DB write.

- [ ] **Step 1: define universal score contract**

Support:
- `relevance_score`
- `quality_score`
- `novelty_score`
- `authority_score`
- `risk_score`
- `virality_score`
- `evergreen_score`
- `commercial_score`
- `final_score`

- [ ] **Step 2: add strategy-based weights**

Make scoring weights depend on `content_strategy`.

- [ ] **Step 3: split scoring from persistence**

Add `save_to_db: true/false` so scoring can be pure when needed.

- [ ] **Step 4: add tests**

Run: `pytest -k scoring -v`

Expected: strategy-specific scoring changes weights correctly and does not require DB writes unless requested.

### Task 6: Generation and Review

**Files:**
- Create: `api/routes/generation.py`
- Create: `api/routes/review.py`
- Create: `services/generation.py`
- Create: `services/review.py`
- Modify: `llm_generator.py`

**Interfaces:**
- Consumes: topic profile, content strategy, tone, depth, post format.
- Produces: generated posts and review verdicts.

- [ ] **Step 1: implement `POST /generation/post`**

The generator must use:
- topic profile
- content strategy
- tone
- depth
- default post format

- [ ] **Step 2: implement `POST /review/post`**

The review gate must enforce:
- safety rules first
- high-risk restrictions
- fallback or rewrite limits

- [ ] **Step 3: implement `POST /review/rewrite`**

Rewrite should be limited and explicit, not endless.

- [ ] **Step 4: add tests**

Run: `pytest -k "generation or review" -v`

Expected: generation and review return envelope-shaped responses and high-risk content does not auto-pass.

### Task 7: Publish Idempotency

**Files:**
- Create: `api/routes/telegram.py`
- Create: `services/telegram_publish.py`
- Modify: `database.py`

**Interfaces:**
- Consumes: approved generated post, `idempotency_key`, target channel.
- Produces: persisted publish result and event log entries.

- [ ] **Step 1: implement `POST /telegram/publish`**

Protect against duplicates by checking:
- `generated_post_id`
- `idempotency_key`
- `telegram_message_id`
- `status == published`

- [ ] **Step 2: write publish and event log records**

Persist publish results and event events atomically where possible.

- [ ] **Step 3: add tests**

Run: `pytest -k telegram_publish -v`

Expected: repeated calls with the same idempotency key do not publish twice.

### Task 8: n8n Workflow Templates

**Files:**
- Create: `n8n/workflows/*`
- Create: `docs/n8n/README.md`

**Interfaces:**
- Consumes: API endpoints and workflow contracts.
- Produces: importable workflow templates.

- [ ] **Step 1: create minimal workflow set**

Workflows:
- WF01 Topic/Profile setup
- WF02 Source validation
- WF04 Scheduled collection
- WF05 Scoring
- WF06 Generation
- WF07 Review
- WF08 Publishing
- WF10 Error handling

- [ ] **Step 2: keep workflows thin**

n8n should only call API endpoints and move statuses.

- [ ] **Step 3: document required env vars**

Document only the variables needed for MVP import/run.

### Task 9: Smoke Test

**Files:**
- Create: `scripts/smoke_test.py`

**Interfaces:**
- Consumes: one source URL, one topic profile, one mock or real publish path.
- Produces: end-to-end pass/fail report.

- [ ] **Step 1: create full pipeline smoke test**

Pipeline:
source -> fetch -> candidate -> score -> generate -> review -> publish/mock_publish -> event_log

- [ ] **Step 2: support mock Telegram publish**

If Telegram is unavailable, the smoke test should use mock publish and still validate idempotency and logging.

- [ ] **Step 3: verify test**

Run: `pytest -k smoke -v`

Expected: smoke test completes the full pipeline or fails with a precise stage-level error.

## Execution Rules

- Run tasks in order.
- Do not expand scope beyond the MVP list.
- Do not let n8n accumulate business logic.
- Keep API responses envelope-shaped.
- Keep side effects explicit.
- Keep source/review/publish idempotent where required.

## Completion Criteria

The MVP is acceptable when this flow works:

1. User submits free-text topic.
2. System builds a structured topic profile.
3. URL source is validated and classified.
4. Materials are fetched.
5. Candidates are scored with strategy-dependent weights.
6. One candidate becomes a Telegram post.
7. Review gate passes or requests rewrite.
8. Publish occurs once, with idempotency protection.
9. Every stage writes to `event_log`.
10. A repeated publish request does not create duplicates.
