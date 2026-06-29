# Psychological Engagement Scoring System for Telegram Content Bot

## Overview

A CPU-based, universal scoring system that evaluates any content for engagement potential using established psychological research. Produces a 0–100 composite score with four tiers: reject, consider, promote, featured.

---

## 1. PSYCHOLOGICAL ENGAGEMENT FACTORS

### 1.1 Curiosity Gap (Weight: 5/5)

- **Scientific Name**: Information Gap Theory
- **Source**: Loewenstein, G. (1994), "The Psychology of Curiosity," *Psychological Bulletin*
- **Description**: The gap between what we know and what we want to know creates an aversive state that motivates information-seeking behavior.
- **How it drives engagement**: Creates intrinsic motivation to consume the full piece to "close the gap." Users feel compelled to read further, click, or follow.
- **CPU-detectable signals**:
  - Questions in content
  - Incomplete information patterns
  - "How to" phrases
  - Mystery/悬念 markers
- **Detection algorithm**:
```python
def detect_curiosity_gap(text):
    score = 0
    question_marks = text.count('?')
    score += min(question_marks * 2, 10)  # Cap at 10
    
    # Incomplete info patterns
    incomplete_patterns = [
        r'you won\'t believe',
        r'what happens next',
        r'the secret',
        r'hidden',
        r'the truth about',
        r'nobody tells you',
        r'what they don\'t want you to know',
        r'most people don\'t realize',
        r'you probably didn\'t know',
    ]
    for pattern in incomplete_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            score += 3
    
    # How-to / tutorial signals
    how_to_patterns = [r'how to', r'step[s]?:', r'guide', r'tutorial', r'walkthrough']
    for pattern in how_to_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            score += 2
    
    return min(score, 50)
```

---

### 1.2 Emotional Arousal (Weight: 5/5)

- **Scientific Name**: Emotional Contagion Theory
- **Source**: Hatfield, E., Cacioppo, J.T., & Rapson, R.L. (1994), *Emotional Contagion*; Berger & Milkman (2012), "What Makes Online Content Viral?" *Journal of Marketing Research*
- **Description**: High-arousal emotions (awe, anxiety, amusement, anger) drive sharing behavior more than low-arousal emotions (sadness, contentment).
- **How it drives engagement**: Arousal triggers physiological activation that increases sharing, commenting, and return visits.
- **CPU-detectable signals**:
  - Emotion-laden words from lexicons
  - Exclamation marks
  - ALL CAPS words
  - Emoji density
- **Detection algorithm**:
```python
def detect_emotional_arousal(text):
    score = 0
    words = text.lower().split()
    total_words = len(words)
    
    # High-arousal positive words
    high_pos = ['amazing', 'incredible', 'unbelievable', 'awesome', 'game-changing',
                'revolutionary', 'mind-blowing', 'breakthrough', 'stunning', 'epic',
                'phenomenal', 'extraordinary', 'powerful', 'brilliant', 'fantastic',
                'miracle', 'jaw-dropping', 'awe-inspiring', 'spectacular', 'magical',
                'thrilling', 'exhilarating', 'electrifying', 'unreal', 'legendary']
    
    # High-arousal negative words
    high_neg = ['outrageous', 'shocking', 'disgusting', 'terrifying', 'horrifying',
                'devastating', 'catastrophic', 'disaster', 'crisis', 'emergency',
                'banned', 'illegal', 'scam', 'fraud', 'danger', 'warning', 'urgent',
                'alert', 'panic', 'rage', 'furious', 'livid', 'infuriated']
    
    pos_count = sum(1 for w in words if w in high_pos)
    neg_count = sum(1 for w in words if w in high_neg)
    
    score += min((pos_count + neg_count) * 5, 30)
    
    # Exclamation density
    exclamations = text.count('!')
    score += min(exclamations * 2, 15)
    
    # ALL CAPS words (not at start of sentence)
    caps_words = len(re.findall(r'\b[A-Z]{2,}\b', text))
    score += min(caps_words * 3, 20)
    
    # Emoji density
    emoji_count = len(re.findall(r'[\U0001F600-\U0001F9FF]', text))
    score += min(emoji_count * 3, 15)
    
    return min(score, 50)
```

---

### 1.3 Social Proof (Weight: 4/5)

- **Scientific Name**: Social Proof Principle
- **Source**: Cialdini, R.B. (2006), *Influence: The Psychology of Persuasion*
- **Description**: People follow the actions of others, especially when uncertain.
- **How it drives engagement**: Signals that others have validated the content make users more likely to engage.
- **CPU-detectable signals**:
  - Numbers of users/downloads/views
  - Citations of studies or data
  - Expert endorsements
  - Community metrics
- **Detection algorithm**:
```python
def detect_social_proof(text):
    score = 0
    
    # Numerical social proof
    numbers = re.findall(r'(\d[\d,\.]*\s*(?:million|M|billion|B|thousand|K)?)', text)
    score += min(len(numbers) * 3, 15)
    
    # Study/research citations
    research_patterns = [r'study (?:shows|found|reveals)', r'research (?:shows|found|confirms)',
                        r'according to', r'data (?:shows|suggests|indicates)',
                        r'survey (?:found|revealed)', r'stats? (?:show|reveal)']
    for pattern in research_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            score += 5
    
    # User metrics
    metric_patterns = [r'\d+\s*(?:users|downloads|subscribers|followers|views|likes)',
                       r'(?:million|thousand|billion)\s+(?:of\s+)?(?:users|people)']
    for pattern in metric_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            score += 5
    
    return min(score, 50)
```

