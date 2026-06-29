# BotTG n8n Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** СЃРѕР·РґР°С‚СЊ РјРѕРґСѓР»СЊРЅСѓСЋ Р°СЂС…РёС‚РµРєС‚СѓСЂСѓ BotTG, РіРґРµ n8n СЏРІР»СЏРµС‚СЃСЏ РіР»Р°РІРЅС‹Рј РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂРѕРј, Р° Python-РєРѕРјРїРѕРЅРµРЅС‚С‹ РїРѕРґРєР»СЋС‡Р°СЋС‚СЃСЏ РєР°Рє РѕС‚РґРµР»СЊРЅС‹Рµ СЃРµСЂРІРёСЃС‹ РёР»Рё РёСЃРїРѕР»РЅСЏРµРјС‹Рµ РјРѕРґСѓР»Рё.

**Architecture:** n8n СѓРїСЂР°РІР»СЏРµС‚ РІСЃРµРјРё СЃС†РµРЅР°СЂРёСЏРјРё: РѕРЅР±РѕСЂРґРёРЅРіРѕРј, РїСЂРѕРІРµСЂРєРѕР№ РёСЃС‚РѕС‡РЅРёРєРѕРІ, СЃР±РѕСЂРѕРј РєРѕРЅС‚РµРЅС‚Р°, СЃРєРѕСЂРёРЅРіРѕРј, РіРµРЅРµСЂР°С†РёРµР№, РіРёР±СЂРёРґРЅС‹РјРё РїСЂРѕРІРµСЂРєР°РјРё, РїСѓР±Р»РёРєР°С†РёРµР№, Р°РЅР°Р»РёС‚РёРєРѕР№ Рё РїРѕСЃС‚РѕСЏРЅРЅС‹Рј РґРѕРѕР±СѓС‡РµРЅРёРµРј СЃС‚РёР»СЏ. Python-СЃР»РѕР№ РѕСЃС‚Р°РµС‚СЃСЏ РЅР°Р±РѕСЂРѕРј СЃРїРµС†РёР°Р»РёР·РёСЂРѕРІР°РЅРЅС‹С… РјРѕРґСѓР»РµР№ Р·Р° HTTP/CLI-РёРЅС‚РµСЂС„РµР№СЃР°РјРё, PostgreSQL С…СЂР°РЅРёС‚ СЃРѕСЃС‚РѕСЏРЅРёРµ, Р»РёРјРёС‚С‹, РёСЃС‚РѕС‡РЅРёРєРё, СЃС‚РёР»СЊ, РєР°РЅРґРёРґР°С‚С‹ Рё РёСЃС‚РѕСЂРёСЋ РїСѓР±Р»РёРєР°С†РёР№.

**Tech Stack:** n8n, Python, FastAPI, PostgreSQL, Telegram Bot API, RouterAI/DeepSeek-compatible API, Mermaid, Obsidian Markdown.

## Global Constraints

