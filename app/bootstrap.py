"""Создание администратора из переменных окружения и демо-наполнение.

На бесплатном тарифе Render нет shell-доступа, поэтому администратор
создаётся при старте из ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD.
"""
import random
import secrets
from datetime import date, timedelta

from sqlalchemy import func

from .extensions import db
from .models import Artist, Release, Review, User
from .utils import unique_slug


def ensure_admin(app) -> None:
    username = app.config.get("ADMIN_USERNAME")
    password = app.config.get("ADMIN_PASSWORD")
    if not username or not password:
        return
    user = User.query.filter(func.lower(User.username) == username.lower()).first()
    if user is None:
        email = app.config.get("ADMIN_EMAIL") or f"{username}@localhost"
        user = User(username=username, email=email, role="admin")
        user.set_password(password)
        db.session.add(user)
        app.logger.info("Создан администратор %s", username)
    elif user.role != "admin":
        user.role = "admin"
    db.session.commit()


# Вымышленные исполнители и релизы — только для демонстрации
DEMO_ARTISTS = [
    ("Северный Ветер", "Питерский рэпер с меланхоличным звуком и плотной лирикой."),
    ("MC Полутон", "Олдскульная школа, бэнгеры и бесконечные панчлайны."),
    ("Луна Неон", "Поп-артистка на стыке R&B и синтвейва."),
    ("Кирпич", "Уличный рэп с тяжёлыми битами и прямолинейной подачей."),
    ("Гамма Синий", "Инди-проект с гитарами и неожиданными аранжировками."),
    ("Тёплый Ламповый", "Электроника, лоу-фай и атмосферные эксперименты."),
]

DEMO_RELEASES = [
    (0, "Белые ночи", "album", "Хип-хоп", 25),
    (0, "Мосты разведены", "single", "Хип-хоп", 4),
    (1, "Строка за строкой", "album", "Хип-хоп", 60),
    (1, "Панч-лаборатория", "ep", "Хип-хоп", 12),
    (2, "Неоновые сны", "album", "R&B", 18),
    (2, "Ночной экспресс", "single", "Поп", 2),
    (3, "Бетон", "mixtape", "Хип-хоп", 40),
    (4, "Синие гитары", "album", "Инди", 90),
    (4, "Шум прибоя", "ep", "Инди", 9),
    (5, "Тёплые волны", "album", "Электроника", 150),
]

DEMO_TEXTS = [
    "Сильный релиз: каждый трек на своём месте, атмосфера держит до конца.",
    "Тексты местами проседают, но звук и подача вытягивают.",
    "Лучшее, что я слышал в этом месяце. Переслушиваю уже третий день.",
    "Неплохо, но хотелось большего — слишком безопасно.",
    "",
    "",
]


def seed_demo() -> None:
    if Release.query.first() is not None:
        return
    rnd = random.Random(42)

    users = []
    for i, (name, role) in enumerate([("demo_critic", "critic"), ("listener_anna", "user"),
                                      ("listener_max", "user"), ("listener_oleg", "user"),
                                      ("listener_kate", "user")]):
        u = User.query.filter_by(username=name).first()
        if u is None:
            u = User(username=name, email=f"{name}@demo.local", role=role,
                     bio="Демо-аккаунт")
            u.set_password(secrets.token_urlsafe(16))  # войти под ним нельзя
            db.session.add(u)
        users.append(u)

    artists = []
    for name, bio in DEMO_ARTISTS:
        a = Artist(name=name, slug=unique_slug(Artist, name), bio=bio)
        db.session.add(a)
        db.session.flush()
        artists.append(a)

    today = date.today()
    for idx, title, rtype, genre, days_ago in DEMO_RELEASES:
        tracks = "\n".join(f"Трек {n}" for n in range(1, {"single": 2, "ep": 5}.get(rtype, 10) + 1))
        r = Release(title=title, slug=unique_slug(Release, f"{artists[idx].name} {title}"),
                    artist=artists[idx], type=rtype, genre=genre,
                    release_date=today - timedelta(days=days_ago),
                    description="Демонстрационный релиз.", tracklist=tracks,
                    status="published")
        db.session.add(r)
        db.session.flush()

        quality = rnd.randint(4, 9)
        for u in users:
            if rnd.random() < 0.25:
                continue
            pts = {k: max(1, min(10, quality + rnd.randint(-2, 1)))
                   for k in ("rhymes", "structure", "style", "charisma", "vibe")}
            rev = Review(user=u, release=r, text=rnd.choice(DEMO_TEXTS))
            rev.apply_points(**pts)
            db.session.add(rev)
        r.recalc()
    db.session.commit()
