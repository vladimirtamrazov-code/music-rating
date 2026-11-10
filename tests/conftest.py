import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Artist, Release, User


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def make_user(username="alice", role="user", password="password123"):
    u = User(username=username, email=f"{username}@example.com", role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return u


def make_release(title="Тестовый альбом", artist_name="Тест Артист", status="published"):
    a = Artist.query.filter_by(name=artist_name).first()
    if a is None:
        a = Artist(name=artist_name, slug=f"artist-{Artist.query.count() + 1}")
        db.session.add(a)
    r = Release(title=title, slug=f"release-{Release.query.count() + 1}", artist=a, status=status)
    db.session.add(r)
    db.session.commit()
    return r


def login(client, username="alice", password="password123"):
    return client.post("/auth/login", data={"login": username, "password": password},
                       follow_redirects=True)