---

### 1.4 Practical Value (Weight: 4/5)

- **Scientific Name**: Utility Value / Practical Value
- **Source**: Berger, J. (2013), *Contagious: Why Things Catch On*; Hovland, Janis, & Kelley (1953), Communication Research
- **Description**: Content that is useful, actionable, or solves a problem is shared more often.
- **How it drives engagement**: Users share useful content to help others and build social capital.
- **CPU-detectable signals**:
  - Action verbs
  - Numbered lists
  - Step-by-step instructions
  - Tool recommendations
  - Problem-solution structure
- **Detection algorithm**:
```python
def detect_practical_value(text):
    score = 0
    
    # Action-oriented language
    action_verbs = ['learn', 'build', 'create', 'start', 'use', 'try', 'get',
                    'install', 'setup', 'configure', 'deploy', 'launch', 'improve',
                    'optimize', 'master', 'unlock', 'boost', 'enhance', 'automate']
    text_lower = text.lower()
    score += min(sum(3 for v in action_verbs if v in text_lower), 20)
    
    # Numbered steps
    steps = re.findall(r'(?:^|\n)\s*\d+[\.\)]\s+', text)
    score += min(len(steps) * 4, 16)
    
    # Checklist/bullet patterns
    bullets = re.findall(r'[•\-\*]\s+', text)
    score += min(len(bullets) * 2, 10)
    
    # Problem-solution markers
    if re.search(r'(?:how to|step[s]:?|guide|tutorial|tip[s]?:?)', text_lower):
        score += 5
    
    return min(score, 50)
```

---

### 1.5 Narrative Structure (Weight: 4/5)

- **Scientific Name**: Narrative Transportation Theory
- **Source**: Green, M.C. & Brock, T.C. (2000), "The Role of Transportation in the Persuasiveness of Public Narratives," *Journal of Personality and Social Psychology*
- **Description**: Story-driven content creates "transportation" — a psychological state where readers are immersed, reducing counter-argument and increasing persuasion.
- **How it drives engagement**: Stories activate empathy, memory encoding, and emotional resonance.
- **CPU-detectable signals**:
  - Character names (proper nouns)
  - Past-tense narrative markers
  - Dialogue quotes
  - Scene-setting language
  - Transition words (then, finally, after)
- **Detection algorithm**:
```python
def detect_narrative_structure(text):
    score = 0
    
    # Dialogue/quotes
    quotes = re.findall(r'["""](.+?)["""]', text)
    score += min(len(quotes) * 5, 15)
    
    # Past tense narrative markers
    past_markers = ['was', 'were', 'had', 'did', 'went', 'said', 'told',
                    'began', 'started', 'finally', 'suddenly', 'eventually']
    text_lower = text.lower()
    score += min(sum(2 for m in past_markers if m in text_lower.split()), 12)
    
    # Temporal transitions
    transitions = ['then', 'after', 'before', 'meanwhile', 'eventually',
                   'suddenly', 'finally', 'next', 'first', 'last']
    score += min(sum(2 for t in transitions if t in text_lower.split()), 10)
    
    # Character/proper nouns (approximate)
    proper_nouns = len(re.findall(r'\b[A-Z][a-z]+\b', text))
    score += min(proper_nouns * 2, 10)
    
    # Paragraph structure (multiple short paragraphs = good)
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    if 3 <= len(paragraphs) <= 20:
        score += 5
    
    return min(score, 50)
```

---

### 1.6 Authority & Expertise (Weight: 3/5)

- **Scientific Name**: Authority Principle
- **Source**: Cialdini, R.B. (2006), *Influence*
- **Description**: People defer to experts and credible sources.
- **How it drives engagement**: Authority markers increase trust and willingness to engage/share.
- **CPU-detectable signals**:
  - Source citations
  - Expert titles
  - Company/brand names
  - Technical terminology
  - Statistics with sources
- **Detection algorithm**:
```python
def detect_authority(text):
    score = 0
    
    # Source citations
    source_patterns = [r'according to', r'source[s]?:', r'reference[s]?:',
                       r'(?:study|paper|report)\s+(?:by|from)',
                       r'(?:published|released)\s+(?:by|in)']
    for pattern in source_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            score += 5
    
    # Expert/authority titles
    authority_patterns = [r'(?:dr|professor|prof|researcher|scientist|expert|analyst)',
                          r'(?:ceo|cto|founder|director|lead|head of)',
                          r'(?:phd|m\.?d\.?|mba|professor)']
    for pattern in authority_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            score += 4
    
    # Technical terminology (general pattern)
    technical_words = re.findall(r'\b[A-Za-z]+(?:tion|ment|ance|ence|ity|ism|ology|ics)\b', text)
    score += min(len(technical_words) * 1, 10)
    
    # Numbers with precision
    precise_numbers = re.findall(r'\b\d+\.?\d*\s*%', text)
    score += min(len(precise_numbers) * 3, 10)
    
    return min(score, 50)
```

---

### 1.7 Identity & Self-Expression (Weight: 3/5)

