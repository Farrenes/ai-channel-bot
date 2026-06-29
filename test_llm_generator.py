import pytest
from unittest.mock import patch, MagicMock
import json


with patch("llm_generator.client", MagicMock()):
    from llm_generator import extract_json
    from scoring import has_cjk, is_russian_or_english, cpu_prefilter, clean_html
    from scoring.constants import AI_KEYWORDS


class TestHasCjk:
    def test_returns_false_for_english(self):
        assert has_cjk("Hello world") is False

    def test_returns_false_for_russian(self):
        assert has_cjk("Привет мир") is False

    def test_returns_true_for_chinese(self):
        assert has_cjk("你好世界") is True

    def test_returns_true_for_kanji(self):
        assert has_cjk("漢字テスト") is True

    def test_returns_false_for_empty(self):
        assert has_cjk("") is False

    def test_mixed_text_with_cjk(self):
        assert has_cjk("Hello 你好") is True

    def test_mixed_text_without_cjk(self):
        assert has_cjk("Hello Привет 123") is False


class TestIsRussianOrEnglish:
    def test_english(self):
        assert is_russian_or_english("Hello world") is True

    def test_russian(self):
        assert is_russian_or_english("Привет мир") is True

    def test_chinese(self):
        assert is_russian_or_english("你好世界") is False

    def test_japanese_hiragana(self):
        assert is_russian_or_english("こんにちは") is False

    def test_empty(self):
        assert is_russian_or_english("") is True

    def test_numbers_and_symbols(self):
        assert is_russian_or_english("123 !@#") is True


class TestCleanHtml:
    def test_removes_script_tags(self):
        result = clean_html("<p>Hello</p><script>alert('x')</script><p>World</p>")
        assert "alert" not in result
        assert "Hello" in result

    def test_removes_style_tags(self):
        result = clean_html("<style>.red{color:red}</style><p>Text</p>")
        assert ".red" not in result
        assert "Text" in result

    def test_strips_html_tags(self):
        result = clean_html("<b>Bold</b> and <i>Italic</i>")
        assert "<b>" not in result
        assert "Bold" in result

    def test_unescapes_html_entities(self):
        result = clean_html("&amp; &lt; &gt;")
        assert "&amp;" not in result
        assert "&" in result

    def test_removes_images(self):
        result = clean_html("Text https://example.com/photo.jpg more")
        assert "photo.jpg" not in result

    def test_removes_utm_params(self):
        result = clean_html("https://example.com?utm_source=google&utm_medium=cpc")
        assert "utm_source" not in result

    def test_truncates_long_text(self):
        long_text = "A" * 300
        result = clean_html(long_text)
        assert len(result) <= 205
        assert result.endswith("...")

    def test_empty_input(self):
        assert clean_html("") == ""
        assert clean_html(None) == ""


class TestExtractJson:
    def test_plain_json_object(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_plain_json_array(self):
        result = extract_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_json_in_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result: {"key": "value"} done.'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="Пустой текст"):
            extract_json("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="Пустой текст"):
            extract_json("   ")

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Не удалось распарсить"):
            extract_json("not json at all {{{")

    def test_multiple_json_objects(self):
        text = '{"a":1} {"b":2}'
        result = extract_json(text)
        assert isinstance(result, list)
        assert len(result) == 2


class TestCpuPrefilter:
    def test_filters_short_titles(self):
        items = [{"title": "Hi", "description": "AI tool"}]
        assert cpu_prefilter(items) == []

    def test_filters_cjk(self):
        items = [{"title": "你好世界 AI工具", "description": ""}]
        assert cpu_prefilter(items) == []

    def test_filters_no_ai_keyword(self):
        items = [{"title": "Great cooking recipe for dinner", "description": ""}]
        assert cpu_prefilter(items) == []

    def test_keeps_ai_content(self):
        items = [{"title": "New AI model from OpenAI", "description": ""}]
        result = cpu_prefilter(items)
        assert len(result) == 1

    def test_ai_keyword_in_description(self):
        items = [{"title": "Amazing new tool released today", "description": "Uses GPT-4 for chat"}]
        result = cpu_prefilter(items)
        assert len(result) == 1

    def test_deduplicates_by_title(self):
        items = [
            {"title": "New AI model released today", "description": ""},
            {"title": "New AI model released today", "description": "duplicate"},
        ]
        result = cpu_prefilter(items)
        assert len(result) == 1

    def test_filters_spam_titles(self):
        items = [{"title": "[ removed by reddit ]", "description": "AI stuff"}]
        assert cpu_prefilter(items) == []

    def test_filters_too_few_words(self):
        items = [{"title": "AI rocks", "description": ""}]
        assert cpu_prefilter(items) == []

    def test_empty_title(self):
        items = [{"title": "", "description": "AI tool"}]
        assert cpu_prefilter(items) == []

    def test_multiple_valid_items(self):
        items = [
            {"title": "New AI model from OpenAI is amazing", "description": ""},
            {"title": "ChatGPT gets major update today", "description": ""},
            {"title": "Local recipes for dinner tonight", "description": ""},
        ]
        result = cpu_prefilter(items)
        assert len(result) == 2

    def test_filters_low_value_tutorials(self):
        items = [
            {"title": "AI Tutorial for Beginners 101", "description": "AI stuff"},
            {"title": "Getting Started with ChatGPT", "description": "AI guide"},
            {"title": "New AI model from Anthropic released today", "description": ""},
        ]
        result = cpu_prefilter(items)
        assert len(result) == 1
        assert "Anthropic" in result[0]["title"]

    def test_trims_description(self):
        items = [{"title": "New AI model from OpenAI today", "description": "A" * 300}]
        result = cpu_prefilter(items)
        assert len(result) == 1
        assert len(result[0]["description"]) <= 205