- n8n СЏРІР»СЏРµС‚СЃСЏ РіР»Р°РІРЅС‹Рј РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂРѕРј Р»РѕРіРёРєРё Рё Р°СЂС…РёС‚РµРєС‚СѓСЂС‹ РїСЂРѕРµРєС‚Р°.
- РџСЂРѕРµРєС‚ СЏРІР»СЏРµС‚СЃСЏ СѓРЅРёРІРµСЂСЃР°Р»СЊРЅС‹Рј content factory Рё Р°РІС‚РѕРїРѕСЃС‚РёРЅРіРѕРј РґР»СЏ Telegram, Р° РЅРµ РЅРёС€РµРІС‹Рј AI-Р±РѕС‚РѕРј.
- РўРµРјР° РєР°РЅР°Р»Р° РІРІРѕРґРёС‚СЃСЏ СЃРІРѕР±РѕРґРЅС‹Рј С‚РµРєСЃС‚РѕРј Рё РЅРѕСЂРјР°Р»РёР·СѓРµС‚СЃСЏ СЃРёСЃС‚РµРјРѕР№.
- РСЃС‚РѕС‡РЅРёРєРё Рё СЃС‚РёР»СЊ РЅР°СЃС‚СЂР°РёРІР°СЋС‚СЃСЏ РїРѕСЃР»Рµ С‚РµРјС‹.
- РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РјРѕР¶РµС‚ РґРѕР±Р°РІРёС‚СЊ РёСЃС‚РѕС‡РЅРёРє С‚РѕР»СЊРєРѕ РїРѕ URL; СЃРёСЃС‚РµРјР° СЃР°РјР° РѕРїСЂРµРґРµР»СЏРµС‚ РјРµС‚Р°РґР°РЅРЅС‹Рµ РёСЃС‚РѕС‡РЅРёРєР°.
- РСЃС‚РѕС‡РЅРёРєРё РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ С„Р°РєС‚РёС‡РµСЃРєРё РЅРµРѕРіСЂР°РЅРёС‡РµРЅС‹ РІ РёРЅС‚РµСЂС„РµР№СЃРµ, РЅРѕ РѕРіСЂР°РЅРёС‡РµРЅС‹ fair-use РёСЃРїРѕР»РЅРµРЅРёРµРј.
- РџСѓР±Р»РёРєР°С†РёСЏ РїРѕСЃР»Рµ РЅР°СЃС‚СЂРѕР№РєРё Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєР°СЏ Рё РЅРµ С‚СЂРµР±СѓРµС‚ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ С‡РµР»РѕРІРµРєР°.
- РЎС‚РёР»СЊ РєР°РЅР°Р»Р° РґРѕРѕР±СѓС‡Р°РµС‚СЃСЏ РїРѕСЃС‚РѕСЏРЅРЅРѕ.
- РџСЂРѕРІРµСЂРєРё Р·Р°РєРѕРЅР°, РїРѕСЂРЅРѕ Рё РєР°С‡РµСЃС‚РІР° РІС‹РїРѕР»РЅСЏСЋС‚СЃСЏ РіРёР±СЂРёРґРЅРѕ: РґРµС€РµРІС‹Рµ РїСЂР°РІРёР»Р° РїРµСЂРІС‹РјРё, LLM С‚РѕР»СЊРєРѕ РїСЂРё РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё.
- РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ С‚РѕРєРµРЅРѕРІ РІ РїСЂРѕРІРµСЂРєР°С… РЅСѓР¶РЅРѕ РјРёРЅРёРјРёР·РёСЂРѕРІР°С‚СЊ.
- РџСЂРё РїРѕРґРѕР·СЂРёС‚РµР»СЊРЅРѕРј РёСЃС‚РѕС‡РЅРёРєРµ СЃРёСЃС‚РµРјР° РїСЂРµРґСѓРїСЂРµР¶РґР°РµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Рё РїСЂРѕСЃРёС‚ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ.
- РџСЂРёРѕСЂРёС‚РµС‚С‹ РїСЂРѕРґСѓРєС‚Р°: РєР°С‡РµСЃС‚РІРѕ РєРѕРЅС‚РµРЅС‚Р°, СЌРєРѕРЅРѕРјРёСЏ РІСЂРµРјРµРЅРё, СЂРѕСЃС‚ РѕС…РІР°С‚РѕРІ Рё РїРѕРґРїРёСЃС‡РёРєРѕРІ С‡РµСЂРµР· РєР°С‡РµСЃС‚РІРѕ.

---

## File Structure

- Create: `docs/obsidian/BotTG - n8n Architecture and Workflows 2026-06-26.md`
  - РС‚РѕРіРѕРІС‹Р№ РґРѕРєСѓРјРµРЅС‚ РґР»СЏ Obsidian: РјРѕРґСѓР»Рё, workflows, РґР°РЅРЅС‹Рµ, Mermaid-СЃС…РµРјС‹, failure paths, РїСЂРѕРІРµСЂРѕС‡РЅС‹Р№ С‡РµРєР»РёСЃС‚.