- **Scientific Name**: Self-Expression / Identity Signaling
- **Source**: Berger, J. (2013), *Contagious*; Belk, R.W. (1988), "Possessions and the Extended Self"
- **Description**: People share content that reflects how they want to be perceived by others.
- **How it drives engagement**: Content that aligns with group identity or aspirational self drives sharing.
- **CPU-detectable signals**:
  - "If you're a..." identity framing
  - Group membership references
  - Aspirational language
  - Lifestyle markers
- **Detection algorithm**:
```python
def detect_identity_signal(text):
    score = 0
    text_lower = text.lower()
    
    # Identity framing
    identity_patterns = [r'if you\'re (?:a|an|into|into)',
                        r'(?:real|true|serious)\s+(?:dev|programmer|marketer|entrepreneur)',
                        r'(?:every|all)\s+(?:good|smart|serious)',
                        r'(?:must|need to)\s+(?:know|have|try|use)']
    for pattern in identity_patterns:
        if re.search(pattern, text_lower):
            score += 5
    
    # Community/belonging signals
    community_words = ['community', 'together', 'join', 'movement', 'tribe',
                       'family', 'fellow', 'like-minded', 'peers']
    score += min(sum(2 for w in community_words if w in text_lower), 10)
    
    return min(score, 50)
```

---

### 1.8 Scarcity & Urgency (Weight: 2/5)

- **Scientific Name**: Scarcity Principle / Fear of Missing Out (FOMO)
- **Source**: Cialdini, R.B. (2006), *Influence*; Przybylski et al. (2013), "Motivational, Emotional, and Behavioral FOMO," *Computers in Human Behavior*
- **Description**: Limited availability increases perceived value.
- **How it drives engagement**: Creates urgency to act now rather than later.
- **CPU-detectable signals**:
  - Time-limited language
  - "Limited" / "exclusive" / "only" markers
  - FOMO triggers
- **Detection algorithm**:
```python
def detect_scarcity_urgency(text):
    score = 0
    text_lower = text.lower()
    
    urgency_words = ['limited', 'exclusive', 'only', 'last chance', 'hurry',
                     'ending soon', 'running out', 'deadline', 'expires',
                     'free today', 'while supplies last', 'don\'t miss',
                     'before it\'s gone', 'act now']
    score += min(sum(4 for w in urgency_words if w in text_lower), 30)
    
    # Time references
    time_patterns = [r'(?:today|tonight|this week|right now|immediately)']
    for pattern in time_patterns:
        if re.search(pattern, text_lower):
            score += 3
    
    return min(score, 50)
```

---

## 2. EMOTIONAL LEXICONS BY CATEGORY

### 2.1 High-Arousal Positive (Excitement, Awe, Curiosity)

```python
HIGH_AROUSAL_POSITIVE = [
    # Awe / Wonder
    'amazing', 'incredible', 'unbelievable', 'mind-blowing', 'jaw-dropping',
    'breathtaking', 'awe-inspiring', 'phenomenal', 'miraculous', 'magical',
    'unreal', 'surreal', 'otherworldly', 'cosmic', 'divine',
    
    # Excitement
    'exciting', 'thrilling', 'electrifying', 'exhilarating', 'revolutionary',
    'game-changing', 'groundbreaking', 'breakthrough', 'transformative', 'epic',
    'legendary', 'iconic', 'masterpiece', 'masterful', 'brilliant',
    
    # Curiosity
    'secret', 'hidden', 'mystery', 'puzzle', 'enigma',
    'fascinating', 'intriguing', 'captivating', 'mesmerizing', 'riveting',
    'compelling', 'enthralling', 'absorbing', 'gripping', 'addictive',
    
    # Delight
    'delightful', 'joyful', 'wonderful', 'fantastic', 'superb',
    'outstanding', 'remarkable', 'exceptional', 'magnificent', 'splendid',
    
    # Motivation
    'inspiring', 'empowering', 'uplifting', 'motivating', 'energizing',
    'invigorating', 'stimulating', 'catalytic', 'unstoppable', 'limitless',
    
    # Achievement
    'success', 'triumph', 'victory', 'milestone', 'achievement',
    'accomplishment', 'breakthrough', 'winning', 'triumphant', 'flourishing',
]
```

### 2.2 High-Arousal Negative (Anger, Fear, Outrage)

```python
HIGH_AROUSAL_NEGATIVE = [
    # Anger / Outrage
    'outrageous', 'disgusting', 'infuriating', 'maddening', 'scandalous',
    'shameful', 'unacceptable', 'horrifying', 'appalling', 'disgraceful',
    'furious', 'livid', 'enraged', 'incensed', 'aggrieved',
    
    # Fear / Alarm
    'terrifying', 'frightening', 'alarming', 'threatening', 'menacing',
    'dangerous', 'risky', 'hazardous', 'perilous', 'vulnerable',
    'catastrophic', 'disastrous', 'devastating', 'ruinous', 'destructive',
    
    # Urgency / Crisis
    'crisis', 'emergency', 'disaster', 'catastrophe', 'emergency',
    'urgent', 'critical', 'dire', 'desperate', 'severe',
    
    # Suspicion
    'scam', 'fraud', 'fake', 'hoax', 'conspiracy',
    'deception', 'manipulation', 'exploitation', 'abuse', 'corruption',
    
    # Controversy
    'controversial', 'debated', 'divisive', 'polarizing', 'contentious',
    'disputed', 'challenged', 'provocative', 'radical', 'extreme',
]
```

