import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import asyncio
from loguru import logger
from aiogram import Bot, Router, F, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

from config import ADMIN_BOT_TOKEN, ADMIN_BOT_ENV_NAMES, ALLOWED_USERS, validate_required_env
from database import (
    init_db, get_pending_ideas, get_category_stats,
    add_style_example, get_style_profile, close_db,
    get_last_post_time
)
from llm_generator import extract_style_profile
from topic_config import (
    create_topic, get_topic, get_active_topics, update_topic,
    delete_topic as delete_topic_db
)
from topic_prompt_manager import (
    generate_topic_prompt, get_cached_prompt, assemble_generation_prompt
)

validate_required_env(ADMIN_BOT_ENV_NAMES)

bot = Bot(token=ADMIN_BOT_TOKEN)
router = Router()
dp = Dispatcher()
dp.include_router(router)

STYLE_EXAMPLES_BUFFER = []


def build_shop_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔥 Купить", callback_data="billing:buy"),
                InlineKeyboardButton(text="💬 Техподдержка", callback_data="billing:support"),
            ],
            [
                InlineKeyboardButton(text="💡 О боте", callback_data="billing:about"),
            ],
        ]
    )


def build_shop_text() -> str:
    return (
        "🔥 <b>BotTG — автопостинг и контент-завод для Telegram</b>\n\n"
        "Бот помогает выбрать тариф, подключить источники, автоматически собирать материалы, "
        "генерировать посты и публиковать их в канал.\n\n"
        "<b>Тарифы:</b>\n"
        "🟢 <b>Beta</b> — 499 ₽\n"
        "🟢 <b>Base</b> — 990 ₽\n"
        "🟢 <b>Pro</b> — 2 990 ₽\n"
        "🟢 <b>Studio</b> — 7 990 ₽\n\n"
        "<b>Что внутри:</b>\n"
        "• автопостинг без ручного редактора\n"
        "• проверка источников\n"
        "• scoring и генерация постов\n"
        "• review и защита от дублей\n"
        "• лимиты по подписке\n\n"
        "Нажмите <b>Купить</b>, чтобы выбрать тариф и продолжить."
    )


def is_authorized(user_id: int) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(build_shop_text(), parse_mode="HTML", reply_markup=build_shop_keyboard())
    await message.answer(
        "Команды администратора:\n"
        "/topics — список тем\n"
        "/addtopic <название> — создать тему\n"
        "/addsource <тема> <url> — добавить источник\n"
        "/setchannel <тема> @channel — канал для публикации\n"
        "/setkeywords <тема> key1,key2 — ключевые слова\n"
        "/setcategories <тема> Кат1:40,Кат2:60 — категории\n"
        "/generate_prompt <тема> — сгенерировать промпт\n"
        "/regenerate_prompt <тема> — перегенерировать\n"
        "/preview_post <тема> — тестовый пост\n"
        "/addstyle — начать обучение стилю\n"
        "/done — завершить обучение\n"
        "/style — текущий профиль\n"
        "/stats — статистика\n"
        "/deactivate <тема> — приостановить тему"
    )