- Modify: `docs/superpowers/plans/2026-06-26-bottg-n8n-architecture-plan.md`
  - Р­С‚РѕС‚ РїР»Р°РЅ: РїРѕСЃР»Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РѕС‚РјРµС‚РёС‚СЊ Р·Р°РґР°С‡Рё РєР°Рє РІС‹РїРѕР»РЅРµРЅРЅС‹Рµ.

## Agent Split

- Agent 1: РјРѕРґСѓР»СЊРЅС‹Рµ РіСЂР°РЅРёС†С‹ Python/n8n Рё РёРЅС‚РµСЂС„РµР№СЃС‹ РІС‹Р·РѕРІР°.
- Agent 2: n8n workflows, nodes, IF/Switch/Loop/Error Trigger.
- Agent 3: РґР°РЅРЅС‹Рµ, СЃС‚Р°С‚СѓСЃС‹, payload-РєРѕРЅС‚СЂР°РєС‚С‹, С‚Р°СЂРёС„РЅС‹Рµ СЃС‡РµС‚С‡РёРєРё.
- Agent 4: Mermaid-СЃС…РµРјС‹, РІРёР·СѓР°Р»СЊРЅР°СЏ СЃС‚СЂСѓРєС‚СѓСЂР°, failure paths, С‡РµРєР»РёСЃС‚ РїСЂРѕРІРµСЂРєРё.

### Task 1: Module Map

**Files:**
- Create: `docs/obsidian/BotTG - n8n Architecture and Workflows 2026-06-26.md`

**Interfaces:**
- Consumes: С‚РµРєСѓС‰РёР№ РїСЂРѕРґСѓРєС‚РѕРІС‹Р№ checkpoint, `README.md`, `main.py`, `parsers.py`, `scoring_service.py`, `llm_generator.py`, `database.py`.
- Produces: СЃРїРёСЃРѕРє РјРѕРґСѓР»РµР№ MVP/later СЃ РІС…РѕРґР°РјРё, РІС‹С…РѕРґР°РјРё Рё СЃРїРѕСЃРѕР±РѕРј РІС‹Р·РѕРІР° РёР· n8n.

- [x] **Step 1: РѕРїРёСЃР°С‚СЊ РїСЂРёРЅС†РёРї Р°СЂС…РёС‚РµРєС‚СѓСЂС‹**

Р”РѕР±Р°РІРёС‚СЊ СЂР°Р·РґРµР»С‹:
- `Р¦РµР»СЊ Р°СЂС…РёС‚РµРєС‚СѓСЂС‹`
- `Р“Р»Р°РІРЅС‹Р№ РїСЂРёРЅС†РёРї`
- `РњРѕРґСѓР»Рё MVP`
- `РњРѕРґСѓР»Рё later`

- [x] **Step 2: СѓРєР°Р·Р°С‚СЊ n8n-callable РёРЅС‚РµСЂС„РµР№СЃС‹**

Р”Р»СЏ РєР°Р¶РґРѕРіРѕ MVP-РјРѕРґСѓР»СЏ СѓРєР°Р·Р°С‚СЊ:
- РѕС‚РІРµС‚СЃС‚РІРµРЅРЅРѕСЃС‚СЊ
- РІС…РѕРґ
- РІС‹С…РѕРґ
- РІС‹Р·РѕРІ РёР· n8n: HTTP, Webhook, Execute Command РёР»Рё PostgreSQL node
- РїРµСЂРµРёСЃРїРѕР»СЊР·СѓРµРјС‹Рµ Python-С„СѓРЅРєС†РёРё
- РЅРѕРІС‹Рµ РѕР±РµСЂС‚РєРё, РєРѕС‚РѕСЂС‹Рµ РїРѕРЅР°РґРѕР±СЏС‚СЃСЏ РїРѕР·Р¶Рµ

- [x] **Step 3: РїСЂРѕРІРµСЂРёС‚СЊ РїРѕРєСЂС‹С‚РёРµ**