### 2.3 Low-Arousal Positive (Calm, Trust, Satisfaction)

```python
LOW_AROUSAL_POSITIVE = [
    # Trust
    'reliable', 'trustworthy', 'dependable', 'consistent', 'proven',
    'verified', 'validated', 'certified', 'endorsed', 'recommended',
    
    # Calm / Peace
    'calm', 'peaceful', 'serene', 'tranquil', 'harmonious',
    'balanced', 'stable', 'steady', 'smooth', 'effortless',
    
    # Satisfaction
    'satisfied', 'pleased', 'content', 'grateful', 'appreciative',
    'fulfilled', 'complete', 'whole', 'wholehearted', 'genuine',
    
    # Comfort
    'comfortable', 'cozy', 'welcoming', 'inviting', 'nurturing',
    'supportive', 'caring', 'gentle', 'soft', 'tender',
    
    # Clarity
    'clear', 'simple', 'straightforward', 'transparent', 'honest',
    'obvious', 'evident', 'apparent', 'manifest', 'self-evident',
]
```

### 2.4 Low-Arousal Negative (Sadness, Boredom, Doubt)

```python
LOW_AROUSAL_NEGATIVE = [
    # Sadness
    'sad', 'unfortunate', 'regrettable', 'tragic', 'melancholy',
    'somber', 'gloomy', 'depressing', 'heartbreaking', 'sorrowful',
    
    # Boredom
    'boring', 'dull', 'tedious', 'monotonous', 'repetitive',
    'predictable', 'ordinary', 'mundane', 'unremarkable', 'generic',
    
    # Doubt
    'uncertain', 'unsure', 'doubtful', 'questionable', 'debatable',
    'speculative', 'unproven', 'unverified', 'theoretical', 'hypothetical',
    
    # Fatigue
    'tired', 'exhausted', 'overwhelmed', 'burned out', 'drained',
    'fatigued', 'weary', 'depleted', 'spent', 'worn',
]
```

### 2.5 Topic-Specific Emotional Triggers

```python
TOPIC_TRIGGERS = {
    'ai_tech': {
        'positive': ['agi', 'breakthrough', 'transformative', 'revolutionary',
                     'cutting-edge', 'state-of-the-art', 'futuristic', 'paradigm'],
        'negative': ['job loss', 'replacement', 'surveillance', 'bias', 'unethical',
                     'dangerous', 'uncontrolled', 'black box', 'hallucination'],
    },
    'crypto_finance': {
        'positive': ['bullish', 'moon', 'breakout', 'gains', 'profit',
                     'undervalued', 'opportunity', 'adoption', 'institutional'],
        'negative': ['crash', 'scam', 'rug pull', 'hack', 'regulation',
                     'bearish', 'collapse', 'fraud', 'ponzi'],
    },
    'fitness_health': {
        'positive': ['stronger', 'leaner', 'healthier', 'energy', 'vitality',
                     'transformation', 'results', 'progress', 'peak'],
        'negative': ['injury', 'risk', 'danger', 'warning', 'overtraining',
                     'burnout', 'plateau', 'setback'],
    },
    'cooking_food': {
        'positive': ['delicious', 'incredible', 'mouth-watering', 'savory',
                     'comfort', 'authentic', 'homemade', 'fresh'],
        'negative': ['bland', 'boring', 'overpriced', 'unhealthy', 'processed'],
    },
    'music_creative': {
        'positive': ['masterpiece', 'genius', 'soulful', 'haunting', 'timeless',
                     'innovative', 'raw', 'authentic', 'viral'],
        'negative': ['overrated', 'generic', 'derivative', 'sellout', 'formulaic'],
    },
    'news_world': {
        'positive': ['breakthrough', 'historic', 'milestone', 'progress', 'deal',
                     'agreement', 'success', 'victory', 'progress'],
        'negative': ['breaking', 'crisis', 'emergency', 'war', 'conflict',
                     'attack', 'collapse', 'plummet', 'disaster'],
    },
}
```

---

## 3. CONTENT QUALITY SIGNALS

### 3.1 Narrative Structure Indicators

```python
def detect_narrative_quality(text):
    indicators = {
        'has_hook': bool(re.search(r'(?:hook|catchy|attention-grabbing|compelling opening)', text[:200].lower())),
        'has_transition_words': len(re.findall(r'\b(?:however|moreover|furthermore|additionally|meanwhile|consequently|therefore|nevertheless)\b', text.lower())),
        'has_paragraphs': len([p for p in text.split('\n') if p.strip()]) >= 3,
        'sentence_variety': len(set([len(s.split()) for s in text.split('.') if s.strip()])) > 3,
        'has_conclusion': bool(re.search(r'(?:in conclusion|to summarize|the takeaway|bottom line|key point|final thought)', text.lower())),
    }
    return sum(indicators.values()) * 8
```

### 3.2 Specificity Markers

```python
def detect_specificity(text):
    score = 0
    
    # Exact numbers
    score += min(len(re.findall(r'\b\d+\.?\d*%?\b', text)) * 2, 20)
    
    # Dates
    score += min(len(re.findall(r'\b(?:20\d{2}|january|february|march|april|may|june|july|august|september|october|november|december)\b', text.lower())) * 3, 15)
    
    # Named entities (approximate)
    score += min(len(re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', text)) * 2, 15)
    
    return min(score, 50)
```

