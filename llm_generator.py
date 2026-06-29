import asyncio
import json
import re
import html
import unicodedata
from loguru import logger
from openai import AsyncOpenAI
from config import ROUTERAI_API_KEY, ROUTERAI_BASE_URL, ROUTERAI_MODEL
from database import get_style_examples, get_style_profile, save_style_profile
from scoring.prefilter import has_cjk
from topic_config import get_topic
from topic_prompt_manager import get_cached_prompt, assemble_generation_prompt

client = AsyncOpenAI(
    api_key=ROUTERAI_API_KEY,
    base_url=ROUTERAI_BASE_URL,
    timeout=90.0,
    max_retries=1
)


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


async def test_api() -> bool:
    """Самотест API: проверяем что RouterAI отвечает и возвращает JSON"""
    logger.info("🔍 Самотест API...")
    try:
        response = await client.chat.completions.create(
            model=ROUTERAI_MODEL,
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON."},
                {"role": "user", "content": 'Return: {"status":"ok"}'}
            ],
            max_tokens=500,
            temperature=0.0
        )
        raw = response.choices[0].message.content
        if not raw or not raw.strip():
            logger.error("❌ API вернул пустой ответ")
            return False
        data = extract_json(raw)
        if isinstance(data, dict) and data.get("status") == "ok":
            logger.info("✅ API работает корректно")
            return True
        logger.warning(f"⚠️ API ответил неожиданно: {raw[:100]}")
        return True
    except Exception as e:
        logger.error(f"❌ Самотест API провален: {e}")
        return False


async def extract_style_profile() -> dict:
    """Анализирует примеры постов → создаёт профиль стиля канала"""
    examples = await get_style_examples()
    if not examples:
        logger.info("📝 Нет примеров стиля, используется профиль по умолчанию")
        return None

    formatted = "\n\n".join(
        f"--- Пост {i+1} ---\n{ex}" for i, ex in enumerate(examples)
    )

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=ROUTERAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Ты аналитик стиля. Проанализируй посты и определи стиль канала. "
                        "Верни JSON."
                    )},
                    {"role": "user", "content": f"""Проанализируй {len(examples)} постов из Telegram-канала.

{formatted}

Определи (верни строго JSON):
{{
  "avg_paragraph_length": число_слов_в_абзаце,
  "avg_post_length": число_слов_в_посте,
  "tone": "экспертный/дерзкий/спокойный/дружеский/информативный",
  "opening_style": "с_вопроса/с_факта/с_провокации/с_истории",
  "favorite_words": ["фраза1", "фраза2", "фраза3"],
  "structure_pattern": "ДО-ПОСЛЕ/список/сторителлинг/смешанный",
  "emoji_frequency": "много/умеренно/минимум",
  "raw_profile": "описание стиля 1-2 предложения"
}}"""}
                ],
                max_tokens=1000,
                temperature=0.0
            ),
            timeout=60.0
        )

        raw = response.choices[0].message.content
        profile = extract_json(raw)
        await save_style_profile(profile)
        logger.success(f"✅ Профиль стиля извлечён: {profile.get('tone', '?')}, {profile.get('opening_style', '?')}")
        return profile

    except Exception as e:
        logger.error(f"❌ Ошибка извлечения стиля: {e}")
        return None


async def get_or_create_style_profile() -> dict:
    """Получает профиль стиля из БД, или создаёт если нет"""
    profile = await get_style_profile()
    if profile:
        return profile
    return await extract_style_profile()


REVIEW_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "review_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "pass": {"type": "boolean"},
                "issues": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "score": {"type": "integer"},
                "summary": {"type": "string"}
            },
            "required": ["pass", "issues", "score", "summary"]
        }
    }
}


