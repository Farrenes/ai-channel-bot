import asyncpg
import json
from loguru import logger
from typing import Optional, List
from datetime import datetime
import database


def _json_loads(value, default):
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    return json.loads(value)


async def init_topic_tables():
    async with database.db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS topic_configs (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                target_channel TEXT,
                sources JSONB DEFAULT '[]',
                keywords TEXT[] DEFAULT '{}',
                categories JSONB DEFAULT '{}',
                prompt_id INT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS topic_prompts (
                id SERIAL PRIMARY KEY,
                topic_name TEXT NOT NULL,
                final_prompt TEXT NOT NULL,
                step_architect TEXT,
                step_constraints TEXT,
                step_cot TEXT,
                step_editor TEXT,
                tokens_input INT DEFAULT 0,
                tokens_output INT DEFAULT 0,
                version INT DEFAULT 1,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_name ON topic_configs(name);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_topic ON topic_prompts(topic_name);")
    logger.info("Таблицы topic_configs и topic_prompts созданы.")


async def create_topic(name: str, target_channel: str = None,
                       sources: list = None, keywords: list = None,
                       categories: dict = None) -> int:
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO topic_configs (name, target_channel, sources, keywords, categories)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (name) DO UPDATE SET
                target_channel = EXCLUDED.target_channel,
                sources = EXCLUDED.sources,
                keywords = EXCLUDED.keywords,
                categories = EXCLUDED.categories,
                updated_at = NOW()
            RETURNING id
        """, name, target_channel,
            json.dumps(sources or []),
            keywords or [],
            json.dumps(categories or {}))
        return row['id']


async def get_topic(name: str) -> Optional[dict]:
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM topic_configs WHERE name = $1", name
        )
        if row:
            d = dict(row)
            d['sources'] = _json_loads(d.get('sources'), [])
            d['categories'] = _json_loads(d.get('categories'), {})
            return d
    return None


async def get_topic_by_channel(channel: str) -> Optional[dict]:
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM topic_configs WHERE target_channel = $1 AND is_active = TRUE", channel
        )
        if row:
            d = dict(row)
            d['sources'] = _json_loads(d.get('sources'), [])
            d['categories'] = _json_loads(d.get('categories'), {})
            return d
    return None


async def get_active_topics() -> List[dict]:
    async with database.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM topic_configs WHERE is_active = TRUE ORDER BY name"
        )
        result = []
        for row in rows:
            d = dict(row)
            d['sources'] = _json_loads(d.get('sources'), [])
            d['categories'] = _json_loads(d.get('categories'), {})
            result.append(d)
        return result


async def update_topic(name: str, **kwargs) -> bool:
    allowed = {'target_channel', 'sources', 'keywords', 'categories', 'is_active', 'prompt_id'}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    if 'sources' in updates:
        updates['sources'] = json.dumps(updates['sources'])
    if 'categories' in updates:
        updates['categories'] = json.dumps(updates['categories'])
    set_parts = []
    values = []
    idx = 2
    for k, v in updates.items():
        set_parts.append(f"{k} = ${idx}")
        values.append(v)
        idx += 1
    set_parts.append("updated_at = NOW()")
    values.insert(0, name)
    async with database.db_pool.acquire() as conn:
        result = await conn.execute(
            f"UPDATE topic_configs SET {', '.join(set_parts)} WHERE name = $1", *values
        )
        return result == "UPDATE 1"


async def delete_topic(name: str) -> bool:
    async with database.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM topic_configs WHERE name = $1", name)
        return result == "DELETE 1"


async def save_topic_prompt(topic_name: str, prompt_data: dict) -> int:
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO topic_prompts (
                topic_name, final_prompt,
                step_architect, step_constraints, step_cot, step_editor,
                tokens_input, tokens_output
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """, topic_name,
            prompt_data.get('final_prompt', ''),
            prompt_data.get('steps', {}).get('architect', ''),
            prompt_data.get('steps', {}).get('constraints', ''),
            prompt_data.get('steps', {}).get('cot', ''),
            prompt_data.get('steps', {}).get('editor', ''),
            prompt_data.get('tokens', {}).get('input', 0),
            prompt_data.get('tokens', {}).get('output', 0))
        return row['id']


async def get_topic_prompt(topic_name: str) -> Optional[dict]:
    async with database.db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM topic_prompts
            WHERE topic_name = $1
            ORDER BY version DESC, created_at DESC LIMIT 1
        """, topic_name)
        return dict(row) if row else None
