import pytest
from unittest.mock import patch, MagicMock
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

HABR_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Habr AI Hub</title>
<item>
<title>Новая нейросеть для генерации кода</title>
<description>Обзор новой модели для автоматической генерации кода на Python</description>
<link>https://habr.com/ru/post/123456/</link>
</item>
<item>
<title>ChatGPT получил обновление</title>
<description>OpenAI выпустила обновление для ChatGPT с улучшенным контекстом</description>
<link>https://habr.com/ru/post/123457/</link>
</item>
</channel>
</rss>"""

PH_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Product Hunt</title>
<item>
<title>AI Writer Pro</title>
<description>A new AI-powered writing assistant</description>
<link>https://producthunt.com/posts/ai-writer-pro</link>
</item>
</channel>
</rss>"""

HN_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Hacker News</title>
<item>
<title>Launching GPT-5 benchmarks</title>
<description>OpenAI releases GPT-5 benchmarks showing major improvements</description>
<link>https://news.ycombinator.com/item?id=12345</link>
</item>
</channel>
</rss>"""

REDDIT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<title type="html">Best AI prompts for coding</title>
<summary type="html">A collection of the best prompts for AI-assisted coding</summary>
<link href="https://reddit.com/r/ChatGPT/comments/abc123/"/>
</entry>
</feed>"""

AWESOME_PROMPTS_MD = """# Awesome ChatGPT Prompts

### Act as AI Prompt Engineer
Create effective prompts for AI models

### Act as Code Reviewer
Review code for best practices and security issues

### Act as Data Scientist
Analyze data and create visualizations
"""

GH_TRENDING_HTML = """<html><body>
<ol class="repo-list">
<li><h2><a href="/user/repo1">AI-Tool</a></h2><p>A powerful AI tool for developers</p></li>
<li><h2><a href="/user/repo2">ML-Lib</a></h2><p>Machine learning library in Python</p></li>
</ol>
</body></html>"""

TAAFT_HTML = """<html><body>
<div class="tool-card"><h3>AI Image Generator</h3><p>Generate images from text</p></div>
<div class="tool-card"><h3>ChatBot Builder</h3><p>Build custom chatbots</p></div>
</body></html>"""

FUTURETOOLS_HTML = """<html><body>
<div class="tool-item"><h3>Voice AI</h3><p>AI-powered voice cloning</p></div>
<div class="tool-item"><h3>Code Assistant</h3><p>AI code completion</p></div>
</body></html>"""

FLOWGPT_HTML = """<html><body>
<div class="prompt-card"><h3>Best ChatGPT prompts</h3><p>Top prompts for productivity</p></div>
<div class="prompt-card"><h3>AI writing prompts</h3><p>Prompts for creative writing</p></div>
</body></html>"""


def _mock_response(text, status_code=200):
    resp = MagicMock()
    resp.text = text
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


class TestParseHabr:
    @patch("parsers.time.sleep")
    @patch("parsers.requests.get")
    def test_parse_habr_success(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(HABR_RSS)
        result = parse_habr()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["title"] == "Новая нейросеть для генерации кода"
        assert "description" in result[0]

    @patch("parsers.time.sleep")
    @patch("parsers.requests.get")
    def test_parse_habr_empty(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response("<rss></rss>")
        result = parse_habr()
        assert isinstance(result, list)


class TestParseProductHunt:
    @patch("parsers.time.sleep")
    @patch("parsers.requests.get")
    def test_parse_producthunt_success(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(PH_RSS)
        result = parse_producthunt()
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "title" in result[0]


class TestParseHackerNews:
    @patch("parsers.time.sleep")
    @patch("parsers.requests.get")
    def test_parse_hackernews_success(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(HN_RSS)
        result = parse_hackernews()
        assert isinstance(result, list)
        assert len(result) >= 1


class TestParseGithubTrending:
    @patch("parsers.time.sleep")
    @patch("parsers.requests.get")
    def test_parse_github_trending_success(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(GH_TRENDING_HTML)
        result = parse_github_trending()
        assert isinstance(result, list)


class TestParseReddit:
    @patch("parsers.time.sleep")
    @patch("parsers.requests.get")
    def test_parse_reddit_chatgpt(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(REDDIT_RSS)
        result = parse_reddit_chatgpt()
        assert isinstance(result, list)

    @patch("parsers.time.sleep")
    @patch("parsers.requests.get")
    def test_parse_reddit_openai(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(REDDIT_RSS)
        result = parse_reddit_openai()
        assert isinstance(result, list)

    @patch("parsers.time.sleep")
    @patch("parsers.requests.get")
    def test_parse_reddit_promptengineering(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(REDDIT_RSS)
        result = parse_reddit_promptengineering()
        assert isinstance(result, list)


class TestParseAwesomePrompts:
    @patch("parsers.time.sleep")
    @patch("parsers.requests.get")
    def test_parse_awesome_prompts_success(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(AWESOME_PROMPTS_MD)
        result = parse_awesome_prompts()
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "title" in result[0]


class TestParseTheresAnAiForThat:
    @patch("parsers.time.sleep")
    @patch("parsers.requests.get")
    def test_parse_taaft_success(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(TAAFT_HTML)
        result = parse_theresanaiforthat()
        assert isinstance(result, list)


class TestParseFutureTools:
    @patch("parsers.time.sleep")
    @patch("parsers.requests.get")
    def test_parse_futuretools_success(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(FUTURETOOLS_HTML)
        result = parse_futuretools()
        assert isinstance(result, list)


class TestParseFlowGpt:
    @patch("parsers.time.sleep")
    @patch("parsers.requests.get")
    def test_parse_flowgpt_success(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(FLOWGPT_HTML)
        result = parse_flowgpt()
        assert isinstance(result, list)
