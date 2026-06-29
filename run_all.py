import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from aiogram import Bot, Router, F, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart

from config import (
    ADMIN_BOT_TOKEN,
    ADMIN_BOT_ENV_NAMES,
    BOT_TOKEN,
    CHANNEL_ID,
    ALLOWED_USERS,
    validate_required_env,
)
from database import init_db, close_db
from llm_generator import test_api

# ==================== SHARED STATE ====================
BOT_RUNNING = True
validate_required_env(ADMIN_BOT_ENV_NAMES)


def is_authorized(user_id: int) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


# ==================== CONTENT BOT ====================
content_bot = Bot(token=BOT_TOKEN)
content_router = Router()
content_dp = Dispatcher()
content_dp.include_router(content_router)


@content_router.message(F.text == "/start")
async def content_start(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    status = "🟢 Работает" if BOT_RUNNING else "🔴 Остановлен"
    await message.answer(
        f"🤖 <b>AI Content Bot</b>\n\n"
        f"Статус: {status}\n\n"
        f"Команды:\n"
        f"/status — статус бота\n"
        f"/style — профиль стиля\n"
        f"/stats — статистика\n\n"
        f"Управление через @zhiizn_admin_bot",
        parse_mode="HTML"
    )


@content_router.message(F.text == "/status")
async def content_status(message: Message):
    if not is_authorized(message.from_user.id):
        return
    status = "🟢 Работает" if BOT_RUNNING else "🔴 Остановлен"
    await message.answer(f"Статус: {status}")


# ==================== ADMIN BOT ====================
admin_bot = Bot(token=ADMIN_BOT_TOKEN)
admin_router = Router()
admin_dp = Dispatcher()
admin_dp.include_router(admin_router)

STYLE_EXAMPLES_BUFFER = []


@admin_router.message(CommandStart())
async def admin_start(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    status = "🟢 Работает" if BOT_RUNNING else "🔴 Остановлен"
    await message.answer(
        f"🤖 Admin Bot - Управление\n\n"
        f"Статус контент-бота: {status}\n\n"
        f"Управление ботом:\n"
        f"/start_bot - запустить контент-бот\n"
        f"/stop_bot - остановить контент-бот\n\n"
        f"Темы:\n"
        f"/topics - список тем\n"
        f"/addtopic name - создать тему\n"
        f"/addsource topic url - добавить источник\n"
        f"/setchannel topic @channel - канал\n"
        f"/setkeywords topic key1,key2 - ключевые слова\n"
        f"/setcategories topic Кат1:40,Кат2:60\n\n"
        f"Промпты:\n"
        f"/generate_prompt topic - генерация\n"
        f"/preview_post topic - тест\n\n"
        f"Стиль:\n"
        f"/addstyle - обучение\n"
        f"/done - завершить\n"
        f"/style - профиль\n\n"
        f"Прочее:\n"
        f"/stats - статистика"
    )


@admin_router.message(F.text == "/start_bot")
async def admin_start_bot(message: Message):
    global BOT_RUNNING
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    if BOT_RUNNING:
        await message.answer("🟢 Бот уже работает!")
        return
    BOT_RUNNING = True
    asyncio.create_task(run_content_bot())
    await message.answer("🟢 Контент-бот запущен! Публикации начнутся после сбора контента.")


@admin_router.message(F.text == "/stop_bot")
async def admin_stop_bot(message: Message):
    global BOT_RUNNING
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    if not BOT_RUNNING:
        await message.answer("🔴 Бот уже остановлен!")
        return
    BOT_RUNNING = False
    await message.answer("🔴 Контент-бот остановлен. Публикации прекращены.")


# ==================== ADMIN TOPIC COMMANDS ====================

from topic_config import (
    create_topic, get_topic, get_active_topics, update_topic
)
from topic_prompt_manager import generate_topic_prompt, get_cached_prompt
from llm_generator import generate_post_from_context
from database import get_style_profile, get_category_stats, get_last_post_time


@admin_router.message(F.text == "/topics")
async def admin_topics(message: Message):
    if not is_authorized(message.from_user.id):
        return
    topics = await get_active_topics()
    if not topics:
        await message.answer("📋 Нет тем. Используйте /addtopic <название>")
        return
    lines = ["📋 <b>Активные темы:</b>\n"]
    for t in topics:
        ch = t.get('target_channel', '❌ не задан')
        src_count = len(t.get('sources', []))
        has_prompt = '✅' if t.get('prompt_id') else '❌'
        lines.append(f"• <b>{t['name']}</b> → {ch}")
        lines.append(f"  Источников: {src_count} | Промпт: {has_prompt}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@admin_router.message(F.text.startswith("/addtopic "))
async def admin_addtopic(message: Message):
    if not is_authorized(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /addtopic <название>")
        return
    name = parts[1].strip().lower()
    await create_topic(name)
    await message.answer(
        f"✅ Тема <b>{name}</b> создана!\n\n"
        f"Далее:\n"
        f"1. /setchannel {name} @канал\n"
        f"2. /addsource {name} https://...\n"
        f"3. /setkeywords {name} ключ1,ключ2\n"
        f"4. /generate_prompt {name}",
        parse_mode="HTML"
    )


@admin_router.message(F.text.startswith("/addsource "))
async def admin_addsource(message: Message):
    if not is_authorized(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: /addsource <тема> <url>")
        return
    topic_name = parts[1].strip().lower()
    url = parts[2].strip()
    topic = await get_topic(topic_name)
    if not topic:
        await message.answer(f"❌ Тема '{topic_name}' не найдена.")
        return
    sources = topic.get('sources', [])
    sources.append({"type": "rss", "url": url, "name": url.split("//")[-1][:30]})
    await update_topic(topic_name, sources=sources)
    await message.answer(f"✅ Источник добавлен: {url}\nВсего: {len(sources)}")


@admin_router.message(F.text.startswith("/setchannel "))
async def admin_setchannel(message: Message):
    if not is_authorized(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: /setchannel <тема> <@channel>")
        return
    topic_name = parts[1].strip().lower()
    channel = parts[2].strip()
    await update_topic(topic_name, target_channel=channel)
    await message.answer(f"✅ Канал для '{topic_name}': {channel}")


@admin_router.message(F.text.startswith("/setkeywords "))
async def admin_setkeywords(message: Message):
    if not is_authorized(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: /setkeywords <тема> <ключ1,ключ2>")
        return
    topic_name = parts[1].strip().lower()
    keywords = [k.strip().lower() for k in parts[2].split(",") if k.strip()]
    await update_topic(topic_name, keywords=keywords)
    await message.answer(f"✅ Ключевые слова: {', '.join(keywords)}")


@admin_router.message(F.text.startswith("/setcategories "))
async def admin_setcategories(message: Message):
    if not is_authorized(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: /setcategories <тема> <Кат1:40,Кат2:60>")
        return
    topic_name = parts[1].strip().lower()
    cats = {}
    for pair in parts[2].split(","):
        if ":" in pair:
            name, weight = pair.split(":", 1)
            cats[name.strip()] = int(weight.strip())
    await update_topic(topic_name, categories=cats)
    await message.answer(f"✅ Категории: {cats}")


@admin_router.message(F.text.startswith("/generate_prompt "))
async def admin_generate_prompt(message: Message):
    if not is_authorized(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /generate_prompt <тема>")
        return
    topic_name = parts[1].strip().lower()
    topic = await get_topic(topic_name)
    if not topic:
        await message.answer(f"❌ Тема '{topic_name}' не найдена.")
        return
    await message.answer(f"⏳ Генерация промпта для '{topic_name}'...")
    try:
        result = await generate_topic_prompt(topic_name, topic_name)
        preview = result['final_prompt'][:500] + "..." if len(result['final_prompt']) > 500 else result['final_prompt']
        await message.answer(
            f"✅ <b>Промпт готов!</b>\n\n"
            f"ID: {result['prompt_id']}\n"
            f"Токены: {result['tokens_used']}\n\n"
            f"<b>Превью:</b>\n{preview}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@admin_router.message(F.text.startswith("/preview_post "))
async def admin_preview_post(message: Message):
    if not is_authorized(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /preview_post <тема>")
        return
    topic_name = parts[1].strip().lower()
    topic = await get_topic(topic_name)
    if not topic:
        await message.answer(f"❌ Тема '{topic_name}' не найдена.")
        return
    await message.answer(f"⏳ Генерация тестового поста...")
    try:
        post = await generate_post_from_context(
            f"Тема: {topic_name}. Актуальные новости и тренды.",
            topic_name=topic_name
        )
        if post:
            await message.answer(f"📝 <b>Тест ({topic_name}):</b>\n\n{post}", parse_mode="HTML")
        else:
            await message.answer("❌ Не удалось сгенерировать.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@admin_router.message(F.text.startswith("/deactivate "))
async def admin_deactivate(message: Message):
    if not is_authorized(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /deactivate <тема>")
        return
    topic_name = parts[1].strip().lower()
    await update_topic(topic_name, is_active=False)
    await message.answer(f"⏸ Тема '{topic_name}' приостановлена.")


# ==================== STYLE ====================

@admin_router.message(F.text == "/addstyle")
async def admin_addstyle(message: Message):
    if not is_authorized(message.from_user.id):
        return
    await message.answer("📝 Перешлите посты для обучения стиля. Завершите /done")


@admin_router.message(F.text == "/done")
async def admin_done(message: Message):
    if not is_authorized(message.from_user.id):
        return
    if not STYLE_EXAMPLES_BUFFER:
        await message.answer("❌ Нет примеров.")
        return
    from database import add_style_example
    for text in STYLE_EXAMPLES_BUFFER:
        await add_style_example(text)
    count = len(STYLE_EXAMPLES_BUFFER)
    STYLE_EXAMPLES_BUFFER.clear()
    from llm_generator import extract_style_profile
    profile = await extract_style_profile()
    if profile:
        await message.answer(f"✅ Сохранено {count} примеров. Профиль создан.")
    else:
        await message.answer(f"✅ Сохранено {count} примеров.")


@admin_router.message(F.forward_origin)
async def admin_forwarded(message: Message):
    if not is_authorized(message.from_user.id):
        return
    if message.text:
        STYLE_EXAMPLES_BUFFER.append(message.text)
        await message.answer(f"📌 ({len(STYLE_EXAMPLES_BUFFER)} шт.)")


@admin_router.message(F.text == "/style")
async def admin_style(message: Message):
    if not is_authorized(message.from_user.id):
        return
    profile = await get_style_profile()
    if not profile:
        await message.answer("❌ Профиль не создан. /addstyle")
        return
    await message.answer(
        f"📊 <b>Стиль:</b>\n"
        f"Тон: {profile.get('tone', '?')}\n"
        f"Начало: {profile.get('opening_style', '?')}\n"
        f"Структура: {profile.get('structure_pattern', '?')}\n"
        f"Фразы: {', '.join(profile.get('favorite_words', []))}",
        parse_mode="HTML"
    )


@admin_router.message(F.text == "/stats")
async def admin_stats(message: Message):
    if not is_authorized(message.from_user.id):
        return
    stats7 = await get_category_stats(days=7)
    total7 = sum(stats7.values())
    stats1 = await get_category_stats(days=1)
    total1 = sum(stats1.values())
    topics = await get_active_topics()
    last_post = await get_last_post_time()
    lines = [
        "📊 <b>Статистика</b>\n",
        f"Тем: {len(topics)} | За 24ч: {total1} | За 7д: {total7}",
        f"Последний пост: {last_post}",
    ]
    for cat, count in sorted(stats7.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat}: {count}")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ==================== CONTENT BOT LOGIC ====================

import importlib.util as _iu
_main_spec = _iu.spec_from_file_location("bot_main", os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py"))
_bot_main = _iu.module_from_spec(_main_spec)
_main_spec.loader.exec_module(_bot_main)
fetch_and_store_job = _bot_main.fetch_and_store_job
adaptive_publish_job = _bot_main.adaptive_publish_job


async def run_content_bot():
    global BOT_RUNNING
    while BOT_RUNNING:
        try:
            logger.info("🔄 Контент-бот: запуск цикла...")
            await fetch_and_store_job()
            await adaptive_publish_job()
            logger.info("✅ Цикл завершён. Следующий через 30 мин.")
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле: {e}")
        await asyncio.sleep(1800)  # 30 минут


# ==================== LAUNCH ====================

async def main():
    await init_db()
    logger.info("✅ БД инициализирована")

    if not await test_api():
        logger.error("❌ API не работает!")
        return

    logger.info("🚀 Запуск обоих ботов...")

    content_task = asyncio.create_task(
        content_dp.start_polling(content_bot)
    )
    admin_task = asyncio.create_task(
        admin_dp.start_polling(admin_bot)
    )
    asyncio.create_task(run_content_bot())

    logger.info("🤖 Оба бота запущены!")
    logger.info("📱 Контент-бот: @zhiizn_ai")
    logger.info("🔧 Админ-бот: @zhiizn_admin_bot")
    logger.info("⏳ Контент-бот запущен автоматически")

    await asyncio.gather(content_task, admin_task)


if __name__ == "__main__":
    asyncio.run(main())
