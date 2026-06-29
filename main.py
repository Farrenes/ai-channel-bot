import asyncio
import signal
import sys
import re
from collections import defaultdict
from datetime import datetime
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from aiogram import Bot, Router, F, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import httpx
from config import BOT_TOKEN, CHANNEL_ID, ALLOWED_USERS, MAIN_BOT_ENV_NAMES, validate_required_env
from database import (
    init_db, get_pending_ideas, update_idea_status, save_post,
    is_title_duplicate, get_recent_published_titles, get_category_stats, close_db,
    add_style_example, add_post_feedback, get_last_post_time, get_style_profile
)
from llm_generator import generate_post_from_context, test_api, deep_research, extract_style_profile
from parsers import (
    parse_habr,
    parse_producthunt,
    parse_github_trending,
    parse_hackernews,
    parse_flowgpt,
    parse_awesome_prompts,
    parse_reddit_promptengineering,
    parse_reddit_chatgpt,
    parse_reddit_openai,
    parse_theresanaiforthat,
    parse_futuretools
)
from topic_config import get_active_topics
from topic_prompt_manager import assemble_generation_prompt

bot = Bot(token=BOT_TOKEN)
router = Router()
dp = Dispatcher()
dp.include_router(router)
scheduler = AsyncIOScheduler()
executor = ThreadPoolExecutor(max_workers=5)

SCORING_SERVICE_URL = "http://127.0.0.1:8001"


def is_authorized(user_id: int) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS

CATEGORY_TARGETS = {
    'Инструменты': 50,
    'Промпты': 20,
    'Кейсы': 15,
    'Подборки': 10,
    'Новости': 5
}

MORNING_CATEGORIES = ['Инструменты', 'Подборки']
DAY_CATEGORIES = ['Промпты', 'Кейсы']
EVENING_CATEGORIES = ['Инструменты', 'Промпты', 'Подборки']
NIGHT_CATEGORIES = ['Новости', 'Кейсы']


def get_time_bucket():
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return 'morning'
    elif 12 <= hour < 18:
        return 'day'
    elif 18 <= hour < 24:
        return 'evening'
    else:
        return 'night'


def get_preferred_categories():
    bucket = get_time_bucket()
    if bucket == 'morning':
        return MORNING_CATEGORIES
    elif bucket == 'day':
        return DAY_CATEGORIES
    elif bucket == 'evening':
        return EVENING_CATEGORIES
    else:
        return NIGHT_CATEGORIES


STOP_WORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
    'on', 'with', 'at', 'by', 'from', 'as', 'into', 'about', 'new', 'how',
    'its', 'that', 'this', 'but', 'not', 'you', 'all', 'any', 'each',
    'which', 'when', 'what', 'there', 'their', 'than', 'some', 'just',
    'also', 'more', 'very', 'most', 'only', 'other', 'like', 'over',
    'after', 'first', 'been', 'make', 'back', 'come', 'give', 'good',
    'и', 'в', 'на', 'не', 'что', 'это', 'как', 'с', 'для', 'от', 'по',
    'из', 'за', 'до', 'при', 'о', 'об', 'но', 'а', 'то', 'все', 'так',
    'его', 'её', 'их', 'вы', 'мы', 'он', 'она', 'они', 'вас', 'нас',
    'который', 'которая', 'которое', 'которые', 'этот', 'эта', 'эти',
    'уже', 'ещё', 'тоже', 'только', 'очень', 'может', 'будет', 'быть',
    'был', 'была', 'были', 'будут', 'если', 'или', 'ни', 'нет', 'да'
}

NGRAM_MIN_HITS = 2


def extract_keywords(text: str) -> list:
    """Извлекает значимые ключевые слова из текста"""
    words = re.findall(r'[a-zA-Zа-яА-ЯёЁ]{4,}', text.lower())
    return [w for w in words if w not in STOP_WORDS]


def extract_ngrams(text: str, n: int = 2) -> list:
    """Извлекает биграммы и триграммы — осмысленные phrase вместо слов"""
    words = re.findall(r'[a-zA-Zа-яА-ЯёЁ]{4,}', text.lower())
    words = [w for w in words if w not in STOP_WORDS]
    ngrams = []
    for i in range(len(words) - n + 1):
        phrase = " ".join(words[i:i + n])
        ngrams.append(phrase)
    return ngrams


