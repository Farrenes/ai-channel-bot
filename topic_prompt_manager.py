import asyncio
import sys
import os
from loguru import logger
from topic_config import get_topic, save_topic_prompt, get_topic_prompt


PROMPTAPP_PATH = os.getenv("PROMPTAPP_PATH", r"C:\Users\dima\PycharmProjects\promptapp")
if PROMPTAPP_PATH and os.path.isdir(PROMPTAPP_PATH):
    sys.path.insert(0, PROMPTAPP_PATH)
try:
    from prompt_generator import PromptGenerator
    PROMPTAPP_AVAILABLE = True
except ImportError:
    PROMPTAPP_AVAILABLE = False
    logger.warning("promptapp не найден. Генерация промптов недоступна.")


async def generate_topic_prompt(topic_name: str, topic_description: str = None,
                                 api_key: str = None) -> dict:
    if not PROMPTAPP_AVAILABLE:
        raise RuntimeError(
            "promptapp не установлен. Укажите PROMPTAPP_PATH или установите пакет в окружение."
        )

    description = topic_description or topic_name
    search_text = (
        f"Telegram канал о {description}. "
        f"Создавай посты с целью максимальной вовлеченности аудитории. "
        f"Формат: ДО/ПОСЛЕ + блок-цитата с гайдом. "
        f"Стиль: экспертный, но доступный. "
        f"Длина: 140-180 слов. HTML-разметка."
    )

    logger.info(f"Генерация промпта для темы '{topic_name}' через promptapp...")

    gen = PromptGenerator(api_key=api_key)
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, gen.generate, search_text)

    prompt_id = await save_topic_prompt(topic_name, result)
    await _link_prompt_to_topic(topic_name, prompt_id)

    logger.success(f"Промпт для '{topic_name}' сгенерирован (ID: {prompt_id}, "
                   f"токены: {result['tokens']['total']})")

    return {
        "prompt_id": prompt_id,
        "final_prompt": result["final_prompt"],
        "tokens_used": result["tokens"]["total"],
    }


async def _link_prompt_to_topic(topic_name: str, prompt_id: int):
    from topic_config import update_topic
    await update_topic(topic_name, prompt_id=prompt_id)


async def get_cached_prompt(topic_name: str) -> str:
    prompt_data = await get_topic_prompt(topic_name)
    if prompt_data:
        return prompt_data['final_prompt']
    return None


async def assemble_generation_prompt(topic_config: dict, context_text: str,
                                      style_profile: dict = None) -> str:
    topic_name = topic_config.get('name', 'general')

    base_prompt = await get_cached_prompt(topic_name)

    if not base_prompt:
        base_prompt = (
            f"Ты контент-стратег для Telegram-канала о {topic_name}. "
            f"Создавай посты с максимальной вовлеченностью. "
            f"Формат: ДО/ПОСЛЕ + блок-цитата. "
            f"Стиль: экспертный, доступный. 140-180 слов. HTML."
        )

    style_block = _build_style_block(style_profile)
    format_rules = _build_format_rules(style_profile)
    guardrails = _build_style_guardrails(style_profile)

    return f"{base_prompt}\n{style_block}\n{format_rules}\n{guardrails}\n\nКонтекст для поста:\n{context_text}"


def _build_style_block(style_profile: dict | None) -> str:
    profile = style_profile or {}
    favorite_words = ", ".join(profile.get("favorite_words", [])) or "нет"
    return (
        "\nСтиль Telegram-поста:\n"
        f"- Тон: {profile.get('tone', 'информативный')}\n"
        f"- Начало: {profile.get('opening_style', 'с факта')}\n"
        f"- Структура: {profile.get('structure_pattern', 'ДО/ПОСЛЕ')}\n"
        f"- Любимые фразы: {favorite_words}\n"
        f"- Emoji: {profile.get('emoji_frequency', 'умеренно')}\n"
        f"- Длина абзацев: ~{profile.get('avg_paragraph_length', 50)} слов\n"
        f"- Длина поста: ~{profile.get('avg_post_length', 500)} символов\n"
        f"- default_post_format: {profile.get('default_post_format', 'telegram_short')}\n"
    )


def _build_format_rules(style_profile: dict | None) -> str:
    profile = style_profile or {}
    structure = str(profile.get("structure_pattern", "ДО/ПОСЛЕ")).lower()
    tone = str(profile.get("tone", "информативный")).lower()
    emoji = str(profile.get("emoji_frequency", "умеренно")).lower()

    lines = [
        "\nФормат:",
        "- Заголовок должен соответствовать стилю канала",
        "- Сохраняй Telegram-ритм: короткие абзацы, ясные переходы",
        "- Не делай текст простынёй",
        "- HTML: <b>, <i>, <code>, <blockquote>",
    ]

    if "до/после" in structure or "before/after" in structure:
        lines += [
            "- **ДО:** проблема, ограничение или исходная ситуация",
            "- **ПОСЛЕ:** результат, решение или улучшение",
            "- <blockquote>краткий полезный блок с шагами или нюансами</blockquote>",
        ]
    elif "list" in structure or "спис" in structure:
        lines += [
            "- Используй списки, если они естественно усиливают полезность",
            "- Каждый пункт должен нести отдельную мысль",
        ]
    elif "story" in structure or "history" in structure:
        lines += [
            "- Начинай с короткой сцены или наблюдения",
            "- Дальше веди к выводу без лишней воды",
        ]
    else:
        lines += [
            "- Построй текст вокруг главной мысли и одного практического вывода",
        ]

    if "практи" in tone or "practical" in tone:
        lines.append("- Дай читателю применимый шаг или инструкцию")
    elif "аналит" in tone or "analysis" in tone:
        lines.append("- Подчеркни выводы, причины и следствия")
    elif "сдерж" in tone or "caut" in tone:
        lines.append("- Не усиливай утверждения без необходимости")

    if emoji in {"минимум", "minimal", "rare"}:
        lines.append("- Emoji используй минимально, только если это усиливает подачу")
    elif emoji in {"много", "many", "frequent"}:
        lines.append("- Emoji можно использовать чаще, но без визуального шума")

    return "\n".join(lines)


def _build_style_guardrails(style_profile: dict | None) -> str:
    profile = style_profile or {}
    return (
        "\nГраницы качества:\n"
        "- Не копируй стиль формально, если это делает пост пустым\n"
        "- Не уходи в слишком сухой или слишком разговорный тон\n"
        "- Не используй нейрориторику и нейромаркеры\n"
        "- Не ломай структуру канала ради универсальности\n"
        f"- Сохраняй формат, совместимый с {profile.get('default_post_format', 'telegram_short')}\n"
    )


async def regenerate_topic_prompt(topic_name: str) -> dict:
    topic = await get_topic(topic_name)
    if not topic:
        raise ValueError(f"Тема '{topic_name}' не найдена")

    description = f"{topic_name}. Канал: {topic.get('target_channel', 'не задан')}"
    result = await generate_topic_prompt(topic_name, description)

    from topic_config import update_topic
    await update_topic(topic_name, prompt_id=result['prompt_id'])

    return result
