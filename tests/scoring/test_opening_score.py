from app.scoring.penalties import opening_strength, weak_opening_penalty


def test_opening_strength_prefers_concrete_hook():
    strong = "Most Telegram posts fail before the reader opens the full text. Here is how to fix that."
    weak = "Today I want to share some thoughts about content and channels in general."

    assert opening_strength(strong) > opening_strength(weak)
    assert weak_opening_penalty(weak) > weak_opening_penalty(strong)