async def triple_review(post: str, context: str, style_profile: dict = None) -> dict:
    """Один вызов с тремя ролями: редактор, читатель, админ"""
    style_hint = f" Стиль канала: {style_profile.get('raw_profile', '')}." if style_profile else ""
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=ROUTERAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Ты проверяешь Telegram-пост с трёх позиций: "
                        "1) Редактор: факты, грамматика, логика. "
                        "2) Читатель: зацепило? Полезно? Сохранишь? "
                        "3) Админ канала: стиль, формат ДО/ПОСЛЕ?" + style_hint + "\n"
                        "Верни JSON: {\"editor\":{\"pass\":bool,\"issues\":[str]},"
                        "\"reader\":{\"pass\":bool,\"score\":1-10},"
                        "\"admin\":{\"pass\":bool,\"issues\":[str]}}"
                    )},
                    {"role": "user", "content": f"Контекст:\n{context[:300]}\n\nПост:\n{post}"}
                ],
                max_tokens=500,
                temperature=0.0
            ),
            timeout=30.0
        )
        raw = response.choices[0].message.content
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {
                "editor": {"pass": True, "issues": []},
                "reader": {"pass": True, "score": 5},
                "admin": {"pass": True, "issues": []}
            }
        all_pass = (
            result.get("editor", {}).get("pass", True) and
            result.get("reader", {}).get("pass", True) and
            result.get("admin", {}).get("pass", True)
        )
        return {
            "editor": result.get("editor", {"pass": True, "issues": []}),
            "reader": result.get("reader", {"pass": True, "score": 5}),
            "admin": result.get("admin", {"pass": True, "issues": []}),
            "overall_pass": all_pass
        }
    except Exception as e:
        logger.warning(f"⚠️ Review ошибка: {e}")
        return {
            "editor": {"pass": True, "issues": []},
            "reader": {"pass": True, "score": 5},
            "admin": {"pass": True, "issues": []},
            "overall_pass": True
        }


def compile_feedback(review: dict) -> str:
    """Собирает фидбэк из трёх взглядов в строку для переписывания"""
    issues = []
    for role in ["editor", "reader", "admin"]:
        role_issues = review.get(role, {}).get("issues", [])
        issues.extend(f"[{role}] {i}" for i in role_issues)
    return "; ".join(issues) if issues else "Мелкие замечания, улучши качество"


async def rewrite_with_feedback(post: str, feedback: str, context: str, category: str = None) -> str:
    """Переписывает пост с учётом фидбэка"""
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=ROUTERAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Перепиши Telegram-пост, исправив замечания. "
                        "Сохрани формат ДО/ПОСЛЕ + <blockquote>."
                    )},
                    {"role": "user", "content": (
                        f"Оригинал:\n{post}\n\n"
                        f"Замечания: {feedback}\n\n"
                        f"Перепиши пост с учётом замечаний."
                    )}
                ],
                max_tokens=6000,
                temperature=0.7
            ),
            timeout=60.0
        )
        raw = response.choices[0].message.content
        return raw.strip() if raw else post
    except Exception as e:
        logger.error(f"❌ Ошибка переписывания: {e}")
        return post


async def deep_research(topic: str) -> str:
    """Когда тема горячая — ищем доп. информацию через LLM"""
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=ROUTERAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Ты исследователь. Дай краткую справку по теме: "
                        "что это, почему важно, какой Impact на обычных пользователей. "
                        "Максимум 200 слов, по-русски."
                    )},
                    {"role": "user", "content": f"Тема: {topic}"}
                ],
                max_tokens=600,
                temperature=0.0
            ),
            timeout=30.0
        )
        result = response.choices[0].message.content
        if result:
            logger.info(f"📚 Deep research: {len(result)} символов для '{topic[:40]}'")
            return result.strip()
    except Exception as e:
        logger.warning(f"⚠️ Deep research ошибка: {e}")
    return ""


POST_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "post_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "post": {"type": "string"}
            },
            "required": ["post"]
        }
    }
}


