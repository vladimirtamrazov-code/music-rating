import pytest

from app.scoring import MAX_SCORE, calc_score, score_tier
from app.utils import plural, slugify


def test_max_and_min():
    assert calc_score(10, 10, 10, 10, 10) == MAX_SCORE == 90
    assert calc_score(1, 1, 1, 1, 1) == 6  # 4 * 1.4 = 5.6


def test_vibe_is_multiplier():
    flat = calc_score(7, 7, 7, 7, 1)
    boosted = calc_score(7, 7, 7, 7, 10)
    assert flat == 39  # 28 * 1.4 = 39.2
    assert boosted == 63  # 39.2 * 1.607
    assert boosted > flat


def test_monotonic():
    prev = 0
    for v in range(1, 11):
        s = calc_score(v, v, v, v, v)
        assert s > prev
        prev = s


@pytest.mark.parametrize("bad", [0, 11, -1, 5.5, "5", None, True])
def test_rejects_bad_values(bad):
    with pytest.raises(ValueError):
        calc_score(5, 5, 5, 5, bad)


def test_tiers():
    assert score_tier(None) == "tier-none"
    assert score_tier(85) == "tier-gold"
    assert score_tier(70) == "tier-high"
    assert score_tier(50) == "tier-mid"
    assert score_tier(20) == "tier-low"


def test_slugify_cyrillic():
    assert slugify("Северный Ветер — Белые ночи") == "severnyy-veter-belye-nochi"
    assert slugify("!!!") == "item"


def test_plural():
    assert plural(1, "оценка", "оценки", "оценок") == "оценка"
    assert plural(3, "оценка", "оценки", "оценок") == "оценки"
    assert plural(11, "оценка", "оценки", "оценок") == "оценок"
    assert plural(22, "оценка", "оценки", "оценок") == "оценки"
