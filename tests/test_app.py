from app.extensions import db
from app.models import Release, Review, User

from .conftest import login, make_release, make_user

POINTS = {"rhymes": 8, "structure": 7, "style": 9, "charisma": 8, "vibe": 9}


def test_public_pages(client):
    make_release()
    for url in ["/", "/releases/", "/top", "/top?period=all", "/artists/", "/about",
                "/search?q=Тест", "/healthz", "/auth/login", "/auth/register"]:
        assert client.get(url).status_code == 200, url
    assert client.get("/releases/release-1").status_code == 200
    assert client.get("/nope").status_code == 404


def test_register_and_login(client):
    r = client.post("/auth/register", data={
        "username": "bob", "email": "bob@example.com",
        "password": "password123", "password2": "password123"}, follow_redirects=True)
    assert r.status_code == 200
    assert User.query.filter_by(username="bob").one().role == "user"
    client.post("/auth/logout")
    r = login(client, "bob@example.com")
    assert "Вы вошли" in r.get_data(as_text=True)


def test_duplicate_username_rejected(client):
    make_user("bob")
    r = client.post("/auth/register", data={
        "username": "BOB", "email": "other@example.com",
        "password": "password123", "password2": "password123"})
    assert "уже занят" in r.get_data(as_text=True)


def test_rate_requires_login(client):
    rel = make_release()
    r = client.post(f"/releases/{rel.slug}/rate", data=POINTS)
    assert r.status_code == 302 and "/auth/login" in r.location


def test_rate_updates_aggregates(client):
    rel = make_release()
    make_user("alice")
    make_user("critic", role="critic")

    login(client, "alice")
    client.post(f"/releases/{rel.slug}/rate", data={**POINTS, "text": "Круто"})
    client.post("/auth/logout")
    login(client, "critic")
    client.post(f"/releases/{rel.slug}/rate", data={**POINTS, "vibe": 1})

    db.session.refresh(rel)
    assert rel.user_count == 1 and rel.user_score == 69  # 32 * 1.4 * 1.54
    assert rel.critic_count == 1 and rel.critic_score == 45

    # повторная оценка обновляет, а не дублирует
    client.post(f"/releases/{rel.slug}/rate", data={**POINTS, "vibe": 10})
    db.session.refresh(rel)
    assert Review.query.count() == 2
    assert rel.critic_score == 72


def test_invalid_points_rejected(client):
    rel = make_release()
    make_user()
    login(client)
    client.post(f"/releases/{rel.slug}/rate", data={**POINTS, "vibe": 42})
    assert Review.query.count() == 0


def test_like_toggle(client):
    rel = make_release()
    author = make_user("author")
    make_user("alice")
    rv = Review(user=author, release=rel)
    rv.apply_points(**POINTS)
    db.session.add(rv)
    db.session.commit()

    assert client.post(f"/api/reviews/{rv.id}/like").status_code == 401
    login(client)
    assert client.post(f"/api/reviews/{rv.id}/like").get_json() == {"liked": True, "count": 1}
    assert client.post(f"/api/reviews/{rv.id}/like").get_json() == {"liked": False, "count": 0}


def test_suggest_goes_to_moderation(client):
    make_user()
    login(client)
    client.post("/releases/suggest", data={
        "artist": "Новый Артист", "title": "Дебют", "type": "ep", "genre": "Поп"})
    rel = Release.query.filter_by(title="Дебют").one()
    assert rel.status == "pending"
    assert rel.artist.slug == "novyy-artist"
    assert client.get(f"/releases/{rel.slug}").status_code == 200  # автор видит
    client.post("/auth/logout")
    assert client.get(f"/releases/{rel.slug}").status_code == 404  # гость — нет


def test_admin_access(client):
    make_user("alice")
    make_user("boss", role="admin")
    assert client.get("/admin/").status_code == 302
    login(client, "alice")
    assert client.get("/admin/").status_code == 403
    client.post("/auth/logout")
    login(client, "boss")
    for url in ["/admin/", "/admin/releases", "/admin/releases/new", "/admin/artists",
                "/admin/artists/new", "/admin/users", "/admin/reviews"]:
        assert client.get(url).status_code == 200, url


def test_role_change_recalcs(client):
    rel = make_release()
    alice = make_user("alice")
    make_user("boss", role="admin")
    rv = Review(user=alice, release=rel)
    rv.apply_points(**POINTS)
    db.session.add(rv)
    rel.recalc()
    db.session.commit()
    assert rel.user_count == 1

    login(client, "boss")
    client.post(f"/admin/users/{alice.id}/role", data={"role": "critic"})
    db.session.refresh(rel)
    assert rel.user_count == 0 and rel.critic_count == 1


def test_delete_release_cascades(client):
    rel = make_release()
    alice = make_user("alice")
    make_user("boss", role="admin")
    rv = Review(user=alice, release=rel)
    rv.apply_points(**POINTS)
    db.session.add(rv)
    db.session.commit()
    login(client, "boss")
    client.post(f"/admin/releases/{rel.id}/delete")
    assert Release.query.count() == 0 and Review.query.count() == 0


def test_open_redirect_blocked(client):
    make_user()
    r = client.post("/auth/login?next=https://evil.example/",
                    data={"login": "alice", "password": "password123"})
    assert r.location == "/"


def test_admin_creates_release_with_new_artist(client):
    make_user("boss", role="admin")
    login(client, "boss")
    r = client.post("/admin/releases/new", data={
        "artist": "Свежий Артист", "title": "Первый", "type": "album",
        "genre": "Рок", "status": "published", "tracklist": "Раз\nДва"})
    assert r.status_code == 302
    rel = Release.query.filter_by(title="Первый").one()
    assert rel.status == "published" and rel.tracks == ["Раз", "Два"]
    assert rel.slug == "svezhiy-artist-pervyy"
    page = client.get(f"/releases/{rel.slug}").get_data(as_text=True)
    assert "Свежий Артист" in page