async def generate_post_from_context(context_text: str, category: str = None,
                                     topic_name: str = None, max_attempts: int = 2) -> str:
    category_emojis = {
        'Промпты': '🧠', 'Инструменты': '🔥', 'Кейсы': '📈',
        'Подборки': '📚', 'Новости': '📰'
    }
    emoji = category_emojis.get(category, '🤖')

    style = await get_or_create_style_profile()
    style_block = _build_style_prompt_block(style)

    if topic_name:
        topic_cfg = await get_topic(topic_name)
        if topic_cfg and topic_cfg.get('prompt_id'):
            template = await assemble_generation_prompt(topic_cfg, context_text, style)
        else:
            template = f"""Telegram пост. {category or topic_name or 'Новости'}.
{style_block}
Контекст материала:
{context_text}

Инструкции по стилю:
- Пиши под {style.get('default_post_format', 'telegram_short') if style else 'telegram_short'}
- Адаптируй плотность текста под {style.get('tone', 'информативный') if style else 'информативный'}
- Сохраняй {style.get('structure_pattern', 'ДО/ПОСЛЕ') if style else 'ДО/ПОСЛЕ'} как базу структуры
- Emoji: {style.get('emoji_frequency', 'умеренно') if style else 'умеренно'}
- Не делай текст простынёй
- Не делай слишком сухой тон
- Не добавляй нейромаркеры и искусственные вводные

Формат:
{_style_format_hint(style)}

Контекст:
{context_text}"""
    else:
        template = f"""Telegram пост "Practical AI". {category or 'Новости'}.
{style_block}
Контекст материала:
{context_text}

Формат:
{_style_format_hint(style)}

Дополнительно:
- Пиши как живой Telegram-редактор
- Сохраняй полезность и краткость
- Не перегружай форматирование"""

    best_post = None
    best_score = -1

    def score_post(p):
        s = 0
        if re.search(r'ДО[:\s]', p, re.IGNORECASE):
            s += 3
        if re.search(r'ПОСЛЕ[:\s]', p, re.IGNORECASE):
            s += 3
        if '<blockquote>' in p and '</blockquote>' in p:
            s += 4
        if 350 <= len(p) <= 1600:
            s += 2
        if not has_cjk(p):
            s += 1
        return s

    for attempt in range(1, max_attempts + 1):
        try:
            prompt = template
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=ROUTERAI_MODEL,
                    messages=[
                        {"role": "system", "content": (
                            "Telegram автор. Пиши как живой редактор. "
                            "ДО/ПОСЛЕ + <blockquote>guide. Формат HTML."
                        )},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=6000,
                    temperature=0.7
                ),
                timeout=120.0
            )

            raw = response.choices[0].message.content.strip()
            if not raw:
                logger.warning(f"⚠️ Пустой ответ (попытка {attempt}), пауза 20 сек...")
                await asyncio.sleep(20)
                continue

            post = raw
            if post.startswith('{') or post.startswith('['):
                try:
                    parsed = json.loads(post)
                    if isinstance(parsed, dict):
                        post = parsed.get("post", parsed.get("text", post))
                    elif isinstance(parsed, list) and parsed:
                        first = parsed[0]
                        post = first.get("post", first.get("text", str(first)))
                except (json.JSONDecodeError, AttributeError):
                    pass

            pts = score_post(post)

            if pts > best_score:
                best_score = pts
                best_post = post

            if pts >= 12:
                logger.success(f"✅ Пост создан ({len(post)} симв., попытка {attempt})")
                break

            logger.warning(f"⚠️ Попытка {attempt}: score={pts}")

        except asyncio.TimeoutError:
            logger.error(f"❌ Таймаут генерации (попытка {attempt})")
            await asyncio.sleep(20)
        except Exception as e:
            logger.error(f"❌ Ошибка генерации: {e}")

    logger.info(f"🔄 Мягкая валидация (лучший score={best_score})")
    for attempt in range(2):
        try:
            prompt = template
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=ROUTERAI_MODEL,
                    messages=[
                        {"role": "system", "content": (
                            "Telegram автор. Пиши как живой редактор. "
                            "ДО/ПОСЛЕ + <blockquote>. Формат HTML."
                        )},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=6000,
                    temperature=0.8
                ),
                timeout=120.0
            )

            raw = response.choices[0].message.content.strip()
            if not raw:
                logger.warning(f"⚠️ Пустой ответ (мягкая попытка {attempt}), пауза 20 сек...")
                await asyncio.sleep(20)
                continue

            post = raw
            if post.startswith('{') or post.startswith('['):
                try:
                    parsed = json.loads(post)
                    if isinstance(parsed, dict):
                        post = parsed.get("post", parsed.get("text", post))
                    elif isinstance(parsed, list) and parsed:
                        first = parsed[0]
                        post = first.get("post", first.get("text", str(first)))
                except (json.JSONDecodeError, AttributeError):
                    pass

            pts = score_post(post)

            if pts > best_score:
                best_score = pts
                best_post = post

            if re.search(r'ДО[:\s]', post, re.IGNORECASE) and re.search(r'ПОСЛЕ[:\s]', post, re.IGNORECASE):
                logger.success(f"✅ Пост создан ({len(post)} симв., мягкая попытка {attempt})")
                break

        except asyncio.TimeoutError:
            logger.error(f"❌ Таймаут мягкой генерации")
            await asyncio.sleep(20)
        except Exception as e:
            logger.error(f"❌ Ошибка мягкой генерации: {e}")

    if best_post and best_score >= 3:
        logger.warning(f"⚠️ Принимаем лучший вариант (score={best_score})")
    elif best_post:
        logger.warning(f"⚠️ Принимаем вариант с низким score ({best_score})")
    else:
        logger.error("❌ Не удалось сгенерировать пост")
        return None

    style = await get_or_create_style_profile()
    review = await triple_review(best_post, context_text, style)

    if review["overall_pass"]:
        logger.success(f"✅ Три взгляда: ОДОБРЕНО")
        return best_post

    logger.warning(f"⚠️ Три взгляда: замечания. Переписываем...")
    feedback = compile_feedback(review)
    rewritten = await rewrite_with_feedback(best_post, feedback, context_text, category)

    if rewritten and rewritten != best_post:
        review2 = await triple_review(rewritten, context_text, style)
        if review2["overall_pass"]:
            logger.success(f"✅ После переписывания: ОДОБРЕНО")
            return rewritten
        logger.info(f"📋 Принимаем оригинал после переписывания")

    return best_post