@router.message(F.text == "/shop")
async def cmd_shop(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(build_shop_text(), parse_mode="HTML", reply_markup=build_shop_keyboard())

# ==================== TOPIC MANAGEMENT ====================

@router.message(F.text == "/topics")
async def cmd_topics(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    topics = await get_active_topics()
    if not topics:
        await message.answer("рџ“‹ РќРµС‚ РЅР°СЃС‚СЂРѕРµРЅРЅС‹С… С‚РµРј.\n\nРСЃРїРѕР»СЊР·СѓР№С‚Рµ /addtopic <РЅР°Р·РІР°РЅРёРµ>")
        return
    lines = ["рџ“‹ <b>РђРєС‚РёРІРЅС‹Рµ С‚РµРјС‹:</b>\n"]
    for t in topics:
        ch = t.get('target_channel', 'вќЊ РЅРµ Р·Р°РґР°РЅ')
        src_count = len(t.get('sources', []))
        has_prompt = 'вњ…' if t.get('prompt_id') else 'вќЊ'
        lines.append(f"вЂў <b>{t['name']}</b> в†’ {ch}")
        lines.append(f"  РСЃС‚РѕС‡РЅРёРєРѕРІ: {src_count} | РџСЂРѕРјРїС‚: {has_prompt}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text.startswith("/addtopic "))
async def cmd_addtopic(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Р¤РѕСЂРјР°С‚: /addtopic <РЅР°Р·РІР°РЅРёРµ>\nРџСЂРёРјРµСЂ: /addtopic cooking")
        return
    name = parts[1].strip().lower()
    await create_topic(name)
    await message.answer(
        f"вњ… РўРµРјР° <b>{name}</b> СЃРѕР·РґР°РЅР°!\n\n"
        f"РЎР»РµРґСѓСЋС‰РёРµ С€Р°РіРё:\n"
        f"1. /setchannel {name} @РІР°С€_РєР°РЅР°Р»\n"
        f"2. /addsource {name} https://...\n"
        f"3. /setkeywords {name} РєР»СЋС‡1,РєР»СЋС‡2\n"
        f"4. /setcategories {name} РљР°С‚1:40,РљР°С‚2:60\n"
        f"5. /generate_prompt {name}"
    )


@router.message(F.text.startswith("/addsource "))
async def cmd_addsource(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Р¤РѕСЂРјР°С‚: /addsource <С‚РµРјР°> <url>\nРџСЂРёРјРµСЂ: /addsource cooking https://habr.com/rss")
        return
    topic_name = parts[1].strip().lower()
    url = parts[2].strip()
    topic = await get_topic(topic_name)
    if not topic:
        await message.answer(f"вќЊ РўРµРјР° '{topic_name}' РЅРµ РЅР°Р№РґРµРЅР°.\nРЎРѕР·РґР°Р№С‚Рµ: /addtopic {topic_name}")
        return
    sources = topic.get('sources', [])
    sources.append({"type": "rss", "url": url, "name": url.split("//")[-1][:30]})
    await update_topic(topic_name, sources=sources)
    await message.answer(f"вњ… РСЃС‚РѕС‡РЅРёРє РґРѕР±Р°РІР»РµРЅ РІ '{topic_name}':\n{url}\n\nР’СЃРµРіРѕ: {len(sources)}")


@router.message(F.text.startswith("/setchannel "))
async def cmd_setchannel(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Р¤РѕСЂРјР°С‚: /setchannel <С‚РµРјР°> <@channel РёР»Рё ID>")
        return
    topic_name = parts[1].strip().lower()
    channel = parts[2].strip()
    await update_topic(topic_name, target_channel=channel)
    await message.answer(f"вњ… РљР°РЅР°Р» РґР»СЏ '{topic_name}': {channel}")


@router.message(F.text.startswith("/setkeywords "))
async def cmd_setkeywords(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Р¤РѕСЂРјР°С‚: /setkeywords <С‚РµРјР°> <РєР»СЋС‡1,РєР»СЋС‡2,РєР»СЋС‡3>")
        return
    topic_name = parts[1].strip().lower()
    keywords = [k.strip().lower() for k in parts[2].split(",") if k.strip()]
    await update_topic(topic_name, keywords=keywords)
    await message.answer(f"вњ… РљР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР° РґР»СЏ '{topic_name}': {', '.join(keywords)}")


@router.message(F.text.startswith("/setcategories "))
async def cmd_setcategories(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Р¤РѕСЂРјР°С‚: /setcategories <С‚РµРјР°> <РљР°С‚1:40,РљР°С‚2:60>")
        return
    topic_name = parts[1].strip().lower()
    cats = {}
    for pair in parts[2].split(","):
        if ":" in pair:
            name, weight = pair.split(":", 1)
            cats[name.strip()] = int(weight.strip())
    await update_topic(topic_name, categories=cats)
    await message.answer(f"вњ… РљР°С‚РµРіРѕСЂРёРё РґР»СЏ '{topic_name}': {cats}")


@router.message(F.text.startswith("/generate_prompt "))
async def cmd_generate_prompt(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Р¤РѕСЂРјР°С‚: /generate_prompt <С‚РµРјР°>")
        return
    topic_name = parts[1].strip().lower()
    topic = await get_topic(topic_name)
    if not topic:
        await message.answer(f"вќЊ РўРµРјР° '{topic_name}' РЅРµ РЅР°Р№РґРµРЅР°.")
        return
    await message.answer(f"вЏі Р“РµРЅРµСЂР°С†РёСЏ РїСЂРѕРјРїС‚Р° РґР»СЏ '{topic_name}'...\n5-С€Р°РіРѕРІС‹Р№ pipeline, ~30 СЃРµРє.")
    try:
        result = await generate_topic_prompt(topic_name, topic_name)
        preview = result['final_prompt'][:500] + "..." if len(result['final_prompt']) > 500 else result['final_prompt']
        await message.answer(
            f"вњ… <b>РџСЂРѕРјРїС‚ СЃРіРµРЅРµСЂРёСЂРѕРІР°РЅ!</b>\n\n"
            f"ID: {result['prompt_id']}\n"
            f"РўРѕРєРµРЅС‹: {result['tokens_used']}\n\n"
            f"<b>РџСЂРµРІСЊСЋ:</b>\n{preview}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"вќЊ РћС€РёР±РєР°: {e}")


@router.message(F.text.startswith("/regenerate_prompt "))
async def cmd_regenerate_prompt(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Р¤РѕСЂРјР°С‚: /regenerate_prompt <С‚РµРјР°>")
        return
    topic_name = parts[1].strip().lower()
    await message.answer(f"вЏі РџРµСЂРµРіРµРЅРµСЂР°С†РёСЏ РїСЂРѕРјРїС‚Р° РґР»СЏ '{topic_name}'...")
    try:
        from topic_prompt_manager import regenerate_topic_prompt
        result = await regenerate_topic_prompt(topic_name)
        await message.answer(
            f"вњ… РџСЂРѕРјРїС‚ РїРµСЂРµРіРµРЅРµСЂРёСЂРѕРІР°РЅ!\n"
            f"РўРѕРєРµРЅС‹: {result['tokens_used']}"
        )
    except Exception as e:
        await message.answer(f"вќЊ РћС€РёР±РєР°: {e}")


@router.message(F.text.startswith("/preview_post "))
async def cmd_preview_post(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Р¤РѕСЂРјР°С‚: /preview_post <С‚РµРјР°>")
        return
    topic_name = parts[1].strip().lower()
    topic = await get_topic(topic_name)
    if not topic:
        await message.answer(f"вќЊ РўРµРјР° '{topic_name}' РЅРµ РЅР°Р№РґРµРЅР°.")
        return
    prompt = await get_cached_prompt(topic_name)
    if not prompt:
        await message.answer(f"вќЊ РџСЂРѕРјРїС‚ РЅРµ СЃРіРµРЅРµСЂРёСЂРѕРІР°РЅ.\nРСЃРїРѕР»СЊР·СѓР№С‚Рµ /generate_prompt {topic_name}")
        return
    await message.answer(f"вЏі Р“РµРЅРµСЂР°С†РёСЏ С‚РµСЃС‚РѕРІРѕРіРѕ РїРѕСЃС‚Р°...")
    try:
        from llm_generator import generate_post_from_context
        style = await get_style_profile()
        post = await generate_post_from_context(
            f"РўРµРјР°: {topic_name}. РђРєС‚СѓР°Р»СЊРЅС‹Рµ РЅРѕРІРѕСЃС‚Рё Рё С‚СЂРµРЅРґС‹.",
            topic_name=topic_name
        )
        if post:
            await message.answer(f"рџ“ќ <b>РўРµСЃС‚РѕРІС‹Р№ РїРѕСЃС‚ ({topic_name}):</b>\n\n{post}", parse_mode="HTML")
        else:
            await message.answer("вќЊ РќРµ СѓРґР°Р»РѕСЃСЊ СЃРіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ РїРѕСЃС‚.")
    except Exception as e:
        await message.answer(f"вќЊ РћС€РёР±РєР°: {e}")


@router.message(F.text.startswith("/deactivate "))
async def cmd_deactivate(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Р¤РѕСЂРјР°С‚: /deactivate <С‚РµРјР°>")
        return
    topic_name = parts[1].strip().lower()
    await update_topic(topic_name, is_active=False)
    await message.answer(f"вЏё РўРµРјР° '{topic_name}' РїСЂРёРѕСЃС‚Р°РЅРѕРІР»РµРЅР°.")


# ==================== STYLE MANAGEMENT ====================

@router.message(F.text == "/addstyle")
async def cmd_addstyle(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    await message.answer(
        "рџ“ќ РџРµСЂРµС€Р»РёС‚Рµ РјРЅРµ 10-20 РІР°С€РёС… Р»СѓС‡С€РёС… РїРѕСЃС‚РѕРІ РёР· РєР°РЅР°Р»Р°.\n"
        "РЇ РёР·СѓС‡Сѓ СЃС‚РёР»СЊ Рё Р±СѓРґСѓ РїРёСЃР°С‚СЊ С‚Р°Рє Р¶Рµ.\n\n"
        "РљРѕРіРґР° Р·Р°РєРѕРЅС‡РёС‚Рµ вЂ” РЅР°РїРёС€РёС‚Рµ /done"
    )


@router.message(F.text == "/done")
async def cmd_done(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    if not STYLE_EXAMPLES_BUFFER:
        await message.answer("вќЊ РќРµС‚ РїСЂРёРјРµСЂРѕРІ. РЎРЅР°С‡Р°Р»Р° РїРµСЂРµС€Р»РёС‚Рµ РїРѕСЃС‚С‹.")
        return
    count = len(STYLE_EXAMPLES_BUFFER)
    for text in STYLE_EXAMPLES_BUFFER:
        await add_style_example(text)
    STYLE_EXAMPLES_BUFFER.clear()
    await message.answer(f"вњ… РЎРѕС…СЂР°РЅРµРЅРѕ {count} РїСЂРёРјРµСЂРѕРІ. РР·РІР»РµРєР°СЋ РїСЂРѕС„РёР»СЊ СЃС‚РёР»СЏ...")
    profile = await extract_style_profile()
    if profile:
        await message.answer(
            f"вњ… <b>РџСЂРѕС„РёР»СЊ СЃС‚РёР»СЏ:</b>\n"
            f"РўРѕРЅ: {profile.get('tone', '?')}\n"
            f"РќР°С‡Р°Р»Рѕ: {profile.get('opening_style', '?')}\n"
            f"РЎС‚СЂСѓРєС‚СѓСЂР°: {profile.get('structure_pattern', '?')}\n"
            f"Р¤СЂР°Р·С‹: {', '.join(profile.get('favorite_words', []))}",
            parse_mode="HTML"
        )
    else:
        await message.answer("вљ пёЏ РќРµ СѓРґР°Р»РѕСЃСЊ РёР·РІР»РµС‡СЊ РїСЂРѕС„РёР»СЊ.")


@router.message(F.forward_origin)
async def handle_forwarded(message: Message):
    if not is_authorized(message.from_user.id):
        return
    if message.text:
        STYLE_EXAMPLES_BUFFER.append(message.text)
        await message.answer(f"рџ“Њ РЎРѕС…СЂР°РЅС‘РЅ ({len(STYLE_EXAMPLES_BUFFER)} С€С‚.)")


@router.message(F.text == "/style")
async def cmd_style(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    profile = await get_style_profile()
    if not profile:
        await message.answer("вќЊ РџСЂРѕС„РёР»СЊ РЅРµ СЃРѕР·РґР°РЅ. РСЃРїРѕР»СЊР·СѓР№С‚Рµ /addstyle")
        return
    await message.answer(
        f"рџ“Љ <b>РџСЂРѕС„РёР»СЊ СЃС‚РёР»СЏ:</b>\n\n"
        f"РўРѕРЅ: {profile.get('tone', '?')}\n"
        f"РќР°С‡Р°Р»Рѕ: {profile.get('opening_style', '?')}\n"
        f"РЎС‚СЂСѓРєС‚СѓСЂР°: {profile.get('structure_pattern', '?')}\n"
        f"Р¤СЂР°Р·С‹: {', '.join(profile.get('favorite_words', []))}\n"
        f"Р”Р»РёРЅР° Р°Р±Р·Р°С†РµРІ: ~{profile.get('avg_paragraph_length', '?')} СЃР»РѕРІ\n"
        f"Emoji: {profile.get('emoji_frequency', '?')}\n\n"
        f"РћР±РЅРѕРІР»С‘РЅ: {profile.get('updated_at', '?')}"
    )


# ==================== STATS ====================

@router.message(F.text == "/stats")
async def cmd_stats(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ.")
        return
    stats7 = await get_category_stats(days=7)
    total7 = sum(stats7.values())
    stats1 = await get_category_stats(days=1)
    total1 = sum(stats1.values())
    topics = await get_active_topics()
    last_post = await get_last_post_time()

    lines = [
        "рџ“Љ <b>РЎС‚Р°С‚РёСЃС‚РёРєР° РєРѕРЅС‚РµРЅС‚-Р±РѕС‚Р°</b>\n",
        f"РђРєС‚РёРІРЅС‹С… С‚РµРј: {len(topics)}",
        f"РџРѕСЃС‚РѕРІ Р·Р° 24С‡: {total1}",
        f"РџРѕСЃС‚РѕРІ Р·Р° 7 РґРЅРµР№: {total7}",
        f"РџРѕСЃР»РµРґРЅРёР№ РїРѕСЃС‚: {last_post}",
        "",
        "<b>РџРѕ РєР°С‚РµРіРѕСЂРёСЏРј (7 РґРЅРµР№):</b>"
    ]
    for cat, count in sorted(stats7.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat}: {count}")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ==================== LIFECYCLE ====================

async def on_startup():
    await init_db()
    logger.info("Admin bot Р·Р°РїСѓС‰РµРЅ")


async def on_shutdown():
    await bot.session.close()
    await close_db()
    logger.info("Admin bot РѕСЃС‚Р°РЅРѕРІР»РµРЅ")


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    logger.info("рџ¤– Admin bot (@zhiizn_admin_bot) Р·Р°РїСѓСЃРєР°РµС‚СЃСЏ...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