Run: `Select-String -LiteralPath "docs/obsidian/BotTG - n8n Architecture and Workflows 2026-06-26.md" -Pattern "MVP","Webhook","FastAPI","PostgreSQL"`

Expected: РЅР°Р№РґРµРЅС‹ СЃС‚СЂРѕРєРё РїРѕ РєР°Р¶РґРѕРјСѓ РєР»СЋС‡РµРІРѕРјСѓ СЃР»РѕРІСѓ.

### Task 2: n8n Workflow Logic

**Files:**
- Modify: `docs/obsidian/BotTG - n8n Architecture and Workflows 2026-06-26.md`

**Interfaces:**
- Consumes: module map from Task 1.
- Produces: СЃРїРёСЃРѕРє n8n workflows СЃ С‚СЂРёРіРіРµСЂР°РјРё, nodes, РІРµС‚РІР»РµРЅРёСЏРјРё, Р»РёРјРёС‚Р°РјРё Рё РїРµСЂРµРґР°С‡РµР№ РґР°РЅРЅС‹С….

- [x] **Step 1: РѕРїРёСЃР°С‚СЊ workflows MVP**

Р”РѕР±Р°РІРёС‚СЊ workflows:
- `01 Onboarding`
- `02 Source Validation`
- `03 Scheduled Content Intake`
- `04 Candidate Scoring`
- `05 Post Generation and Review`
- `06 Autopublish`
- `07 Analytics and Continuous Style Learning`
- `08 Error Handling and Retry`

- [x] **Step 2: РѕРїРёСЃР°С‚СЊ node-by-node Р»РѕРіРёРєСѓ**

Р”Р»СЏ РєР°Р¶РґРѕРіРѕ workflow СѓРєР°Р·Р°С‚СЊ:
- trigger
- РѕСЃРЅРѕРІРЅС‹Рµ nodes
- IF/Switch/Loop/Error Trigger
- РІС…РѕРґРЅС‹Рµ Рё РІС‹С…РѕРґРЅС‹Рµ РґР°РЅРЅС‹Рµ
- С‡С‚Рѕ РїРёС€РµС‚СЃСЏ РІ PostgreSQL

- [x] **Step 3: РїСЂРѕРІРµСЂРёС‚СЊ РїРѕРєСЂС‹С‚РёРµ**

Run: `Select-String -LiteralPath "docs/obsidian/BotTG - n8n Architecture and Workflows 2026-06-26.md" -Pattern "01 Onboarding","06 Autopublish","Error Trigger","fair-use"`

Expected: РЅР°Р№РґРµРЅС‹ СЃС‚СЂРѕРєРё РїРѕ РєР°Р¶РґРѕРјСѓ РєР»СЋС‡РµРІРѕРјСѓ СЃР»РѕРІСѓ.

### Task 3: Data Contracts

**Files:**
- Modify: `docs/obsidian/BotTG - n8n Architecture and Workflows 2026-06-26.md`

**Interfaces:**
- Consumes: workflows from Task 2.
- Produces: С‚Р°Р±Р»РёС†С‹, СЃС‚Р°С‚СѓСЃС‹, payload JSON Рё СЃС‡РµС‚С‡РёРєРё С‚Р°СЂРёС„РѕРІ.

- [x] **Step 1: РѕРїРёСЃР°С‚СЊ РѕСЃРЅРѕРІРЅС‹Рµ СЃСѓС‰РЅРѕСЃС‚Рё**

Р”РѕР±Р°РІРёС‚СЊ СЃСѓС‰РЅРѕСЃС‚Рё:
- `channels`
- `channel_sources`
- `content_candidates`
- `generated_posts`
- `style_profiles`
- `subscription_limits`
- `usage_counters`
- `workflow_events`

- [x] **Step 2: РѕРїРёСЃР°С‚СЊ СЃС‚Р°С‚СѓСЃС‹**

Р”РѕР±Р°РІРёС‚СЊ СЃС‚Р°С‚СѓСЃС‹:
- source validation
- content candidate lifecycle
- generated post lifecycle
- retry/failure reasons

