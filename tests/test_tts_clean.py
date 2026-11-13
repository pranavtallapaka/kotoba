from kotoba.tts import clean_for_tts


def test_strips_emoji():
    assert clean_for_tts("좋아요! 😊") == "좋아요!"


def test_keeps_korean_and_latin():
    assert clean_for_tts("안녕하세요. Hello!") == "안녕하세요. Hello!"


def test_strips_mid_sentence_emoji():
    assert clean_for_tts("오늘 🌸 날씨가 좋네요.") == "오늘  날씨가 좋네요."


def test_empty():
    assert clean_for_tts("😂😂😂") == ""