### 3.3 Authority Signals

```python
def detect_authority_signals(text):
    score = 0
    
    # Citations
    score += min(len(re.findall(r'\[\d+\]|\(.*?\d{4}.*?\)|doi:|arxiv:|pubmed:', text.lower())) * 5, 20)
    
    # Source mentions
    sources = ['harvard', 'mit', 'stanford', 'oxford', 'cambridge',
               'google', 'microsoft', 'nvidia', 'openai', 'meta',
               'bloomberg', 'reuters', 'nature', 'science', 'lancet']
    score += min(sum(3 for s in sources if s in text.lower()), 15)
    
    # Expert quotes
    score += min(len(re.findall(r'["""].*?["""].*?(?:said|says|stated|explained|noted|added|remarked)', text)) * 5, 15)
    
    return min(score, 50)
```

### 3.4 Social Proof Indicators

```python
def detect_social_proof_signals(text):
    score = 0
    
    # User metrics
    metrics = re.findall(r'(\d[\d,\.]*\s*(?:million|M|thousand|K|billion|B)?\s*(?:users|downloads|views|followers|subscribers|customers))', text.lower())
    score += min(len(metrics) * 8, 30)
    
    # Testimonials
    score += min(len(re.findall(r'["""].*?["""].*?(?:user|customer|client|member)', text.lower())) * 5, 15)
    
    # Awards/recognition
    awards = ['award', 'winner', 'best', 'top-rated', 'editor\'s choice', '#1']
    score += min(sum(3 for a in awards if a in text.lower()), 15)
    
    return min(score, 50)
```

### 3.5 Actionability Markers

```python
def detect_actionability(text):
    score = 0
    
    # Steps/instructions
    score += min(len(re.findall(r'(?:^|\n)\s*\d+[\.\)]\s+', text)) * 5, 20)
    
    # Action verbs
    action_verbs = ['click', 'download', 'install', 'sign up', 'try', 'start',
                    'check', 'visit', 'subscribe', 'follow', 'join', 'register']
    score += min(sum(2 for v in action_verbs if v in text.lower()), 15)
    
    # Links/URLs
    score += min(len(re.findall(r'https?://\S+', text)) * 3, 10)
    
    # Time estimates
    score += min(len(re.findall(r'\d+\s*(?:min|hour|day|week|month)', text.lower())) * 3, 10)
    
    return min(score, 50)
```

---

## 4. TOPIC-ADAPTIVE WEIGHTS

```python
TOPIC_WEIGHTS = {
    'news_breaking': {
        'curiosity_gap': 1.0,       # Moderate
        'emotional_arousal': 1.2,    # High - breaking news needs urgency
        'social_proof': 0.8,         # Lower - people want raw info
        'practical_value': 0.6,      # Lower - not actionable
        'narrative': 0.5,            # Lower - straight facts
        'authority': 1.3,            # Highest - credibility critical
        'identity': 0.4,             # Lower
        'scarcity': 1.4,             # Highest - urgency matters
    },
    'educational': {
        'curiosity_gap': 1.3,        # High - learning is about gaps
        'emotional_arousal': 0.7,    # Lower - calm learning preferred
        'social_proof': 0.9,         # Moderate
        'practical_value': 1.5,      # Highest - must be useful
        'narrative': 1.2,            # High - stories teach
        'authority': 1.4,            # High - expertise matters
        'identity': 0.8,             # Moderate
        'scarcity': 0.3,             # Low - not time-sensitive
    },
    'entertainment': {
        'curiosity_gap': 1.2,        # High - wants surprise
        'emotional_arousal': 1.5,    # Highest - emotion is the product
        'social_proof': 0.7,         # Lower
        'practical_value': 0.4,      # Low - not functional
        'narrative': 1.4,            # High - storytelling
        'authority': 0.3,            # Low - entertainment value
        'identity': 1.3,             # High - shares identity
        'scarcity': 0.6,             # Moderate
    },
    'products_tools': {
        'curiosity_gap': 0.8,        # Moderate
        'emotional_arousal': 0.9,    # Moderate
        'social_proof': 1.4,         # High - others' experiences matter
        'practical_value': 1.5,      # Highest - must be useful
        'narrative': 0.6,            # Lower - direct is better
        'authority': 1.3,            # High - trust required
        'identity': 0.7,             # Moderate
        'scarcity': 1.1,             # Moderate-High
    },
    'fitness_health': {
        'curiosity_gap': 1.1,        # Moderate-High
        'emotional_arousal': 1.2,    # High - motivation
        'social_proof': 1.3,         # High - transformation proof
        'practical_value': 1.3,      # High - actionable tips
        'narrative': 1.1,            # Moderate-High
        'authority': 1.2,            # High - expertise matters
        'identity': 1.2,             # High - fitness identity
        'scarcity': 0.5,             # Lower
    },
    'cooking_food': {
        'curiosity_gap': 0.9,        # Moderate
        'emotional_arousal': 1.1,    # Moderate-High - appetite
        'social_proof': 0.8,         # Moderate
        'practical_value': 1.4,      # High - recipes must work
        'narrative': 1.0,            # Moderate
        'authority': 0.7,            # Moderate
        'identity': 0.9,             # Moderate
        'scarcity': 0.4,             # Low
    },
    'music_creative': {
        'curiosity_gap': 1.0,        # Moderate
        'emotional_arousal': 1.4,    # High - music is emotional
        'social_proof': 1.1,         # Moderate-High
        'practical_value': 0.5,      # Lower - subjective
        'narrative': 1.3,            # High - stories around music
        'authority': 0.6,            # Lower - taste varies
        'identity': 1.4,             # High - music = identity
        'scarcity': 0.7,             # Moderate
    },
    'crypto_finance': {
        'curiosity_gap': 1.2,        # High - market uncertainty
        'emotional_arousal': 1.3,    # High - financial anxiety/excitement
        'social_proof': 1.4,         # High - crowd sentiment
        'practical_value': 1.2,      # High - actionable advice
        'narrative': 0.7,            # Moderate-Low
        'authority': 1.3,            # High - credibility critical
        'identity': 1.1,             # Moderate-High
        'scarcity': 1.3,             # High - FOMO drives crypto
    },
}
```

