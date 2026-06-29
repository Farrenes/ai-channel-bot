import re
import math
from typing import Dict, List, Optional
from scoring.constants import HIGH_AROUSAL_POSITIVE, HIGH_AROUSAL_NEGATIVE, LOW_AROUSAL_NEGATIVE, EMOTION_MAP, WEIGHTS, TELEGRAM_TIMING, ANTI_PATTERNS


def count_syllables_russian(text: str) -> int:
    vowels = set('аеёиоуыэюя')
    return sum(1 for char in text.lower() if char in vowels)


def calculate_fre_russian(text: str) -> float:
    sentences = re.split(r'[.!?]+', text)
    sentences = [s for s in sentences if s.strip()]
    words = text.split()
    syllables = count_syllables_russian(text)
    if not sentences or not words:
        return 0.0
    asl = len(words) / len(sentences)
    asw = syllables / len(words)
    fre = 206.835 - 1.3 * asl - 60.1 * asw
    return max(0.0, min(100.0, fre))


def calculate_fkgl_russian(text: str) -> float:
    sentences = re.split(r'[.!?]+', text)
    sentences = [s for s in sentences if s.strip()]
    words = text.split()
    syllables = count_syllables_russian(text)
    if not sentences or not words:
        return 20.0
    asl = len(words) / len(sentences)
    asw = syllables / len(words)
    fkgl = 0.39 * asl + 11.8 * asw - 15.59
    return max(6.0, min(20.0, fkgl))


def calculate_solovsky(text: str) -> float:
    words = text.split()
    sentences = re.split(r'[.!?]+', text)
    sentences = [s for s in sentences if s.strip()]
    if not sentences or not words:
        return 100.0
    complex_words = sum(1 for w in words if len(w) > 6)
    solovsky = (len(words) / len(sentences)) + (complex_words / len(words) * 100)
    return max(0.0, min(100.0, solovsky))


def calculate_rsbi(text: str) -> float:
    words = text.split()
    sentences = re.split(r'[.!?]+', text)
    sentences = [s for s in sentences if s.strip()]
    if not sentences or not words:
        return 10.0
    asl = len(words) / len(sentences)
    complex_words = sum(1 for w in words if len(w) > 6)
    pct_complex = (complex_words / len(words) * 100)
    rsbi = 0.5 * asl + 0.1 * pct_complex
    return max(0.0, min(10.0, rsbi))


def validate_readability(text: str) -> Dict:
    sentences = re.split(r'[.!?]+', text)
    sentences = [s for s in sentences if s.strip()]
    words = text.split()
    long_sentences = [s for s in sentences if len(s.split()) > 21]
    passive_words = ['был', 'была', 'было', 'были', 'быть', 'является', 'являются']
    passive_count = sum(1 for w in words if w.lower() in passive_words)
    passive_ratio = passive_count / len(words) * 100 if words else 0
    return {
        'fre': calculate_fre_russian(text),
        'fkgl': calculate_fkgl_russian(text),
        'solovsky': calculate_solovsky(text),
        'rsbi': calculate_rsbi(text),
        'sentence_count': len(sentences),
        'word_count': len(words),
        'long_sentences_count': len(long_sentences),
        'passive_ratio': passive_ratio,
        'is_valid': len(long_sentences) == 0 and passive_ratio < 5.0 and calculate_fre_russian(text) >= 30.0
    }


def score_emotion(text: str) -> float:
    text_lower = text.lower()
    words = text_lower.split()
    high_pos = sum(1 for w in words if any(kw in w for kw in HIGH_AROUSAL_POSITIVE))
    high_neg = sum(1 for w in words if any(kw in w for kw in HIGH_AROUSAL_NEGATIVE))
    low_neg = sum(1 for w in words if any(kw in w for kw in LOW_AROUSAL_NEGATIVE))
    excl = text.count('!')
    caps = len(re.findall(r'\b[A-ZА-ЯЁ]{2,}\b', text))
    question_marks = text.count('?')
    arousal = min(1.0, (high_pos * 0.3 + high_neg * 0.25 + excl * 0.15 + caps * 0.2 + question_marks * 0.1))
    if low_neg > 2:
        arousal *= 0.84
    return max(0.0, min(1.0, arousal))