- [x] **Step 3: РѕРїРёСЃР°С‚СЊ payload-РєРѕРЅС‚СЂР°РєС‚С‹**

Р”РѕР±Р°РІРёС‚СЊ JSON-РєРѕРЅС‚СЂР°РєС‚С‹:
- source validation request/response
- scoring request/response
- generation request/response
- publish request/response
- analytics event

- [x] **Step 4: РїСЂРѕРІРµСЂРёС‚СЊ РїРѕРєСЂС‹С‚РёРµ**

Run: `Select-String -LiteralPath "docs/obsidian/BotTG - n8n Architecture and Workflows 2026-06-26.md" -Pattern "channel_sources","content_candidates","usage_counters","source_validation"`

Expected: РЅР°Р№РґРµРЅС‹ СЃС‚СЂРѕРєРё РїРѕ РєР°Р¶РґРѕРјСѓ РєР»СЋС‡РµРІРѕРјСѓ СЃР»РѕРІСѓ.

### Task 4: Visual Scheme

**Files:**
- Modify: `docs/obsidian/BotTG - n8n Architecture and Workflows 2026-06-26.md`

**Interfaces:**
- Consumes: module map, workflows, data contracts.
- Produces: Mermaid flowchart and sequence diagrams.

- [x] **Step 1: РґРѕР±Р°РІРёС‚СЊ РѕР±С‰СѓСЋ СЃС…РµРјСѓ Р°СЂС…РёС‚РµРєС‚СѓСЂС‹**

Mermaid flowchart РґРѕР»Р¶РµРЅ РїРѕРєР°Р·С‹РІР°С‚СЊ:
- Telegram/user input
- n8n workflows
- Python services
- PostgreSQL
- Telegram channel
- analytics/style learning loop

- [x] **Step 2: РґРѕР±Р°РІРёС‚СЊ sequence РїСѓР±Р»РёРєР°С†РёРё**

Mermaid sequence РґРѕР»Р¶РµРЅ РїРѕРєР°Р·С‹РІР°С‚СЊ:
- Cron trigger
- Р»РёРјРёС‚ С‚Р°СЂРёС„Р°
- РїРѕР»СѓС‡РµРЅРёРµ РєР°РЅРґРёРґР°С‚РѕРІ
- СЃРєРѕСЂРёРЅРі
- РіРµРЅРµСЂР°С†РёСЋ
- РіРёР±СЂРёРґРЅС‹Рµ РїСЂРѕРІРµСЂРєРё
- РїСѓР±Р»РёРєР°С†РёСЋ
- Р·Р°РїРёСЃСЊ СЂРµР·СѓР»СЊС‚Р°С‚Р°
- РґРѕРѕР±СѓС‡РµРЅРёРµ СЃС‚РёР»СЏ

- [x] **Step 3: РґРѕР±Р°РІРёС‚СЊ failure paths**

РџРѕРєР°Р·Р°С‚СЊ, С‡С‚Рѕ РїСЂРѕРёСЃС…РѕРґРёС‚ РїСЂРё:
- РЅРµРґРѕСЃС‚СѓРїРЅРѕРј РёСЃС‚РѕС‡РЅРёРєРµ
- РїРѕРґРѕР·СЂРёС‚РµР»СЊРЅРѕРј РёСЃС‚РѕС‡РЅРёРєРµ
- РЅРёР·РєРѕРј РєР°С‡РµСЃС‚РІРµ РєР°РЅРґРёРґР°С‚Р°
- РїСЂРѕРІР°Р»Рµ РїСЂРѕРІРµСЂРєРё Р·Р°РєРѕРЅР°/РїРѕСЂРЅРѕ
- РѕС€РёР±РєРµ Telegram API
- РїСЂРµРІС‹С€РµРЅРёРё Р»РёРјРёС‚РѕРІ С‚Р°СЂРёС„Р°

- [x] **Step 4: РїСЂРѕРІРµСЂРёС‚СЊ Mermaid-Р±Р»РѕРєРё**