def detect_trends(items: list) -> list:
    """Тренд = 2+ источника упомянули одну n-грамму или phrase"""
    topic_sources = defaultdict(list)

    for item in items:
        title = item.get('title', '')
        unigrams = extract_keywords(title)
        bigrams = extract_ngrams(title, 2)
        trigrams = extract_ngrams(title, 3)

        for ng in unigrams + bigrams + trigrams:
            topic_sources[ng].append(item)

    trends = []
    seen_topics = set()
    for topic, sources in topic_sources.items():
        unique_sources = list({s.get('title', ''): s for s in sources}.values())
        min_hits = NGRAM_MIN_HITS if len(topic.split()) >= 2 else 3
        if len(unique_sources) >= min_hits and topic not in seen_topics:
            seen_topics.add(topic)
            trends.append({
                "topic": topic,
                "sources": unique_sources,
                "count": len(unique_sources),
                "is_breaking": len(unique_sources) >= 5
            })

    trends.sort(key=lambda x: x["count"], reverse=True)
    if trends:
        top = trends[0]
        logger.info(f"🔥 Найдено {len(trends)} трендов (топ: '{top['topic']}' — {top['count']} источников)")
    return trends


async def fetch_and_store_job():
    """Задача сбора контента"""
    logger.info("📡 Запуск сбора контента...")
    parsers = [
        parse_habr,
        parse_producthunt,
        parse_github_trending,
        parse_hackernews,
        parse_flowgpt,
        parse_awesome_prompts,
        parse_reddit_promptengineering,
        parse_reddit_chatgpt,
        parse_reddit_openai,
        parse_theresanaiforthat,
        parse_futuretools
    ]

    all_items = []
    loop = asyncio.get_running_loop()

    async def run_parser(parser):
        try:
            return await loop.run_in_executor(executor, parser)
        except Exception as e:
            logger.error(f"Ошибка парсера {parser.__name__}: {e}")
            return []

    logger.info(f"🔄 Запускаем {len(parsers)} парсеров параллельно...")
    tasks = [run_parser(parser) for parser in parsers]
    results = await asyncio.gather(*tasks)

    for result in results:
        all_items.extend(result)

    logger.info(f"📊 Собрано {len(all_items)} материалов со всех источников")

    if not all_items:
        logger.warning("Нет новых материалов для обработки")
        return

    unique_items = []
    for item in all_items:
        if not await is_title_duplicate(item['title']):
            unique_items.append(item)

    if not unique_items:
        logger.info("Все материалы уже есть в базе")
        return

    trends = detect_trends(unique_items)
    if trends:
        for trend in trends[:3]:
            logger.info(f"🔥 ТРЕНД: '{trend['topic']}' ({trend['count']} источников)")

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{SCORING_SERVICE_URL}/score",
                json={"items": unique_items}
            )
            if response.status_code == 200:
                result = response.json()
                logger.success(f"✅ Скоринг: {result.get('scored_items', 0)}/{result.get('total_items', 0)} оценено")
            else:
                logger.error(f"❌ Scoring service вернул {response.status_code}: {response.text}")
    except httpx.ConnectError:
        logger.error("❌ Scoring service недоступен. Убедитесь, что scoring_service.py запущен на порту 8001")
    except Exception as e:
        logger.error(f"❌ Ошибка вызова scoring service: {e}")
    logger.success("✅ Сбор и скоринг завершён")