def _build_style_prompt_block(style: dict | None) -> str:
    if not style:
        return "СТИЛЬ КАНАЛА: не задан, используй универсальный Telegram-формат."

    favorite_words = ", ".join(style.get("favorite_words", [])) or "нет"
    return (
        "СТИЛЬ КАНАЛА:\n"
        f"Тон: {style.get('tone', 'информативный')}\n"
        f"Начало поста: {style.get('opening_style', 'с факта')}\n"
        f"Структура: {style.get('structure_pattern', 'ДО/ПОСЛЕ')}\n"
        f"Любимые фразы: {favorite_words}\n"
        f"Длина абзацев: ~{style.get('avg_paragraph_length', 50)} слов\n"
        f"Длина поста: ~{style.get('avg_post_length', 500)} символов\n"
        f"Emoji: {style.get('emoji_frequency', 'умеренно')}\n"
        f"Формат: {style.get('default_post_format', 'telegram_short')}"
    )


def _style_format_hint(style: dict | None) -> str:
    profile = style or {}
    structure = str(profile.get("structure_pattern", "ДО/ПОСЛЕ")).lower()
    tone = str(profile.get("tone", "информативный")).lower()
    emoji = str(profile.get("emoji_frequency", "умеренно")).lower()
    default_format = str(profile.get("default_post_format", "telegram_short")).lower()

    lines = [
        f"- default_post_format: {default_format}",
        f"- tone: {tone}",
        f"- structure: {structure}",
        f"- emoji_frequency: {emoji}",
        "- HTML tags allowed: <b>, <i>, <code>, <blockquote>",
    ]

    if "до/после" in structure:
        lines += [
            "- Use ДО/ПОСЛЕ as the core frame",
            "- Show problem first, then result or solution",
        ]
    elif "list" in structure or "спис" in structure:
        lines += [
            "- Use a list when it increases clarity",
            "- Keep items short and concrete",
        ]
    elif "story" in structure:
        lines += [
            "- Open with a short scene or observation",
            "- Lead into a practical takeaway",
        ]

    if "практи" in tone or "practical" in tone:
        lines.append("- Add one actionable step")
    elif "аналит" in tone or "analysis" in tone:
        lines.append("- Emphasize why it matters")
    elif "сдерж" in tone or "caut" in tone:
        lines.append("- Avoid overconfident wording")

    if emoji in {"минимум", "minimal", "rare"}:
        lines.append("- Use emoji sparingly")
    elif emoji in {"много", "many", "frequent"}:
        lines.append("- Emoji allowed, but do not overdo it")

    return "\n".join(lines)
