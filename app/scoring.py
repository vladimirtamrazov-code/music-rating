"""Система оценки релиза.

Четыре базовых критерия (1–10) складываются и умножаются на 1.4,
пятый критерий «Атмосфера» работает как множитель от x1.0 до ~x1.61.
Итог — целое число от 6 до 90. Та же формула продублирована в static/js/app.js.
"""

CRITERIA = [
    ("rhymes", "Рифмы и образы",
     "Текст: рифмовка, метафоры, панчлайны, образность"),
    ("structure", "Структура и ритмика",
     "Построение куплетов и хуков, флоу, попадание в бит"),
    ("style", "Реализация стиля",
     "Насколько качественно исполнен выбранный жанр: звук, продакшн, сведение"),
    ("charisma", "Индивидуальность и харизма",
     "Узнаваемость, подача, собственное лицо артиста"),
]
VIBE = ("vibe", "Атмосфера и вайб",
        "Общее впечатление от релиза — усиливает итоговую оценку")
ALL_CRITERIA = CRITERIA + [VIBE]
CRITERIA_KEYS = [key for key, _, _ in ALL_CRITERIA]

MIN_POINTS = 1
MAX_POINTS = 10
MAX_SCORE = 90
BASE_K = 1.4
VIBE_MAX_BONUS = MAX_SCORE / (BASE_K * len(CRITERIA) * MAX_POINTS) - 1  # ≈ 0.607


def _check(name: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name}: ожидается целое число")
    if not MIN_POINTS <= value <= MAX_POINTS:
        raise ValueError(f"{name}: значение вне диапазона {MIN_POINTS}–{MAX_POINTS}")
    return value


def vibe_multiplier(vibe: int) -> float:
    vibe = _check("vibe", vibe)
    return 1 + (vibe - MIN_POINTS) / (MAX_POINTS - MIN_POINTS) * VIBE_MAX_BONUS


def calc_score(rhymes: int, structure: int, style: int, charisma: int, vibe: int) -> int:
    base = sum(_check(n, v) for n, v in
               (("rhymes", rhymes), ("structure", structure),
                ("style", style), ("charisma", charisma)))
    raw = base * BASE_K * vibe_multiplier(vibe)
    # округление «вверх от .5», как Math.round в JS
    return min(MAX_SCORE, int(raw + 0.5))


def score_tier(score) -> str:
    """CSS-класс для цветного бейджа оценки."""
    if score is None:
        return "tier-none"
    if score >= 80:
        return "tier-gold"
    if score >= 65:
        return "tier-high"
    if score >= 45:
        return "tier-mid"
    return "tier-low"
