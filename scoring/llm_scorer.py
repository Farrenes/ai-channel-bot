import re
import asyncio
import json
from loguru import logger
from openai import AsyncOpenAI
from config import ROUTERAI_API_KEY, ROUTERAI_BASE_URL, ROUTERAI_MODEL
from scoring.constants import SCORING_SCHEMA, CHUNK_SIZE
from scoring.prefilter import cpu_prefilter, clean_html, fast_theme_check, chunk_content


def extract_json(text: str):
    text = text.strip()
    if not text:
        raise ValueError("Пустой текст")
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if match:
        json_str = match.group(1)
    else:
        start = re.search(r'[\[\{]', text)
        end = re.search(r'[\]\}]', text[::-1])
        if start and end:
            json_str = text[start.start():len(text) - end.start()]
        else:
            json_str = text
    json_str = json_str.strip()
    if not json_str:
        raise ValueError("Пустой JSON после очистки")
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    objects = []
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(json_str):
        try:
            obj, end_idx = decoder.raw_decode(json_str, idx)
            objects.append(obj)
            idx = end_idx
        except json.JSONDecodeError:
            idx += 1
    if objects:
        return objects
    raise ValueError("Не удалось распарсить JSON")

client = AsyncOpenAI(
    api_key=ROUTERAI_API_KEY,
    base_url=ROUTERAI_BASE_URL,
    timeout=90.0,
    max_retries=1
)

_scoring_cache: dict = {}
_db_write_callback = None


def set_db_write_callback(callback):
    global _db_write_callback
    _db_write_callback = callback


def _cache_key(title: str) -> str:
    return title.strip().lower()[:80]


async def _score_chunk(raw_content: str) -> bool:
    if not raw_content.strip() or len(raw_content) < 50:
        return False

    titles_in_chunk = [
        line.strip() for line in raw_content.split("\n\n")
        if line.strip() and len(line.strip()) > 5
    ]
    uncached = [t for t in titles_in_chunk if _cache_key(t) not in _scoring_cache]
    if not uncached:
        logger.info(f"📊 Все {len(titles_in_chunk)} идей уже в кэше, пропуск")
        return True

    eval_prompt = f"""Проанализируй материалы и оцени каждый по формуле:
total_score = b2c*3 + sav*2 + util*2 + repost*1 + prac*2

Категории: Инструменты/Промпты/Кейсы/Подборки/Новости
Оценки: от 0 до 10

{raw_content}"""

    for attempt in range(1, 4):
        try:
            response = await client.chat.completions.create(
                model=ROUTERAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Ты контент-аналитик Telegram-канала. Оцени материалы по формуле. "
                        "Верни JSON со списком items."
                    )},
                    {"role": "user", "content": eval_prompt}
                ],
                max_tokens=8000,
                temperature=0.0
            )

            raw_response = response.choices[0].message.content
            if not raw_response or not raw_response.strip():
                logger.warning(f"⚠️ Пустой ответ (попытка {attempt}/3), пауза 20 сек...")
                await asyncio.sleep(20)
                continue

            try:
                json_data = json.loads(raw_response)
                if isinstance(json_data, dict) and "items" in json_data:
                    json_data = json_data["items"]
            except json.JSONDecodeError:
                json_data = extract_json(raw_response)

            if not isinstance(json_data, list):
                json_data = [json_data]

            valid_ideas = []
            for item in json_data:
                if isinstance(item, dict) and item.get('title'):
                    valid_ideas.append(item)
                elif isinstance(item, str) and len(item) > 5:
                    valid_ideas.append({"title": item, "source": "unknown", "total_score": 0})

            if len(valid_ideas) > CHUNK_SIZE * 2:
                logger.warning(f"⚠️ Галлюцинация: {len(valid_ideas)} идей (макс {CHUNK_SIZE*2})")
                continue

            if not valid_ideas:
                logger.warning(f"⚠️ Нет валидных идей в ответе")
                continue

            logger.info(f"📊 {len(valid_ideas)} идей")
            for idea in valid_ideas:
                if not idea.get('title'):
                    continue
                key = _cache_key(idea['title'])
                if key in _scoring_cache:
                    continue
                if 'total_score' not in idea or not isinstance(idea['total_score'], (int, float)):
                    b2c = idea.get('score_b2c', 0)
                    sav = idea.get('score_savability', 0)
                    util = idea.get('score_utility', 0)
                    rep = idea.get('score_repostability', 0)
                    prac = idea.get('score_practical', 0)
                    idea['total_score'] = b2c*3 + sav*2 + util*2 + rep*1 + prac*2
                else:
                    idea['total_score'] = int(idea['total_score'])
                idea['status'] = 'pending' if idea['total_score'] >= 30 else 'rejected'
                if _db_write_callback:
                    await _db_write_callback(idea)
                _scoring_cache[key] = idea['total_score']
                logger.info(f"📌 {idea['title'][:60]} → {idea['total_score']}")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка (попытка {attempt}): {e}")
            if attempt < 3:
                await asyncio.sleep(20)
    return False


async def _score_chunk_with_timeout(chunk: str, idx: int, total: int) -> bool:
    try:
        return await asyncio.wait_for(
            _score_chunk(chunk),
            timeout=120.0
        )
    except asyncio.TimeoutError:
        logger.error(f"❌ Чанк {idx}/{total}: таймаут 120 сек")
        return False
    except Exception as e:
        logger.error(f"❌ Чанк {idx}/{total}: {e}")
        return False


async def run_screening_to_pool(raw_content: str, items: list = None) -> bool:
    if items:
        items = cpu_prefilter(items)
        if not items:
            logger.info("🧹 Все элементы отфильтрованы до LLM (CPU)")
            return False

        for item in items:
            item['description'] = clean_html(item.get('description', ''))
            item['title'] = clean_html(item.get('title', ''))

        items = await fast_theme_check(items)
        if not items:
            logger.info("🧹 Все элементы отфильтрованы ситом (тематика)")
            return False

        raw_content = "\n\n".join([
            f"{item.get('title', '')}\n{item.get('description', '')}"
            for item in items
        ])
        logger.info(f"🧹 После CPU + сито: {len(items)} идей")

    if not raw_content.strip():
        logger.warning("Пустой контент для скоринга")
        return False

    chunks = chunk_content(raw_content)
    total_chunks = len(chunks)
    logger.info(f"📡 Скоринг: {total_chunks} чанков...")

    tasks = [_score_chunk_with_timeout(chunk, i+1, total_chunks)
             for i, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    total_ideas = sum(1 for r in results if r is True)
    errors = sum(1 for r in results if isinstance(r, Exception) or r is False)

    if total_ideas > 0:
        logger.success(f"✅ Скоринг: {total_ideas}/{total_chunks} OK, ошибок: {errors}")
    else:
        logger.error("❌ Все чанки провалились")

    return total_ideas > 0
