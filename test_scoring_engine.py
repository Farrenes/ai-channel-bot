import pytest
from scoring.engine import (
    count_syllables_russian, calculate_fre_russian, calculate_fkgl_russian,
    calculate_solovsky, calculate_rsbi, validate_readability,
    score_emotion, score_usefulness, score_visual, score_readability,
    score_interactivity, score_personalization, score_structure,
    calculate_timing_score, calculate_telegram_coefficient,
    check_anti_patterns, score_telegram_content,
)
from scoring.constants import WEIGHTS


class TestRussianReadability:
    def test_count_syllables(self):
        assert count_syllables_russian('привет') == 2
        assert count_syllables_russian('мир') == 1
        assert count_syllables_russian('а') == 1
        assert count_syllables_russian('') == 0

    def test_fre_russian_simple(self):
        text = 'Кот сидит на столе. Кот спит.'
        fre = calculate_fre_russian(text)
        assert 0 <= fre <= 100

    def test_fre_russian_empty(self):
        assert calculate_fre_russian('') == 0.0

    def test_fkgl_russian(self):
        text = 'Это простой текст для проверки.'
        fkgl = calculate_fkgl_russian(text)
        assert 6.0 <= fkgl <= 20.0

    def test_solovsky(self):
        text = 'Абстрактные концепции детерминизма определяют парадигму.'
        sol = calculate_solovsky(text)
        assert 0 <= sol <= 100

    def test_rsbi(self):
        text = 'Простой текст для проверки индекса.'
        rsbi = calculate_rsbi(text)
        assert 0 <= rsbi <= 10

    def test_validate_readability(self):
        text = 'Короткий текст. Второе предложение.'
        result = validate_readability(text)
        assert 'fre' in result
        assert 'fkgl' in result
        assert 'is_valid' in result
        assert isinstance(result['is_valid'], bool)


class TestEmotionScoring:
    def test_positive_emotion(self):
        text = 'Невероятный прорыв! Потрясающий результат!'
        score = score_emotion(text)
        assert score > 0.3

    def test_negative_emotion(self):
        text = 'Ужасная катастрофа! Тревога и паника!'
        score = score_emotion(text)
        assert score > 0.3

    def test_sadness_penalty(self):
        text = 'Грустная новость. Тоска и печаль.'
        score = score_emotion(text)
        assert score < 0.3

    def test_neutral_text(self):
        text = 'Обычный текст без ярких эмоций.'
        score = score_emotion(text)
        assert 0.0 <= score <= 1.0


class TestUsefulnessScoring:
    def test_useful_content(self):
        text = 'Совет: попробуйте этот простой способ. Как сделать за 5 шагов.'
        score = score_usefulness(text)
        assert score > 0.5

    def test_personal_experience(self):
        text = 'Я заметил что это работает. Мой опыт показал результат.'
        score = score_usefulness(text)
        assert score > 0.5

    def test_not_useful(self):
        text = 'Просто информация без советов.'
        score = score_usefulness(text)
        assert score < 0.5


class TestVisualScoring:
    def test_video(self):
        assert score_visual(False, True, 1) >= 0.5

    def test_image(self):
        assert score_visual(True, False, 1) >= 0.3

    def test_no_media(self):
        assert score_visual(False, False, 0) == 0.0

    def test_multiple_media(self):
        assert score_visual(True, False, 3) > score_visual(True, False, 1)


class TestInteractivityScoring:
    def test_interactive(self):
        text = 'Напишите в комментариях! Как вам? Поделитесь мнением!'
        score = score_interactivity(text)
        assert score > 0.5

    def test_not_interactive(self):
        text = 'Простой текст без вопросов.'
        score = score_interactivity(text)
        assert score < 0.5


class TestTimingScore:
    def test_optimal_hours(self):
        assert calculate_timing_score(12) == 1.3
        assert calculate_timing_score(15) == 1.3

    def test_peak_hours(self):
        assert calculate_timing_score(8) == 0.8
        assert calculate_timing_score(17) == 0.9

    def test_avoid_hours(self):
        assert calculate_timing_score(2) == 0.5


class TestTelegramCoefficient:
    def test_long_read(self):
        assert calculate_telegram_coefficient(500) == 1.371

    def test_medium(self):
        assert calculate_telegram_coefficient(200) == 1.1

    def test_short(self):
        assert calculate_telegram_coefficient(50) == 1.0


class TestAntiPatterns:
    def test_clean_text(self):
        text = 'Отличный совет! Попробуйте это.'
        result = check_anti_patterns(text, media_count=1)
        assert result['is_clean']

    def test_wall_of_text(self):
        text = ' '.join(['слово'] * 150)
        result = check_anti_patterns(text)
        assert not result['is_clean']

    def test_penalty_limit(self):
        text = 'Грустная ужасная проблема без решения. ' * 10
        result = check_anti_patterns(text)
        assert result['total_penalty'] >= -0.9


class TestFullScoring:
    def test_score_content(self):
        text = 'Отличный совет! Попробуйте этот способ.'
        result = score_telegram_content(text, media_count=1, publish_hour=12)
        assert 'final_score' in result
        assert 'grade' in result
        assert 'factors' in result
        assert 0 <= result['final_score'] <= 100

    def test_score_weights_sum(self):
        assert abs(sum(WEIGHTS.values()) - 1.0) < 0.001

    def test_grade_mapping(self):
        result = score_telegram_content('Текст', publish_hour=12)
        assert result['grade'] in ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D']
