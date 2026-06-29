try:
    import asyncpg
except ImportError:  # pragma: no cover - lightweight smoke-test fallback
    asyncpg = None

try:
    from loguru import logger
except ImportError:  # pragma: no cover - lightweight smoke-test fallback
    import logging

    logger = logging.getLogger("bottg")
from config import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
from datetime import datetime, timedelta

db_pool = None


async def init_db():
    global db_pool
    if asyncpg is None:
        raise RuntimeError("asyncpg is not installed")
    try:
        db_pool = await asyncpg.create_pool(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        logger.info("✅ Пул соединений PostgreSQL успешно создан.")

        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ideas_pool (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    source TEXT,
                    link TEXT,
                    category TEXT,
                    score_b2c INT,
                    score_utility INT,
                    score_savability INT,
                    score_repostability INT,
                    score_practical INT,
                    total_score INT,
                    raw_description TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await conn.execute("""
                DELETE FROM ideas_pool 
                WHERE id NOT IN (
                    SELECT MIN(id) 
                    FROM ideas_pool 
                    GROUP BY title
                );
            """)
            await conn.execute("""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ideas_pool_title_key') THEN
                        ALTER TABLE ideas_pool ADD CONSTRAINT ideas_pool_title_key UNIQUE (title);
                    END IF;
                END $$;
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS published_posts (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    post_text TEXT NOT NULL,
                    source_info TEXT,
                    category TEXT,
                    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Добавляем колонку category если её нет
            await conn.execute("""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name='published_posts' AND column_name='category'
                    ) THEN
                        ALTER TABLE published_posts ADD COLUMN category TEXT;
                    END IF;
                END $$;
            """)

            await conn.execute("CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas_pool(status);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_ideas_score ON ideas_pool(total_score);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_published_at ON published_posts(published_at DESC);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_published_category ON published_posts(category);")

        logger.info("✅ Структура базы данных и индексы созданы.")

        await init_style_tables()
        await _init_topic_tables()
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации БД: {e}")
        raise


async def is_title_duplicate(title: str) -> bool:
    if not title:
        return False
    if asyncpg is None:
        return False
    clean_title = title.strip().lower()
    async with db_pool.acquire() as conn:
        res1 = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM ideas_pool WHERE LOWER(title) = $1)", clean_title
        )
        res2 = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM published_posts WHERE LOWER(title) = $1)", clean_title
        )
        return res1 or res2


async def get_recent_published_titles(limit: int = 7) -> list:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT title FROM published_posts ORDER BY published_at DESC LIMIT $1", limit
        )
        return [row['title'] for row in rows]


async def add_idea_to_pool(idea: dict):
    if not idea.get('title'):
        return
    if asyncpg is None:
        return
    async with db_pool.acquire() as conn:
        try:
            await conn.execute("""
                INSERT INTO ideas_pool (
                    title, source, link, category, score_b2c, score_utility,
                    score_savability, score_repostability, score_practical,
                    total_score, raw_description, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (title) DO NOTHING
            """,
                               idea['title'], idea.get('source'), idea.get('link'), idea.get('category'),
                               idea.get('score_b2c'), idea.get('score_utility'), idea.get('score_savability'),
                               idea.get('score_repostability'), idea.get('score_practical'),
                               idea.get('total_score'), idea.get('raw_description'),
                               idea.get('status', 'pending')
                               )
        except asyncpg.exceptions.UniqueViolationError:
            logger.debug(f"Идея '{idea.get('title')}' уже существует (пропуск)")


async def get_pending_ideas(limit: int = 10):
    async with db_pool.acquire() as conn:
        return await conn.fetch("""
            SELECT id, title, raw_description, total_score, category
            FROM ideas_pool 
            WHERE status = 'pending' AND total_score >= 30
            ORDER BY total_score DESC LIMIT $1
        """, limit)


async def get_category_stats(days: int = 1):
    since = datetime.now() - timedelta(days=days)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT category, COUNT(*) as count
            FROM published_posts
            WHERE published_at >= $1
            GROUP BY category
        """, since)
        stats = {row['category']: row['count'] for row in rows}
        return stats


async def update_idea_status(idea_id: int, status: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE ideas_pool SET status = $2 WHERE id = $1", idea_id, status
        )


async def save_post(title: str, post_text: str, source_info: str, category: str) -> int:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO published_posts (title, post_text, source_info, category) VALUES ($1, $2, $3, $4) RETURNING id",
            title, post_text, source_info, category
        )
        return row['id']


async def init_style_tables():
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS channel_style_examples (
                id SERIAL PRIMARY KEY,
                post_text TEXT NOT NULL,
                post_url TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS channel_style_profile (
                id SERIAL PRIMARY KEY,
                avg_paragraph_length INT DEFAULT 50,
                avg_post_length INT DEFAULT 500,
                tone TEXT DEFAULT 'экспертный',
                opening_style TEXT DEFAULT 'с факта',
                favorite_words TEXT[] DEFAULT '{}',
                structure_pattern TEXT DEFAULT 'ДО/ПОСЛЕ',
                emoji_frequency TEXT DEFAULT 'умеренно',
                raw_profile TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS post_feedback (
                id SERIAL PRIMARY KEY,
                post_id INT REFERENCES published_posts(id),
                reaction TEXT CHECK (reaction IN ('like', 'dislike', 'neutral')),
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_style_examples_cat ON channel_style_examples(category);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_post ON post_feedback(post_id);")
    logger.info("✅ Таблицы стиля и фидбэка созданы.")


async def add_style_example(post_text: str, post_url: str = None, category: str = None):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO channel_style_examples (post_text, post_url, category) VALUES ($1, $2, $3)",
            post_text, post_url, category
        )
    logger.info(f"📌 Пример стиля сохранён ({len(post_text)} симв.)")


async def get_style_examples(limit: int = 20) -> list:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT post_text FROM channel_style_examples ORDER BY created_at DESC LIMIT $1",
            limit
        )
        return [row['post_text'] for row in rows]


async def get_style_profile() -> dict:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM channel_style_profile ORDER BY id DESC LIMIT 1"
        )
        if row:
            return dict(row)
        return None


async def save_style_profile(profile: dict):
    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM channel_style_profile LIMIT 1")
        if existing:
            await conn.execute("""
                UPDATE channel_style_profile SET
                    avg_paragraph_length=$1, avg_post_length=$2, tone=$3,
                    opening_style=$4, favorite_words=$5, structure_pattern=$6,
                    emoji_frequency=$7, raw_profile=$8, updated_at=NOW()
                WHERE id=$9
            """, profile.get('avg_paragraph_length', 50),
                profile.get('avg_post_length', 500),
                profile.get('tone', 'экспертный'),
                profile.get('opening_style', 'с факта'),
                profile.get('favorite_words', []),
                profile.get('structure_pattern', 'ДО/ПОСЛЕ'),
                profile.get('emoji_frequency', 'умеренно'),
                profile.get('raw_profile', ''),
                existing['id']
            )
        else:
            await conn.execute("""
                INSERT INTO channel_style_profile (
                    avg_paragraph_length, avg_post_length, tone, opening_style,
                    favorite_words, structure_pattern, emoji_frequency, raw_profile
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, profile.get('avg_paragraph_length', 50),
                profile.get('avg_post_length', 500),
                profile.get('tone', 'экспертный'),
                profile.get('opening_style', 'с факта'),
                profile.get('favorite_words', []),
                profile.get('structure_pattern', 'ДО/ПОСЛЕ'),
                profile.get('emoji_frequency', 'умеренно'),
                profile.get('raw_profile', '')
            )
    logger.info("✅ Профиль стиля сохранён")


async def add_post_feedback(post_id: int, reaction: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO post_feedback (post_id, reaction) VALUES ($1, $2)",
            post_id, reaction
        )


async def get_feedback_stats(days: int = 7) -> dict:
    since = datetime.now() - timedelta(days=days)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT reaction, COUNT(*) as count
            FROM post_feedback
            WHERE created_at >= $1
            GROUP BY reaction
        """, since)
        return {row['reaction']: row['count'] for row in rows}


async def get_liked_posts(days: int = 7) -> list:
    since = datetime.now() - timedelta(days=days)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT pp.post_text FROM published_posts pp
            JOIN post_feedback pf ON pp.id = pf.post_id
            WHERE pf.reaction = 'like' AND pf.created_at >= $1
            ORDER BY pf.created_at DESC LIMIT 10
        """, since)
        return [row['post_text'] for row in rows]


async def get_disliked_posts(days: int = 7) -> list:
    since = datetime.now() - timedelta(days=days)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT pp.post_text FROM published_posts pp
            JOIN post_feedback pf ON pp.id = pf.post_id
            WHERE pf.reaction = 'dislike' AND pf.created_at >= $1
            ORDER BY pf.created_at DESC LIMIT 10
        """, since)
        return [row['post_text'] for row in rows]


async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("✅ Пул соединений закрыт.")


async def get_last_post_time() -> datetime:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT published_at FROM published_posts ORDER BY published_at DESC LIMIT 1"
        )
        if row:
            return row['published_at']
    return datetime.now() - timedelta(days=1)


async def _init_topic_tables():
    async with db_pool.acquire() as conn:
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
    logger.info("✅ Таблицы topic_configs и topic_prompts созданы.")
