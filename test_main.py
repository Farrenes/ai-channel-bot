import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os


with patch("main.bot", MagicMock()), \
     patch("main.router", MagicMock()), \
     patch("main.dp", MagicMock()), \
     patch("main.scheduler", MagicMock()):
    with patch("main.init_db", new_callable=AsyncMock), \
         patch("main.test_api", new_callable=AsyncMock, return_value=True):
        sys.modules.setdefault("database", MagicMock())
        sys.modules.setdefault("llm_generator", MagicMock())
        sys.modules.setdefault("parsers", MagicMock())
        from main import (
            extract_keywords, extract_ngrams, detect_trends,
            get_time_bucket, get_preferred_categories,
            is_authorized, CATEGORY_TARGETS
        )


class TestExtractKeywords:
    def test_extracts_words(self):
        result = extract_keywords("Hello World")
        assert "hello" in result
        assert "world" in result

    def test_filters_stop_words(self):
        result = extract_keywords("the quick brown fox")
        assert "the" not in result
        assert "quick" in result

    def test_filters_short_words(self):
        result = extract_keywords("AI is ok for us")
        assert "ai" not in result

    def test_russian_stop_words(self):
        result = extract_keywords("это новый промпт для чатбота")
        assert "это" not in result
        assert "промпт" in result

    def test_empty_text(self):
        result = extract_keywords("")
        assert result == []


class TestExtractNgrams:
    def test_bigrams(self):
        result = extract_ngrams("machine learning model released today", n=2)
        assert "machine learning" in result
        assert "learning model" in result

    def test_trigrams(self):
        result = extract_ngrams("machine learning model released today", n=3)
        assert "machine learning model" in result

    def test_empty_text(self):
        result = extract_ngrams("", n=2)
        assert result == []


class TestDetectTrends:
    def test_finds_trend_from_multiple_sources(self):
        items = [
            {"title": "OpenAI releases new machine learning model today", "description": ""},
            {"title": "machine learning model from OpenAI beats benchmarks", "description": ""},
            {"title": "Another machine learning model announcement from OpenAI", "description": ""},
        ]
        trends = detect_trends(items)
        assert len(trends) > 0
        assert any("machine learning" in t["topic"] or "openai" in t["topic"] for t in trends)

    def test_no_trend_single_source(self):
        items = [
            {"title": "Unique quantum computing breakthrough today", "description": ""},
            {"title": "Another unrelated topic for testing", "description": ""},
        ]
        trends = detect_trends(items)
        assert len(trends) == 0

    def test_empty_items(self):
        trends = detect_trends([])
        assert trends == []

    def test_trend_sorted_by_count(self):
        items = [
            {"title": "machine learning tool A released today", "description": ""},
            {"title": "machine learning tool B released today", "description": ""},
            {"title": "machine learning tool C released today", "description": ""},
            {"title": "machine learning tool D released today", "description": ""},
            {"title": "Unique product for developers", "description": ""},
        ]
        trends = detect_trends(items)
        if trends:
            assert trends[0]["count"] >= trends[-1]["count"]


class TestGetTimeBucket:
    @patch("main.datetime")
    def test_morning(self, mock_dt):
        mock_dt.now.return_value.hour = 8
        assert get_time_bucket() == "morning"

    @patch("main.datetime")
    def test_day(self, mock_dt):
        mock_dt.now.return_value.hour = 14
        assert get_time_bucket() == "day"

    @patch("main.datetime")
    def test_evening(self, mock_dt):
        mock_dt.now.return_value.hour = 20
        assert get_time_bucket() == "evening"

    @patch("main.datetime")
    def test_night(self, mock_dt):
        mock_dt.now.return_value.hour = 2
        assert get_time_bucket() == "night"


class TestGetPreferredCategories:
    @patch("main.get_time_bucket", return_value="morning")
    def test_morning_categories(self, _):
        cats = get_preferred_categories()
        assert "Инструменты" in cats

    @patch("main.get_time_bucket", return_value="day")
    def test_day_categories(self, _):
        cats = get_preferred_categories()
        assert "Промпты" in cats


class TestIsAuthorized:
    def test_empty_whitelist_allows_all(self):
        with patch("main.ALLOWED_USERS", set()):
            assert is_authorized(123456) is True

    def test_whitelist_allows_listed_user(self):
        with patch("main.ALLOWED_USERS", {123, 456}):
            assert is_authorized(123) is True

    def test_whitelist_blocks_unlisted_user(self):
        with patch("main.ALLOWED_USERS", {123, 456}):
            assert is_authorized(999) is False


class TestCategoryTargets:
    def test_all_targets_sum_to_100(self):
        total = sum(CATEGORY_TARGETS.values())
        assert total == 100

    def test_has_expected_categories(self):
        assert "Инструменты" in CATEGORY_TARGETS
        assert "Промпты" in CATEGORY_TARGETS
        assert "Кейсы" in CATEGORY_TARGETS