async def publish_best_job():
    """Задача публикации"""
    logger.info("🔥 Поиск лучшей идеи для публикации...")

    stats = await get_category_stats(days=1)
    total_published = sum(stats.values())

    ideas = await get_pending_ideas(limit=10)
    if not ideas:
        logger.info("Нет идей для публикации")
        return

    preferred = get_preferred_categories()

    selected_idea = None
    for idea in ideas:
        cat = idea['category'] or 'Неизвестно'
        target_percent = CATEGORY_TARGETS.get(cat, 0)
        current_count = stats.get(cat, 0)
        if target_percent == 0:
            continue
        expected = (target_percent / 100) * (total_published + 1)
        if current_count < expected or cat in preferred:
            selected_idea = idea
            break

    if not selected_idea:
        selected_idea = ideas[0]

    logger.info(f"🏆 Выбрана: '{selected_idea['title']}' (кат. {selected_idea['category']}, рейтинг {selected_idea['total_score']})")

    context = f"{selected_idea['title']}: {selected_idea['raw_description']}"

    trend_keywords = extract_keywords(selected_idea['title'])
    is_trending = False
    for kw in trend_keywords:
        if any(kw in idea['title'].lower() for idea in ideas if idea['id'] != selected_idea['id']):
            is_trending = True
            break

    if is_trending or selected_idea['total_score'] >= 80:
        logger.info(f"🔥 Тренд-контекст: углубляем研究 для '{selected_idea['title']}'")
        extra = await deep_research(selected_idea['title'])
        if extra:
            context = f"{context}\n\nДоп. информация:\n{extra}"

    post_text = await generate_post_from_context(
        context,
        category=selected_idea['category']
    )
    if not post_text:
        await update_idea_status(selected_idea['id'], 'failed')
        logger.error(f"❌ Не удалось сгенерировать пост для '{selected_idea['title']}'")
        return

    try:
        sent_message = await bot.send_message(
            chat_id=CHANNEL_ID, text=post_text, parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки в Telegram: {e}")
        await update_idea_status(selected_idea['id'], 'failed')
        return

    await update_idea_status(selected_idea['id'], 'published')
    published_post_id = await save_post(selected_idea['title'], post_text, "RouterAI", selected_idea['category'])
    try:
        await bot.edit_message_reply_markup(
            chat_id=CHANNEL_ID,
            message_id=sent_message.message_id,
            reply_markup=get_feedback_keyboard(published_post_id)
        )
    except Exception as e:
        logger.warning(f"Не удалось добавить feedback-кнопки: {e}")
    logger.success(f"🎉 Пост опубликован: '{selected_idea['title']}'")


def get_feedback_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для обратной связи на пост"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍", callback_data=f"fb:like:{post_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"fb:dislike:{post_id}"),
            InlineKeyboardButton(text="🔄 Переписать", callback_data=f"fb:rewrite:{post_id}"),
        ]
    ])


@router.message(F.text == "/start")
async def cmd_start(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "🤖 AI Channel Bot — автономный редактор\n\n"
        "Команды:\n"
        "/addstyle — добавить пример стиля (перешлите пост)\n"
        "/style — посмотреть текущий профиль стиля\n"
        "/extract_style — извлечь профиль из примеров\n"
        "/stats — статистика публикаций"
    )


@router.message(F.text == "/addstyle")
async def cmd_addstyle(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "📝 Перешлите мне 10-20 ваших лучших постов из канала.\n"
        "Я изучу стиль и буду писать так же.\n\n"
        "Когда закончите — напишите /done"
    )


STYLE_EXAMPLES_BUFFER = []


