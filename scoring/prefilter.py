import re
import html
import unicodedata
from loguru import logger
from scoring.constants import AI_KEYWORDS, LOW_VALUE_PATTERNS, CHUNK_SIZE


def has_cjk(text: str) -> bool:
    for char in text:
        try:
            name = unicodedata.name(char, "")
            if "CJK" in name:
                return True
        except ValueError:
            pass
    return False


def is_russian_or_english(text: str) -> bool:
    if has_cjk(text):
        return False
    for char in text:
        try:
            name = unicodedata.name(char, "")
            if "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name:
                return False
        except ValueError:
            pass
    return True


def clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<!--[\s\S]*?-->', '', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = re.sub(r'https?://[^\s<>"]+\.(jpg|png|gif|svg|webp|ico)(\?[^\s<>"]*)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'data:image/[^\s"]+;base64,[A-Za-z0-9+/=]+', '', text)
    text = re.sub(r'[?&](utm_\w+|ref|source|campaign|fbclid|gclid)=[^&\s]*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 200:
        text = text[:200] + "..."
    return text


def cpu_prefilter(items: list) -> list:
    filtered = []
    seen_titles = set()
    for item in items:
        title = (item.get('title') or '').strip()
        desc = (item.get('description') or '').strip()

        if not title or len(title) < 8:
            continue
        if has_cjk(title + " " + desc):
            continue
        if not is_russian_or_english(title):
            continue

        title_lower = title.lower()
        if title_lower in ('[ removed by reddit ]', 'plz help me', 'soon at your local school'):
            continue
        if len(title.split()) < 3:
            continue

        if LOW_VALUE_PATTERNS.search(title):
            continue

        has_ai = any(kw in title_lower for kw in AI_KEYWORDS)
        if not has_ai and desc:
            has_ai = any(kw in desc.lower() for kw in AI_KEYWORDS)
        if not has_ai:
            continue

        title_norm = title_lower[:80]
        if title_norm in seen_titles:
            continue
        seen_titles.add(title_norm)

        item['description'] = clean_html(desc)[:200]
        filtered.append(item)
    return filtered


SIEVE_BATCH_SIZE = 3


async def fast_theme_check(items: list, topic: str = "") -> list:
    if not items:
        return []
    passed = []
    for item in items:
        title = (item.get('title') or '').lower()
        desc = (item.get('description') or '').lower()
        combined = title + " " + desc
        matches = sum(1 for kw in AI_KEYWORDS if kw in combined)
        if matches >= 2:
            passed.append(item)
        elif matches == 1 and len(title.split()) >= 4:
            passed.append(item)
    logger.info(f"🔍 Сито (локальное): {len(passed)}/{len(items)} прошли тематический фильтр")
    return passed


def chunk_content(raw_content: str) -> list:
    items = raw_content.split("\n\n")
    chunks = []
    for i in range(0, len(items), CHUNK_SIZE):
        chunks.append("\n\n".join(items[i:i + CHUNK_SIZE]))
    return chunks if chunks else [raw_content]
