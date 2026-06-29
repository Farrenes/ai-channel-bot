import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


@pytest.fixture(autouse=True)
def mock_db_pool():
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch.object(
        __import__("database", fromlist=["db_pool"]),
        "db_pool",
        mock_pool,
    ):
        yield mock_pool, mock_conn


def _get_db():
    return __import__("database", fromlist=[
        "is_title_duplicate", "get_recent_published_titles",
        "add_idea_to_pool", "get_pending_ideas", "get_category_stats",
        "update_idea_status", "save_post", "add_style_example",
        "get_style_examples", "get_style_profile", "save_style_profile",
        "add_post_feedback", "get_feedback_stats", "get_last_post_time",
    ])


class TestIsTitleDuplicate:
    @pytest.mark.asyncio
    async def test_duplicate_in_ideas_pool(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetchval.side_effect = [True, False]
        result = await db.is_title_duplicate("Test Title")
        assert result is True

    @pytest.mark.asyncio
    async def test_duplicate_in_published(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetchval.side_effect = [False, True]
        result = await db.is_title_duplicate("Test Title")
        assert result is True

    @pytest.mark.asyncio
    async def test_not_duplicate(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetchval.side_effect = [False, False]
        result = await db.is_title_duplicate("Test Title")
        assert result is False

    @pytest.mark.asyncio
    async def test_empty_title(self, mock_db_pool):
        db = _get_db()
        result = await db.is_title_duplicate("")
        assert result is False

    @pytest.mark.asyncio
    async def test_none_title(self, mock_db_pool):
        db = _get_db()
        result = await db.is_title_duplicate(None)
        assert result is False


class TestGetRecentPublishedTitles:
    @pytest.mark.asyncio
    async def test_returns_titles(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetch.return_value = [
            {"title": "Post 1"},
            {"title": "Post 2"},
        ]
        result = await db.get_recent_published_titles(limit=2)
        assert result == ["Post 1", "Post 2"]

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetch.return_value = []
        result = await db.get_recent_published_titles()
        assert result == []


class TestAddIdeaToPool:
    @pytest.mark.asyncio
    async def test_inserts_idea(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        idea = {
            "title": "Test Idea",
            "source": "test",
            "link": "http://test.com",
            "category": "Tools",
            "score_b2c": 7,
            "score_utility": 8,
            "score_savability": 6,
            "score_repostability": 5,
            "score_practical": 7,
            "total_score": 70,
            "raw_description": "A test idea",
            "status": "pending",
        }
        await db.add_idea_to_pool(idea)
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_empty_title(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        await db.add_idea_to_pool({"title": ""})
        mock_conn.execute.assert_not_called()


class TestGetPendingIdeas:
    @pytest.mark.asyncio
    async def test_returns_ideas(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetch.return_value = [
            {"id": 1, "title": "Idea 1", "total_score": 80},
        ]
        result = await db.get_pending_ideas(limit=5)
        assert len(result) == 1
        assert result[0]["title"] == "Idea 1"


class TestGetCategoryStats:
    @pytest.mark.asyncio
    async def test_returns_stats(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetch.return_value = [
            {"category": "Tools", "count": 5},
            {"category": "News", "count": 2},
        ]
        result = await db.get_category_stats(days=7)
        assert result == {"Tools": 5, "News": 2}


class TestUpdateIdeaStatus:
    @pytest.mark.asyncio
    async def test_updates_status(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        await db.update_idea_status(1, "published")
        mock_conn.execute.assert_called_once()


class TestSavePost:
    @pytest.mark.asyncio
    async def test_saves_post(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        mock_conn.fetchrow.return_value = {'id': 42}
        db = _get_db()
        post_id = await db.save_post("Title", "Post text", "source", "Tools")
        assert post_id == 42
        mock_conn.fetchrow.assert_called_once()


class TestAddStyleExample:
    @pytest.mark.asyncio
    async def test_adds_example(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        await db.add_style_example("Example post text")
        mock_conn.execute.assert_called_once()


class TestGetStyleExamples:
    @pytest.mark.asyncio
    async def test_returns_examples(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetch.return_value = [
            {"post_text": "Example 1"},
            {"post_text": "Example 2"},
        ]
        result = await db.get_style_examples(limit=2)
        assert result == ["Example 1", "Example 2"]


class TestGetStyleProfile:
    @pytest.mark.asyncio
    async def test_returns_profile(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetchrow.return_value = {
            "tone": "expert",
            "opening_style": "fact-first",
        }
        result = await db.get_style_profile()
        assert result["tone"] == "expert"

    @pytest.mark.asyncio
    async def test_returns_none_when_empty(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetchrow.return_value = None
        result = await db.get_style_profile()
        assert result is None


class TestSaveStyleProfile:
    @pytest.mark.asyncio
    async def test_updates_existing(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetchrow.return_value = {"id": 1}
        profile = {"tone": "casual", "opening_style": "question"}
        await db.save_style_profile(profile)
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_inserts_new(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetchrow.return_value = None
        profile = {"tone": "casual"}
        await db.save_style_profile(profile)
        mock_conn.execute.assert_called_once()


class TestAddPostFeedback:
    @pytest.mark.asyncio
    async def test_adds_feedback(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        await db.add_post_feedback(1, "like")
        mock_conn.execute.assert_called_once()


class TestGetFeedbackStats:
    @pytest.mark.asyncio
    async def test_returns_stats(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetch.return_value = [
            {"reaction": "like", "count": 10},
            {"reaction": "dislike", "count": 2},
        ]
        result = await db.get_feedback_stats(days=7)
        assert result == {"like": 10, "dislike": 2}


class TestGetLastPostTime:
    @pytest.mark.asyncio
    async def test_returns_time(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        now = datetime.now()
        mock_conn.fetchrow.return_value = {"published_at": now}
        result = await db.get_last_post_time()
        assert result == now

    @pytest.mark.asyncio
    async def test_returns_now_when_empty(self, mock_db_pool):
        _, mock_conn = mock_db_pool
        db = _get_db()
        mock_conn.fetchrow.return_value = None
        result = await db.get_last_post_time()
        assert isinstance(result, datetime)
