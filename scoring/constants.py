import re

HIGH_AROUSAL_POSITIVE = [
    'amazing', 'incredible', 'mind-blowing', 'breakthrough', 'revolutionary',
    'game-changing', 'epic', 'stunning', 'phenomenal', 'extraordinary',
    'thrilling', 'exhilarating', 'electrifying', 'magical', 'spectacular',
    'удивительно', 'невероятно', 'прорыв', 'революция', 'эпический',
    ' потрясающ', 'восхитительн', 'великолепн', 'грандиозн', 'сногсшибательн',
    'class', 'супер', 'отлично', 'класс', 'топ',
]

HIGH_AROUSAL_NEGATIVE = [
    'outrageous', 'shocking', 'terrifying', 'horrifying', 'catastrophic',
    'crisis', 'emergency', 'disaster', 'urgent', 'critical',
    'scam', 'fraud', 'danger', 'warning', 'panic',
    'ужасно', 'шокирующе', 'катастроф', 'кризис', 'авария',
    'опасно', 'срочно', 'критическ', 'угроза', 'паник',
    'скам', 'мошенничеств', 'обман', 'угроза', 'тревог',
]

LOW_AROUSAL_NEGATIVE = [
    'sad', 'boring', 'dull', 'tedious', 'predictable', 'ordinary',
    'gloomy', 'depressing', 'monotonous', 'repetitive',
    'грустн', 'скучн', 'тосклив', 'пресн', 'монотонн',
    'повторяющ', 'предсказуем', 'обыденн', 'банальн',
]

EMOTION_MAP = {
    'high_pos': HIGH_AROUSAL_POSITIVE,
    'high_neg': HIGH_AROUSAL_NEGATIVE,
    'low_neg': LOW_AROUSAL_NEGATIVE,
}

WEIGHTS = {
    'emotion': 0.30,
    'usefulness': 0.25,
    'visual': 0.15,
    'readability': 0.15,
    'interactivity': 0.08,
    'personalization': 0.05,
    'structure': 0.02,
}

TELEGRAM_TIMING = {
    'optimal_hours': [4, 12, 15],
    'peak': {7: 0.8, 8: 0.8, 9: 0.8, 11: 0.9, 12: 1.0, 13: 1.0, 14: 0.9,
             15: 0.95, 16: 0.9, 17: 0.9, 19: 0.7, 20: 0.7, 21: 0.7, 22: 0.6},
    'avoid': {1: 0.5, 2: 0.5, 3: 0.5, 5: 0.5, 6: 0.6},
}

ANTI_PATTERNS = {
    'sadness_heavy': {
        'description': 'Текст перегружен грустью',
        'penalty': -0.16,
        'check': lambda t: sum(1 for w in t.lower().split() if any(k in w for k in LOW_AROUSAL_NEGATIVE)) > 3
    },
    'long_sentences': {
        'description': 'Предложения длиннее 21 слова',
        'penalty': -0.10,
        'check': lambda t: any(len(s.split()) > 21 for s in re.split(r'[.!?]+', t) if s.strip())
    },
    'wall_of_text': {
        'description': 'Сплошной текст без абзацев',
        'penalty': -0.15,
        'check': lambda t: '\n\n' not in t and len(t.split()) > 100
    },
    'no_visuals': {
        'description': 'Текст без изображений',
        'penalty': -0.15,
        'check': lambda t, m=0: m == 0
    },
    'complaint_no_solution': {
        'description': 'Жалоба без решения',
        'penalty': -0.20,
        'check': lambda t: 'проблема' in t.lower() and not any(w in t.lower() for w in ['решение', 'совет', 'как исправить', 'вот как'])
    },
}

AI_KEYWORDS = {
    'ai', 'llm', 'gpt', 'chatgpt', 'openai', 'anthropic', 'claude',
    'gemini', 'midjourney', 'stable', 'diffusion', 'transformer',
    'neural', 'model', 'prompt', 'agent', 'copilot', 'cursor',
    'deepseek', 'machine', 'learning', 'deep', 'rag', 'embedding',
    'fine-tun', 'finetun', 'inference', 'token', 'context',
    'нейросет', 'промпт', 'искусственн', 'модел', 'обучен',
    'машинн', 'генерац', 'генерат', 'ассистент', 'чат-бот',
    'автоматизац', 'робот', 'алгоритм', 'обработк', 'язык'
}

LOW_VALUE_PATTERNS = re.compile(
    r'tutorial|beginner|101|getting started|basics|how to use|step by step|'
    r'introduction to|learn.*in.*minutes|for dummies|cheatsheet|cheat sheet',
    re.IGNORECASE
)

CHUNK_SIZE = 25

SCORING_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "scoring_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "source": {"type": "string"},
                            "link": {"type": "string"},
                            "category": {"type": "string"},
                            "score_b2c": {"type": "integer"},
                            "score_utility": {"type": "integer"},
                            "score_savability": {"type": "integer"},
                            "score_repostability": {"type": "integer"},
                            "score_practical": {"type": "integer"},
                            "total_score": {"type": "integer"},
                            "raw_description": {"type": "string"}
                        },
                        "required": ["title", "category", "total_score", "raw_description",
                                      "source", "link", "score_b2c", "score_utility",
                                      "score_savability", "score_repostability", "score_practical"]
                    }
                }
            },
            "required": ["items"]
        }
    }
}
