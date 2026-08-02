from src.agent import check_catalog_guardrails


def make_songs():
    return [
        {"title": "A", "genre": "pop", "mood": "happy", "acousticness": 0.1},
        {"title": "B", "genre": "pop", "mood": "happy", "acousticness": 0.2},
        {"title": "C", "genre": "folk", "mood": "sad", "acousticness": 0.9},
    ]


def test_flags_genre_not_in_catalog():
    profile = {"genre": "k-pop", "mood": "happy", "energy": 0.5, "likes_acoustic": False}
    warnings = check_catalog_guardrails(profile, make_songs())
    assert any("k-pop" in w for w in warnings)


def test_flags_mood_not_in_catalog():
    profile = {"genre": "pop", "mood": "angry", "energy": 0.5, "likes_acoustic": False}
    warnings = check_catalog_guardrails(profile, make_songs())
    assert any("angry" in w for w in warnings)


def test_clamps_and_warns_on_out_of_range_energy():
    profile = {"genre": "pop", "mood": "happy", "energy": 1.4, "likes_acoustic": False}
    warnings = check_catalog_guardrails(profile, make_songs())
    assert any("1.4" in w for w in warnings)
    assert profile["energy"] == 1.0


def test_flags_acoustic_genre_contradiction():
    profile = {"genre": "pop", "mood": "happy", "energy": 0.5, "likes_acoustic": True}
    warnings = check_catalog_guardrails(profile, make_songs())
    assert any("acoustic" in w.lower() for w in warnings)


def test_no_warnings_for_consistent_profile():
    profile = {"genre": "folk", "mood": "sad", "energy": 0.5, "likes_acoustic": True}
    warnings = check_catalog_guardrails(profile, make_songs())
    assert warnings == []