def score_usefulness(text: str) -> float:
    text_lower = text.lower()
    indicators = [
        'как ', 'совет', 'рекомендация', 'попробуй', 'сделай', 'пошагово',
        'инструкция', 'guide', 'tutorial', 'how to', 'lifehack', 'лайфхак',
        'простой способ', 'эффективн', 'результат', 'польз', 'помога',
    ]
    count = sum(1 for ind in indicators if ind in text_lower)
    personal = ['я заметил', 'мой опыт', 'лично', 'у меня было', 'я попробовал', 'я тестировал']
    personal_count = sum(1 for p in personal if p in text_lower)
    return max(0.0, min(1.0, 0.3 + count * 0.1 + personal_count * 0.15))


def score_visual(has_image: bool, has_video: bool, media_count: int) -> float:
    score = 0.0
    if has_video:
        score += 0.5
    elif has_image:
        score += 0.3
    if media_count >= 2:
        score += 0.2
    return min(1.0, score)


def score_readability(text: str) -> float:
    metrics = validate_readability(text)
    fre_score = min(metrics['fre'], 100) / 100
    fkgl_score = 1 - min(metrics['fkgl'], 20) / 20
    solovsky_score = 1 - min(metrics['solovsky'], 100) / 100
    rsbi_score = 1 - min(metrics['rsbi'], 10) / 10
    return max(0.0, min(1.0, (fre_score + fkgl_score + solovsky_score + rsbi_score) / 4))


def score_interactivity(text: str) -> float:
    text_lower = text.lower()
    indicators = ['?', 'напишите', 'поделитесь', 'мнение', 'голосование', 'опрос',
                  'лайк', 'репост', 'комментар', 'подпиш', 'сохран']
    count = sum(1 for ind in indicators if ind in text_lower)
    return max(0.0, min(1.0, 0.2 + count * 0.15))


def score_personalization(text: str, audience: str = '18-34') -> float:
    text_lower = text.lower()
    personal = ['я ', 'мой', 'мне', 'лично', 'мой опыт', 'заметил']
    count = sum(1 for p in personal if p in text_lower)
    return max(0.0, min(1.0, 0.3 + count * 0.12))


def score_structure(text: str, media_count: int) -> float:
    words = text.split()
    word_count = len(words)
    optimal_length = 50 <= word_count <= 1500
    paragraphs = text.split('\n\n')
    good_paragraphs = all(len(p.split()) <= 50 for p in paragraphs if p.strip())
    hook = ' '.join(words[:3]) if words else ''
    has_hook = len(hook) > 0
    score = 0.0
    if optimal_length:
        score += 0.4
    if good_paragraphs:
        score += 0.3
    if has_hook:
        score += 0.3
    return min(1.0, score)


def calculate_timing_score(hour: int) -> float:
    if hour in TELEGRAM_TIMING['optimal_hours']:
        return 1.3
    if hour in TELEGRAM_TIMING['peak']:
        return TELEGRAM_TIMING['peak'][hour]
    if hour in TELEGRAM_TIMING['avoid']:
        return TELEGRAM_TIMING['avoid'][hour]
    return 0.8


def calculate_telegram_coefficient(word_count: int) -> float:
    if word_count >= 300:
        return 1.371
    elif word_count >= 150:
        return 1.1
    return 1.0


ANTI_PATTERNS['passive_overuse'] = {
    'description': 'Пассивный залог > 5%',
    'penalty': -0.08,
    'check': lambda t: validate_readability(t)['passive_ratio'] > 5.0
}


def check_anti_patterns(text: str, media_count: int = 0) -> Dict:
    penalties = []
    total_penalty = 0.0
    for name, pattern in ANTI_PATTERNS.items():
        if name == 'no_visuals':
            triggered = pattern['check'](text, media_count)
        else:
            triggered = pattern['check'](text)
        if triggered:
            penalties.append({'pattern': name, 'description': pattern['description'], 'penalty': pattern['penalty']})
            total_penalty += pattern['penalty']
    return {
        'total_penalty': max(total_penalty, -0.9),
        'penalties': penalties,
        'is_clean': len(penalties) == 0,
    }