---

## 5. ANTI-PATTERNS (What to AVOID)

### 5.1 Clickbait Without Substance

```python
CLICKBAIT_PATTERNS = [
    r'(?:you won\'t believe|this one trick|doctors hate)',
    r'(?:what happens next|what she did next)',
    r'(?:the (?:one|only) (?:thing|way|secret))',
    r'(?:you\'re doing it wrong)',
    r'(?:this will change your life)',
    r'(?:99% of people don\'t know)',
    r'(?:they don\'t want you to see)',
    r'(?:gone wrong|gone sexual|not what you think)',
]

def detect_clickbait(text):
    score = 0
    text_lower = text.lower()
    for pattern in CLICKBAIT_PATTERNS:
        if re.search(pattern, text_lower):
            score += 10
    return min(score, 50)
```

### 5.2 Outrage Farming

```python
OUTRAGE_PATTERNS = [
    r'(?:can you believe|how is this (?:allowed|possible))',
    r'(?:this is (?:why|what happens))',
    r'(?:wake up|open your eyes)',
    r'(?:they (?:don\'t want you to know|are hiding))',
    r'(?:share before (?:they take it down|it\'s deleted))',
    r'(?:mainstream media won\'t tell you)',
]

def detect_outrage_farming(text):
    score = 0
    text_lower = text.lower()
    for pattern in OUTRAGE_PATTERNS:
        if re.search(pattern, text_lower):
            score += 12
    # Excessive caps
    caps_ratio = len(re.findall(r'\b[A-Z]{2,}\b', text)) / max(len(text.split()), 1)
    if caps_ratio > 0.1:
        score += 15
    return min(score, 50)
```

### 5.3 Misinformation Signals

```python
MISINFO_SIGNALS = [
    r'(?:do your own research|think for yourself)',
    r'(?:the (?:government|media|they) (?:is |are )?(?:lying|hiding))',
    r'(?:100% (?:proven|guaranteed|cured))',
    r'(?:miracle (?:cure|solution|remedy))',
    r'(?:doctors don\'t want you to know)',
    r'(?:big pharma|mainstream science)',
]

def detect_misinfo_signals(text):
    score = 0
    text_lower = text.lower()
    for pattern in MISINFO_SIGNALS:
        if re.search(pattern, text_lower):
            score += 15
    # Absolute claims
    absolutes = re.findall(r'(?:100%|always|never|impossible|guaranteed|proven)', text_lower)
    score += min(len(absolutes) * 5, 20)
    return min(score, 50)
```

### 5.4 Low-Effort Content

```python
LOW_EFFORT_SIGNALS = [
    r'(?:^|\n)(?:thread|THREAD)\s*[1/]\s*$',
    r'(?:follow for more|like and share|rt if you agree)',
    r'(?:link in bio|check my profile)',
    r'(?:DM me|send me a message)',
    r'(?:boost this|retweet this|share this)',
]

def detect_low_effort(text):
    score = 0
    text_lower = text.lower()
    
    for pattern in LOW_EFFORT_SIGNALS:
        if re.search(pattern, text_lower):
            score += 10
    
    # Very short content
    words = text.split()
    if len(words) < 20:
        score += 15
    elif len(words) < 50:
        score += 5
    
    # No formatting
    if '\n' not in text and len(text) > 200:
        score += 10
    
    return min(score, 50)
```

### 5.5 Duplicate/Regurgitated Content

```python
def detect_generic_content(text):
    score = 0
    text_lower = text.lower()
    
    # Overused buzzwords
    buzzwords = ['disrupt', 'synergy', 'leverage', 'innovative', 'cutting-edge',
                 'game-changer', 'next-gen', 'paradigm shift', 'ecosystem']
    score += min(sum(5 for b in buzzwords if b in text_lower), 25)
    
    # Generic advice
    generic_patterns = [r'(?:just be yourself|follow your passion|believe in)',
                       r'(?:the key to|the secret to|the only way to)',
                       r'(?:everyone knows|it\'s obvious that|clearly)']
    for pattern in generic_patterns:
        if re.search(pattern, text_lower):
            score += 8
    
    # Lack of specifics (no numbers, no names, no dates)
    if not re.search(r'\d', text):
        score += 10
    if not re.search(r'[A-Z][a-z]+', text):
        score += 10
    
    return min(score, 50)
```