@router.message(F.text == "/done")
async def cmd_done(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    if not STYLE_EXAMPLES_BUFFER:
        await message.answer("❌ Нет примеров для сохранения. Сначала перешлите посты.")
        return
    count = len(STYLE_EXAMPLES_BUFFER)
    for text in STYLE_EXAMPLES_BUFFER:
        await add_style_example(text)
    STYLE_EXAMPLES_BUFFER.clear()
    await message.answer(f"✅ Сохранено {count} примеров. Извлекаю профиль стиля...")
    profile = await extract_style_profile()
    if profile:
        await message.answer(
            f"✅ Профиль стиля создан:\n"
            f"Тон: {profile.get('tone', '?')}\n"
            f"Начало: {profile.get('opening_style', '?')}\n"
            f"Структура: {profile.get('structure_pattern', '?')}\n"
            f"Фразы: {', '.join(profile.get('favorite_words', []))}"
        )
    else:
        await message.answer("⚠️ Не удалось извлечь профиль. Попробуйте позже.")


@router.message(F.forward_origin)
async def handle_forwarded(message: Message):
    if not is_authorized(message.from_user.id):
        return
    if STYLE_EXAMPLES_BUFFER is not None and message.text:
        STYLE_EXAMPLES_BUFFER.append(message.text)
        await message.answer(f"📌 Сохранён ({len(STYLE_EXAMPLES_BUFFER)} шт.)")


@router.message(F.text == "/style")
async def cmd_style(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    profile = await get_style_profile()
    if not profile:
        await message.answer("❌ Профиль стиля ещё не создан. Используйте /addstyle")
        return
    await message.answer(
        f"📊 Текущий профиль стиля:\n\n"
        f"Тон: {profile.get('tone', '?')}\n"
        f"Начало поста: {profile.get('opening_style', '?')}\n"
        f"Структура: {profile.get('structure_pattern', '?')}\n"
        f"Любимые фразы: {', '.join(profile.get('favorite_words', []))}\n"
        f"Длина абзацев: ~{profile.get('avg_paragraph_length', '?')} слов\n"
        f"Emoji: {profile.get('emoji_frequency', '?')}\n\n"
        f"Обновлён: {profile.get('updated_at', '?')}"
    )


@router.message(F.text == "/stats")
async def cmd_stats(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    stats = await get_category_stats(days=7)
    total = sum(stats.values())
    lines = [f"📊 Статистика за 7 дней ({total} постов):"]
    for cat, count in sorted(stats.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat}: {count}")
    await message.answer("\n".join(lines))


@router.callback_query(F.data.startswith("fb:"))
async def handle_feedback(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    reaction, post_id_str = parts[1], parts[2]
    try:
        post_id = int(post_id_str)
    except ValueError:
        return

    if reaction == "rewrite":
        await callback.answer("🔄 Функция переписывания в разработке", show_alert=True)
        return

    await add_post_feedback(post_id, reaction)
    emoji = "👍" if reaction == "like" else "👎"
    await callback.answer(f"{emoji} Спасибо за фидбэк!")


async def get_pending_ideas_count() -> int:
    ideas = await get_pending_ideas(limit=100)
    return len(ideas)


async def get_today_published_count() -> int:
    stats = await get_category_stats(days=1)
    return sum(stats.values())


async def should_publish_now() -> dict:
    """Определяем, стоит ли публиковать прямо сейчас"""
    pending = await get_pending_ideas_count()
    today_count = await get_today_published_count()
    last_post_time = await get_last_post_time()
    hours_since_last = (datetime.now() - last_post_time).total_seconds() / 3600

    ideas = await get_pending_ideas(limit=1)
    quality_score = ideas[0]['total_score'] if ideas else 0

    if quality_score >= 80 and hours_since_last >= 3:
        return {"publish": True, "reason": f"высокое качество ({quality_score}) + {hours_since_last:.1f}ч"}

    if pending >= 10 and today_count < 8 and hours_since_last >= 4:
        return {"publish": True, "reason": f"много контента ({pending}) + активность ниже нормы"}

    if pending < 3:
        return {"publish": False, "reason": f"мало контента ({pending}), ждём"}

    if quality_score < 40 and quality_score > 0:
        return {"publish": False, "reason": f"контент слабый (score={quality_score}), ждём"}

    if hours_since_last < 2:
        return {"publish": False, "reason": f"недавно публиковали ({hours_since_last:.1f}ч)"}

    return {"publish": True, "reason": "нормальная частота"}


async def adaptive_publish_job():
    """Каждые 30 минут проверяем: публиковать или ждать"""
    logger.info("🔍 Проверка: публиковать сейчас?")
    decision = await should_publish_now()
    if decision['publish']:
        logger.info(f"📤 Публикуем: {decision['reason']}")
        await publish_best_job()
    else:
        logger.info(f"⏳ Пропуск: {decision['reason']}")


async def graceful_shutdown():
    """Корректное завершение работы"""
    logger.info("🛑 Получен сигнал остановки...")
    scheduler.shutdown(wait=False)
    executor.shutdown(wait=False)
    await bot.session.close()
    await close_db()
    logger.info("✅ Бот корректно остановлен")
    sys.exit(0)


async def main():
    validate_required_env(MAIN_BOT_ENV_NAMES)
    await init_db()

    if not await test_api():
        logger.error("❌ API не работает. Бот не запущен.")
        return

    logger.info("🚀 Автономная контент-платформа запущена")

    # СТАРТОВЫЙ ЗАПУСК: сразу парсим и публикуем
    logger.info("🔥 Выполняем стартовый сбор и публикацию...")
    try:
        await fetch_and_store_job()
        await publish_best_job()
    except Exception as e:
        logger.error(f"Ошибка при стартовом выполнении: {e}")

    logger.info("✅ Стартовый цикл завершён. Переходим в режим планировщика.")
    logger.info("⏰ Сбор контента: каждые 30 минут")
    logger.info("⏰ Публикация: каждые 3 часа")

    # Настраиваем планировщик
    scheduler.add_job(
        fetch_and_store_job,
        trigger=IntervalTrigger(minutes=30),
        id='content_collection',
        name='Сбор контента',
        replace_existing=True
    )
    scheduler.add_job(
        adaptive_publish_job,
        trigger=IntervalTrigger(minutes=30),
        id='adaptive_publishing',
        name='Адаптивная публикация',
        replace_existing=True
    )

    # Обработчики сигналов для корректного завершения
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(graceful_shutdown()))
        except NotImplementedError:
            # Windows не поддерживает add_signal_handler
            pass

    scheduler.start()
    logger.info("⏰ Планировщик запущен")

    logger.info("🤖 Бот слушает команды...")
    asyncio.create_task(dp.start_polling(bot))

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        await graceful_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