def score_telegram_content(
    text: str,
    media_count: int = 0,
    has_video: bool = False,
    publish_hour: int = 12,
) -> Dict:
    scores = {
        'emotion': score_emotion(text),
        'usefulness': score_usefulness(text),
        'visual': score_visual(media_count > 0, has_video, media_count),
        'readability': score_readability(text),
        'interactivity': score_interactivity(text),
        'personalization': score_personalization(text),
        'structure': score_structure(text, media_count),
    }

    base_score = sum(WEIGHTS[k] * scores[k] for k in WEIGHTS)
    words = text.split()
    K_telegram = calculate_telegram_coefficient(len(words))
    K_timing = calculate_timing_score(publish_hour)
    anti_patterns = check_anti_patterns(text, media_count)
    final_score = base_score * K_telegram * K_timing + anti_patterns['total_penalty']
    final_score = max(0.0, min(1.0, final_score))
    score_100 = final_score * 100

    grade = (
        'A+' if score_100 >= 85 else
        'A' if score_100 >= 75 else
        'B+' if score_100 >= 65 else
        'B' if score_100 >= 55 else
        'C+' if score_100 >= 45 else
        'C' if score_100 >= 35 else 'D'
    )

    recommendations = []
    if scores['emotion'] < 0.5:
        recommendations.append('Усилите эмоциональный крючок (гнев +34%, тревога +21%)')
    if scores['usefulness'] < 0.5:
        recommendations.append('Добавьте практический совет (77.6% предпочитают полезный контент)')
    if scores['visual'] < 0.3:
        recommendations.append('Добавьте изображение/видео (+20-50% engagement)')
    if scores['readability'] < 0.5:
        recommendations.append('Упростите текст: предложения ≤21 слово, пассив <5%')
    if not anti_patterns['is_clean']:
        for ap in anti_patterns['penalties']:
            recommendations.append(f"Исправьте: {ap['description']}")

    return {
        'final_score': round(score_100, 1),
        'grade': grade,
        'factors': {k: round(v * 100, 1) for k, v in scores.items()},
        'coefficients': {'K_telegram': round(K_telegram, 3), 'K_timing': round(K_timing, 3)},
        'anti_patterns': anti_patterns,
        'readability': validate_readability(text),
        'recommendations': recommendations,
    }


if __name__ == '__main__':
    examples = [
        ("Совет", "Вы замечали как уходит время в телефоне? Я заметил 3 правила: 1.Таймер 30мин 2.Выкл уведомления 3.Прогулка. Попробуйте и напишите!", 2, 12),
        ("Гнев", "ШОК! Новая угроза для данных! Кибератаки выросли на 34%. Мошенники используют новые схемы. Срочно проверьте настройки безопасности!", 1, 15),
        ("Новость", "OpenAI выпустила GPT-5. Точность выросла на 15%. Доступна для подписчиков ChatGPT Plus.", 0, 10),
        ("Story", "Однажды я потерял 50к подписчиков за день. Причина - сухие факты без эмоций. Добавил личные истории и вопросы. Через месяц +20к новых.", 3, 20),
        ("Прода", "СКИДКА 50% ТОЛЬКО СЕГОДНЯ! Курс по Python для начинающих. 40 видеоуроков и сертификат. Успейте купить!", 1, 12),
    ]
    for name, text, media, hour in examples:
        r = score_telegram_content(text, media_count=media, publish_hour=hour)
        print(f"=== {name} ===")
        print(f"  Score: {r['final_score']}/100 ({r['grade']})")
        for f, s in r['factors'].items():
            bar = "#" * int(s / 10)
            print(f"  {f:18s}: {s:5.1f} {bar}")
        if r['recommendations']:
            for rec in r['recommendations']:
                print(f"  -> {rec}")
        print()