Run: `Select-String -LiteralPath "docs/obsidian/BotTG - n8n Architecture and Workflows 2026-06-26.md" -Pattern "```mermaid","flowchart TD","sequenceDiagram"`

Expected: РЅР°Р№РґРµРЅС‹ Mermaid-Р±Р»РѕРєРё.

### Task 5: Self-Review and Completion

**Files:**
- Modify: `docs/obsidian/BotTG - n8n Architecture and Workflows 2026-06-26.md`
- Modify: `docs/superpowers/plans/2026-06-26-bottg-n8n-architecture-plan.md`

**Interfaces:**
- Consumes: final architecture document.
- Produces: checked plan and short verification report.

- [x] **Step 1: РїСЂРѕРІРµСЂРёС‚СЊ РѕС‚СЃСѓС‚СЃС‚РІРёРµ СЏРІРЅС‹С… Р·Р°РіР»СѓС€РµРє**

Run: `Select-String -LiteralPath "docs/obsidian/BotTG - n8n Architecture and Workflows 2026-06-26.md" -Pattern "TBD","TODO","РїРѕС‚РѕРј СѓС‚РѕС‡РЅРёС‚СЊ","Р·Р°РіР»СѓС€РєР°"`

Expected: РЅРµС‚ РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РЅРµР·Р°РєСЂС‹С‚С‹С… Р·Р°РіР»СѓС€РµРє.

- [x] **Step 2: РїСЂРѕРІРµСЂРёС‚СЊ РєР»СЋС‡РµРІС‹Рµ С‚СЂРµР±РѕРІР°РЅРёСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ**

Run: `Select-String -LiteralPath "docs/obsidian/BotTG - n8n Architecture and Workflows 2026-06-26.md" -Pattern "n8n","СЃРІРѕР±РѕРґРЅС‹Рј С‚РµРєСЃС‚РѕРј","РїРѕСЃС‚РѕСЏРЅРЅРѕРµ РґРѕРѕР±СѓС‡РµРЅРёРµ","РіРёР±СЂРёРґРЅС‹Рµ РїСЂРѕРІРµСЂРєРё","Р°РІС‚РѕРїСѓР±Р»РёРєР°С†РёСЏ","Mermaid"`

Expected: РЅР°Р№РґРµРЅС‹ СЃС‚СЂРѕРєРё РїРѕ РєР°Р¶РґРѕРјСѓ РєР»СЋС‡РµРІРѕРјСѓ СЃР»РѕРІСѓ.

- [x] **Step 3: РѕС‚РјРµС‚РёС‚СЊ Р·Р°РґР°С‡Рё РїР»Р°РЅР° РІС‹РїРѕР»РЅРµРЅРЅС‹РјРё**

Р’ СЌС‚РѕРј С„Р°Р№Р»Рµ Р·Р°РјРµРЅРёС‚СЊ С‡РµРєР±РѕРєСЃС‹ Р·Р°РІРµСЂС€РµРЅРЅС‹С… С€Р°РіРѕРІ СЃ `[ ]` РЅР° `[x]`.

- [x] **Step 4: С„РёРЅР°Р»СЊРЅС‹Р№ РѕС‚С‡РµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ**

РЎРѕРѕР±С‰РёС‚СЊ:
- РіРґРµ Р»РµР¶РёС‚ РїР»Р°РЅ
- РіРґРµ Р»РµР¶РёС‚ Р°СЂС…РёС‚РµРєС‚СѓСЂРЅС‹Р№ РґРѕРєСѓРјРµРЅС‚
- РєР°РєРёРµ РѕРіСЂР°РЅРёС‡РµРЅРёСЏ Р±С‹Р»Рё Р·Р°РјРµС‡РµРЅС‹
- С‡С‚Рѕ РјРѕР¶РЅРѕ РґРµР»Р°С‚СЊ СЃР»РµРґСѓСЋС‰РёРј С€Р°РіРѕРј