---

## 6. SCORING FORMULA

### 6.1 Base Score Calculation

```python
def calculate_base_score(text, topic='general'):
    """
    Calculate the base psychological engagement score.
    Returns 0-100.
    """
    # Raw scores (each 0-50)
    raw_scores = {
        'curiosity_gap': detect_curiosity_gap(text),
        'emotional_arousal': detect_emotional_arousal(text),
        'social_proof': detect_social_proof(text),
        'practical_value': detect_practical_value(text),
        'narrative': detect_narrative_structure(text),
        'authority': detect_authority(text),
        'identity': detect_identity_signal(text),
        'scarcity': detect_scarcity_urgency(text),
    }
    
    # Get topic-specific weights
    weights = TOPIC_WEIGHTS.get(topic, TOPIC_WEIGHTS['general'])
    
    # Normalize raw scores to 0-1 scale
    normalized = {k: v / 50.0 for k, v in raw_scores.items()}
    
    # Apply topic weights
    weighted_scores = {}
    for factor, score in normalized.items():
        weight = weights.get(factor, 1.0)
        weighted_scores[factor] = score * weight
    
    # Quality bonuses
    quality_bonus = 0
    quality_bonus += detect_narrative_quality(text) / 100.0
    quality_bonus += detect_specificity(text) / 100.0
    quality_bonus += detect_authority_signals(text) / 100.0
    quality_bonus += detect_actionability(text) / 100.0
    
    # Anti-pattern penalties
    penalty = 0
    penalty += detect_clickbait(text) / 100.0
    penalty += detect_outrage_farming(text) / 100.0
    penalty += detect_misinfo_signals(text) / 100.0
    penalty += detect_low_effort(text) / 100.0
    penalty += detect_generic_content(text) / 100.0
    
    # Composite score
    total_weight = sum(weights.values())
    raw_composite = sum(weighted_scores.values()) / total_weight
    
    # Apply quality bonus and penalties
    final_score = (raw_composite + quality_bonus * 0.3 - penalty * 0.5) * 100
    
    return max(0, min(100, round(final_score)))
```

### 6.2 Scoring Thresholds

```python
SCORING_TIERS = {
    'reject': {
        'range': (0, 30),
        'action': 'REJECT',
        'description': 'Content fails to meet minimum quality standards',
        'criteria': [
            'High anti-pattern scores (clickbait, outrage farming)',
            'Low engagement factors across all dimensions',
            'Generic or low-effort content',
            'Misinformation signals detected',
        ],
    },
    'consider': {
        'range': (30, 60),
        'action': 'CONSIDER',
        'description': 'Content has potential but needs review or improvement',
        'criteria': [
            'Some engagement factors present but not strong',
            'May be topic-appropriate for niche audiences',
            'Could benefit from editing or enhancement',
            'No major anti-pattern violations',
        ],
    },
    'promote': {
        'range': (60, 80),
        'action': 'PROMOTE',
        'description': 'High-quality content worth publishing',
        'criteria': [
            'Strong engagement factors in multiple dimensions',
            'Good content quality signals',
            'No significant anti-patterns',
            'Appropriate for broad audience',
        ],
    },
    'featured': {
        'range': (80, 100),
        'action': 'FEATURE',
        'description': 'Exceptional content for premium placement',
        'criteria': [
            'Outstanding engagement potential',
            'Excellent quality and authority',
            'Strong narrative or emotional impact',
            'High shareability and virality potential',
        ],
    },
}
```

### 6.3 Score Breakdown Output

```python
def generate_score_breakdown(text, topic='general'):
    """
    Generate detailed score breakdown for debugging/transparency.
    """
    raw_scores = {
        'curiosity_gap': detect_curiosity_gap(text),
        'emotional_arousal': detect_emotional_arousal(text),
        'social_proof': detect_social_proof(text),
        'practical_value': detect_practical_value(text),
        'narrative': detect_narrative_structure(text),
        'authority': detect_authority(text),
        'identity': detect_identity_signal(text),
        'scarcity': detect_scarcity_urgency(text),
    }
    
    weights = TOPIC_WEIGHTS.get(topic, TOPIC_WEIGHTS['general'])
    
    breakdown = {
        'total_score': calculate_base_score(text, topic),
        'factors': {},
        'quality_signals': {},
        'anti_patterns': {},
    }
    
    for factor, score in raw_scores.items():
        weight = weights.get(factor, 1.0)
        breakdown['factors'][factor] = {
            'raw': score,
            'weight': weight,
            'weighted': round(score * weight / 50, 2),
        }
    
    breakdown['quality_signals'] = {
        'narrative_quality': detect_narrative_quality(text),
        'specificity': detect_specificity(text),
        'authority_signals': detect_authority_signals(text),
        'social_proof_signals': detect_social_proof_signals(text),
        'actionability': detect_actionability(text),
    }
    
    breakdown['anti_patterns'] = {
        'clickbait': detect_clickbait(text),
        'outrage_farming': detect_outrage_farming(text),
        'misinfo_signals': detect_misinfo_signals(text),
        'low_effort': detect_low_effort(text),
        'generic_content': detect_generic_content(text),
    }
    
    return breakdown
```

---

## 7. TOPIC DETECTION

