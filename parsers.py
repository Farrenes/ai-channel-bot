import feedparser
import requests
from bs4 import BeautifulSoup
import html
import re
from loguru import logger
import time
from functools import wraps
from typing import Callable


def rate_limit(calls_per_second: float = 1.0):
    """Декоратор для ограничения частоты вызовов"""
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            last_called[0] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator


@rate_limit(0.5)  # Не более 1 запроса в 2 секунды
def parse_habr():
    logger.info("Парсим Habr (20 записей)...")
    try:
        response = requests.get(
            "https://habr.com/ru/rss/hub/artificial_intelligence/all/?fl=ru",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        response.encoding = 'utf-8'
        feed = feedparser.parse(response.text)
        return [{
            "title": entry.title,
            "description": re.sub(r'<[^>]+>', '', entry.summary)[:400] + "..."
        } for entry in feed.entries[:20]]
    except Exception as e:
        logger.error(f"Habr error: {e}")
        return []


@rate_limit(0.5)
def parse_producthunt():
    logger.info("Парсим ProductHunt (15 записей)...")
    try:
        response = requests.get(
            "https://www.producthunt.com/feed",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        response.encoding = 'utf-8'
        feed = feedparser.parse(response.text)
        return [{"title": e.title, "description": getattr(e, 'description', '')[:400]} for e in feed.entries[:15]]
    except Exception as e:
        logger.error(f"ProductHunt error: {e}")
        return []


@rate_limit(0.5)
def parse_github_trending():
    """Парсим GitHub Trending за daily, weekly, monthly (3 страницы)"""
    logger.info("Парсим GitHub Trending (daily, weekly, monthly)...")
    periods = ['daily', 'weekly', 'monthly']
    all_items = []
    for period in periods:
        try:
            url = f"https://github.com/trending?since={period}"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            items = [{
                "title": repo.find('h3').get_text(strip=True).replace('\n', ' - ') if repo.find('h3') else "",
                "description": repo.find('p', class_='col-9').get_text(strip=True) if repo.find('p', class_='col-9') else ""
            } for repo in soup.select('article')[:5]]
            all_items.extend(items)
            time.sleep(1)  # небольшая пауза, чтобы не банили
        except Exception as e:
            logger.error(f"GitHub {period} error: {e}")
    logger.info(f"Собрано {len(all_items)} репозиториев с GitHub Trending")
    return all_items


@rate_limit(0.5)
def parse_hackernews():
    logger.info("Парсим HackerNews (20 записей)...")
    try:
        response = requests.get(
            "https://news.ycombinator.com/rss",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        response.encoding = 'utf-8'
        feed = feedparser.parse(response.text)
        return [{"title": e.title, "description": ""} for e in feed.entries[:20]]
    except Exception as e:
        logger.error(f"HackerNews error: {e}")
        return []


@rate_limit(0.33)  # Не более 1 запроса в 3 секунды
def parse_flowgpt():
    """Парсим FlowGPT (пытаемся взять несколько страниц, если есть пагинация)"""
    logger.info("Парсим FlowGPT (страницы 1-3)...")
    all_prompts = []
    for page in range(1, 4):
        try:
            url = f"https://flowgpt.com/trending?page={page}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://flowgpt.com/",
                "DNT": "1",
            }
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                logger.warning(f"FlowGPT страница {page} вернула {response.status_code}, пропускаем")
                continue
            soup = BeautifulSoup(response.text, 'html.parser')
            prompts = []
            for card in soup.select('div.prompt-card, div.prompt-item, article'):
                title_elem = card.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|name|heading'))
                desc_elem = card.find(['p', 'div'], class_=re.compile(r'description|excerpt|text'))
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                description = desc_elem.get_text(strip=True) if desc_elem else ""
                if len(description) > 400:
                    description = description[:400] + "..."
                if title:
                    prompts.append({"title": f"Промт: {title}", "description": description})
            if not prompts:
                # альтернативный метод
                for h in soup.find_all(['h2', 'h3']):
                    title = h.get_text(strip=True)
                    desc = h.find_next('p')
                    desc_text = desc.get_text(strip=True) if desc else ""
                    if len(desc_text) > 400:
                        desc_text = desc_text[:400] + "..."
                    if title:
                        prompts.append({"title": f"Промт: {title}", "description": desc_text})
            all_prompts.extend(prompts)
            time.sleep(1)
        except Exception as e:
            logger.error(f"FlowGPT page {page} error: {e}")
    logger.info(f"Собрано {len(all_prompts)} промтов с FlowGPT")
    return all_prompts[:18]  # ограничим до 18, чтобы не перегружать


@rate_limit(0.5)
def parse_awesome_prompts():
    logger.info("Парсим awesome-chatgpt-prompts...")
    try:
        url = "https://raw.githubusercontent.com/f/awesome-chatgpt-prompts/main/README.md"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            logger.error(f"GitHub вернул статус {response.status_code}")
            return []
        content = response.text
        prompts = []
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('### Act as'):
                title = line.replace('###', '').strip()
                desc_lines = []
                i += 1
                while i < len(lines) and lines[i].strip() == '':
                    i += 1
                while i < len(lines) and not lines[i].startswith('###'):
                    desc_lines.append(lines[i].strip())
                    i += 1
                desc = ' '.join(desc_lines)
                if len(desc) > 400:
                    desc = desc[:400] + "..."
                if title and desc:
                    prompts.append({"title": f"Промт: {title}", "description": desc})
            else:
                i += 1
        logger.info(f"Собрано {len(prompts)} промтов из awesome-chatgpt-prompts")
        return prompts[:16]
    except Exception as e:
        logger.error(f"Awesome prompts error: {e}")
        return []


@rate_limit(0.33)
def parse_reddit_subreddit(subreddit: str, limit: int = 30):
    """Парсинг сабреддита с увеличенным лимитом"""
    logger.info(f"Парсим r/{subreddit} (до {limit} записей)...")
    try:
        url = f"https://www.reddit.com/r/{subreddit}/.rss?limit={limit}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            logger.warning(f"Reddit r/{subreddit} вернул статус {response.status_code}")
            return []
        feed = feedparser.parse(response.text)
        posts = []
        for entry in feed.entries[:limit]:
            title = entry.title
            description = re.sub(r'<[^>]+>', '', entry.description) if hasattr(entry, 'description') else ""
            description = html.unescape(description)[:600]
            if len(description) < 50 and hasattr(entry, 'content'):
                description = re.sub(r'<[^>]+>', '', entry.content[0].value) if entry.content else ""
                description = html.unescape(description)[:600]
            if title:
                posts.append({
                    "title": title,
                    "description": description
                })
        logger.info(f"Собрано {len(posts)} постов из r/{subreddit}")
        return posts
    except Exception as e:
        logger.error(f"Reddit r/{subreddit} error: {e}")
        return []


def parse_reddit_chatgpt():
    return parse_reddit_subreddit("ChatGPT", limit=30)


def parse_reddit_openai():
    return parse_reddit_subreddit("OpenAI", limit=30)


def parse_reddit_promptengineering():
    return parse_reddit_subreddit("PromptEngineering", limit=30)


@rate_limit(0.33)
def parse_theresanaiforthat():
    """Парсим theresanaiforthat.com, страницы 1-3"""
    logger.info("Парсим theresanaiforthat.com (страницы 1-3)...")
    all_tools = []
    for page in range(1, 4):
        try:
            url = f"https://theresanaiforthat.com/page/{page}/"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                logger.warning(f"theresanaiforthat страница {page} вернула {response.status_code}")
                continue
            soup = BeautifulSoup(response.text, 'html.parser')
            tools = []
            for card in soup.select('div.tool-card, div.ai-tool, div.tool-item, article'):
                title_elem = card.find(['h2', 'h3', 'a'], class_=re.compile(r'title|name|heading|tool-title'))
                desc_elem = card.find(['p', 'div'], class_=re.compile(r'description|excerpt|summary'))
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                description = desc_elem.get_text(strip=True) if desc_elem else ""
                if len(description) > 400:
                    description = description[:400] + "..."
                if title:
                    tools.append({
                        "title": f"AI-инструмент: {title}",
                        "description": description
                    })
            if not tools:
                for h in soup.find_all(['h2', 'h3']):
                    title = h.get_text(strip=True)
                    desc = h.find_next('p')
                    desc_text = desc.get_text(strip=True) if desc else ""
                    if len(desc_text) > 400:
                        desc_text = desc_text[:400] + "..."
                    if title:
                        tools.append({
                            "title": f"AI-инструмент: {title}",
                            "description": desc_text
                        })
            all_tools.extend(tools)
            time.sleep(1)
        except Exception as e:
            logger.error(f"theresanaiforthat page {page} error: {e}")
    logger.info(f"Собрано {len(all_tools)} AI-инструментов с theresanaiforthat")
    return all_tools[:24]


@rate_limit(0.33)
def parse_futuretools():
    """Парсим futuretools.io, страницы 1-3"""
    logger.info("Парсим futuretools.io (страницы 1-3)...")
    all_tools = []
    for page in range(1, 4):
        try:
            url = f"https://futuretools.io/page/{page}/"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                logger.warning(f"futuretools.io страница {page} вернула {response.status_code}")
                continue
            soup = BeautifulSoup(response.text, 'html.parser')
            tools = []
            for card in soup.select('div.tool-card, div.tool-item, article, div[class*="tool"]'):
                title_elem = card.find(['h2', 'h3', 'a'], class_=re.compile(r'title|name|heading'))
                desc_elem = card.find(['p', 'div'], class_=re.compile(r'description|excerpt|summary'))
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                description = desc_elem.get_text(strip=True) if desc_elem else ""
                if len(description) > 400:
                    description = description[:400] + "..."
                if title:
                    tools.append({
                        "title": f"Нейросеть: {title}",
                        "description": description
                    })
            if not tools:
                for h in soup.find_all(['h2', 'h3']):
                    title = h.get_text(strip=True)
                    desc = h.find_next('p')
                    desc_text = desc.get_text(strip=True) if desc else ""
                    if len(desc_text) > 400:
                        desc_text = desc_text[:400] + "..."
                    if title:
                        tools.append({
                            "title": f"Нейросеть: {title}",
                            "description": desc_text
                        })
            all_tools.extend(tools)
            time.sleep(1)
        except Exception as e:
            logger.error(f"futuretools.io page {page} error: {e}")
    logger.info(f"Собрано {len(all_tools)} нейросетей с futuretools.io")
    return all_tools[:24]


# ==================== FACTORY FUNCTIONS FOR DYNAMIC PARSERS ====================

def make_rss_parser(url: str, name: str = "generic", limit: int = 20) -> Callable:
    @rate_limit(0.5)
    def parser():
        logger.info(f"Парсим RSS {name} ({url})...")
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            response.encoding = 'utf-8'
            feed = feedparser.parse(response.text)
            return [{
                "title": entry.title,
                "description": re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:400] + "..."
            } for entry in feed.entries[:limit]]
        except Exception as e:
            logger.error(f"RSS {name} error: {e}")
            return []
    parser.__name__ = f"parse_{name}"
    return parser


def make_html_parser(url: str, name: str = "generic",
                     title_selector: str = "h2, h3, h1",
                     desc_selector: str = "p",
                     limit: int = 20) -> Callable:
    @rate_limit(0.5)
    def parser():
        logger.info(f"Парсим HTML {name} ({url})...")
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = []
            for card in soup.select(title_selector)[:limit]:
                title = card.get_text(strip=True)[:200]
                desc_el = card.find_next(desc_selector)
                desc = desc_el.get_text(strip=True)[:400] if desc_el else ""
                if title:
                    items.append({"title": title, "description": desc})
            return items
        except Exception as e:
            logger.error(f"HTML {name} error: {e}")
            return []
    parser.__name__ = f"parse_{name}"
    return parser


def build_parsers_for_topic(sources: list) -> list:
    parsers = []
    for src in sources:
        src_type = src.get('type', 'rss')
        url = src.get('url', '')
        name = src.get('name', url.split('//')[-1][:30])
        if src_type == 'rss':
            parsers.append(make_rss_parser(url, name))
        elif src_type == 'html':
            parsers.append(make_html_parser(url, name,
                title_selector=src.get('title_selector', 'h2, h3'),
                desc_selector=src.get('desc_selector', 'p')))
    return parsers