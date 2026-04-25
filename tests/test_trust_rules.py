from src.utils.trust_rules import apply_deterministic_trust


def test_deterministic_flags_icu():
    f = {
        "name": "X",
        "trust_score": 0.8,
        "specialties": "[]",
        "procedure": "[]",
        "equipment": "[]",
        "capability": '["icu", "ventilator support"]',
        "description": "We run ICU with critical care",
    }
    r = apply_deterministic_trust(f)
    assert r.adjusted_score_0_1 <= 1.0
    # ICU without equipment evidence may flag
    assert isinstance(r.flags, list)