```python
TOPIC_KEYWORDS = {
    'ai_tech': ['ai', 'artificial intelligence', 'machine learning', 'neural',
                'llm', 'gpt', 'openai', 'deep learning', 'automation', 'robot',
                'algorithm', 'model', 'training', 'data science', 'tech'],
    'crypto_finance': ['crypto', 'bitcoin', 'ethereum', 'blockchain', 'defi',
                       'nft', 'token', 'wallet', 'trading', 'investment',
                       'stock', 'market', 'finance', 'money', 'wealth'],
    'fitness_health': ['fitness', 'workout', 'exercise', 'gym', 'muscle',
                       'weight loss', 'nutrition', 'diet', 'health', 'wellness',
                       'running', 'strength', 'cardio', 'protein', 'training'],
    'cooking_food': ['recipe', 'cook', 'baking', 'food', 'kitchen', 'chef',
                     'ingredient', 'meal', 'dinner', 'lunch', 'breakfast',
                     'restaurant', 'cuisine', 'flavor', 'taste'],
    'music_creative': ['music', 'song', 'album', 'artist', 'band', 'concert',
                       'playlist', 'guitar', 'piano', 'vocal', 'producer',
                       'sound', 'melody', 'rhythm', 'creative'],
    'news_breaking': ['breaking', 'news', 'report', 'announce', 'launch',
                      'release', 'update', 'today', 'urgent', 'developing'],
}

def detect_topic(text):
    """Auto-detect content topic from keywords."""
    text_lower = text.lower()
    scores = {}
    
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        scores[topic] = score
    
    if max(scores.values()) >= 2:
        return max(scores, key=scores.get)
    return 'general'
```

---

## 8. IMPLEMENTATION EXAMPLE

```python
def score_content(text, topic=None):
    """
    Main entry point for content scoring.
    
    Args:
        text: Content to score
        topic: Optional topic override (auto-detected if None)
    
    Returns:
        dict with score, tier, breakdown
    """
    # Auto-detect topic if not provided
    if topic is None:
        topic = detect_topic(text)
    
    # Calculate score
    score = calculate_base_score(text, topic)
    
    # Determine tier
    tier = 'reject'
    for tier_name, tier_info in SCORING_TIERS.items():
        low, high = tier_info['range']
        if low <= score < high:
            tier = tier_name
            break
    
    # Generate breakdown
    breakdown = generate_score_breakdown(text, topic)
    
    return {
        'score': score,
        'tier': tier,
        'tier_action': SCORING_TIERS[tier]['action'],
        'topic': topic,
        'breakdown': breakdown,
    }


# Usage example
if __name__ == '__main__':
    test_content = """
    Breaking: OpenAI just released GPT-5 with 10x better reasoning.
    
    The model scored 95% on MMLU benchmark, surpassing human experts.
    Early tests show it can write production-grade code and solve PhD-level
    math problems in seconds.
    
    "This changes everything," said Sam Altman, CEO of OpenAI.
    
    Available now for ChatGPT Plus subscribers. Try it today before
    the API pricing increases next week.
    """
    
    result = score_content(test_content)
    print(f"Score: {result['score']}/100")
    print(f"Tier: {result['tier'].upper()}")
    print(f"Action: {result['tier_action']}")
    print(f"Topic: {result['topic']}")
```

---

## 9. RECOMMENDED CONFIGURATION

```python
# Default configuration
CONFIG = {
    'min_word_count': 50,          # Minimum words for valid content
    'max_word_count': 2000,        # Maximum words (longer content penalized)
    'emoji_limit': 10,             # Max emojis before penalty
    'caps_limit': 0.05,            # Max caps ratio
    'paragraph_min': 2,            # Minimum paragraphs
    'paragraph_max': 50,           # Maximum paragraphs
    'time_decay_hours': 48,        # Score decay for news content
    'boost_hours': 4,              # Boost window for breaking news
}
```

---

## 10. REFERENCES

1. Loewenstein, G. (1994). The Psychology of Curiosity: A Review and Reinterpretation. *Psychological Bulletin*, 116(1), 75-98.
2. Cialdini, R.B. (2006). *Influence: The Psychology of Persuasion*. Harper Business.
3. Berger, J. & Milkman, K.L. (2012). What Makes Online Content Viral? *Journal of Marketing Research*, 49(2), 192-205.
4. Berger, J. (2013). *Contagious: Why Things Catch On*. Simon & Schuster.
5. Green, M.C. & Brock, T.C. (2000). The Role of Transportation in the Persuasiveness of Public Narratives. *Journal of Personality and Social Psychology*, 79(5), 701-721.
6. Hatfield, E., Cacioppo, J.T., & Rapson, R.L. (1994). *Emotional Contagion*. Cambridge University Press.
7. Przybylski, A.K. et al. (2013). Motivational, Emotional, and Behavioral FOMO. *Computers in Human Behavior*, 29(4), 1841-1848.
8. Kahneman, D. (2011). *Thinking, Fast and Slow*. Farrar, Straus and Giroux.
9. Vohs, K.D. et al. (2008). Making Choices Impairs Subsequent Self-Control. *Journal of Personality and Social Psychology*, 94(5), 883-898.

---

*Document Version: 1.0*
*Last Updated: 2026-06-21*
*Author: Dr. Elena Volkov, Consumer Psychology Framework*
