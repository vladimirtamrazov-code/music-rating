from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager
from .scoring import CRITERIA_KEYS, calc_score


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    ROLES = {"user": "Слушатель", "critic": "Критик", "admin": "Администратор"}
    EDITORIAL_ROLES = ("critic", "admin")

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="user")
    bio = db.Column(db.Text, default="")
    avatar_url = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    reviews = db.relationship("Review", back_populates="user", lazy="dynamic",
                              cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_editorial(self) -> bool:
        return self.role in self.EDITORIAL_ROLES

    @property
    def role_label(self) -> str:
        return self.ROLES.get(self.role, self.role)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Artist(db.Model):
    __tablename__ = "artists"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    bio = db.Column(db.Text, default="")
    photo_url = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    releases = db.relationship("Release", back_populates="artist", lazy="dynamic")


class Release(db.Model):
    __tablename__ = "releases"

    TYPES = {"album": "Альбом", "ep": "EP", "single": "Сингл", "mixtape": "Микстейп"}
    GENRES = ["Хип-хоп", "Поп", "R&B", "Рок", "Электроника", "Инди",
              "Альтернатива", "Метал", "Джаз", "Фолк", "Другое"]
    STATUSES = {"published": "Опубликован", "pending": "На модерации",
                "rejected": "Отклонён"}

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id"), nullable=False, index=True)
    feat = db.Column(db.String(200), default="")
    type = db.Column(db.String(16), nullable=False, default="album")
    genre = db.Column(db.String(40), nullable=False, default="Хип-хоп")
    release_date = db.Column(db.Date, index=True)
    cover_url = db.Column(db.String(500), default="")
    description = db.Column(db.Text, default="")
    tracklist = db.Column(db.Text, default="")
    status = db.Column(db.String(16), nullable=False, default="published", index=True)
    submitted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    # Денормализованные агрегаты — пересчитываются в recalc()
    user_score = db.Column(db.Float)
    user_count = db.Column(db.Integer, nullable=False, default=0)
    critic_score = db.Column(db.Float)
    critic_count = db.Column(db.Integer, nullable=False, default=0)

    artist = db.relationship("Artist", back_populates="releases")
    submitted_by = db.relationship("User")
    reviews = db.relationship("Review", back_populates="release", lazy="dynamic",
                              cascade="all, delete-orphan")

    @classmethod
    def published(cls):
        return cls.query.filter(cls.status == "published")

    @property
    def type_label(self) -> str:
        return self.TYPES.get(self.type, self.type)

    @property
    def status_label(self) -> str:
        return self.STATUSES.get(self.status, self.status)

    @property
    def tracks(self) -> list[str]:
        return [t.strip() for t in (self.tracklist or "").splitlines() if t.strip()]

    @property
    def total_count(self) -> int:
        return self.user_count + self.critic_count

    def _aggregate(self, editorial: bool):
        q = (db.session.query(func.avg(Review.score), func.count(Review.id))
             .join(User, Review.user_id == User.id)
             .filter(Review.release_id == self.id))
        cond = User.role.in_(User.EDITORIAL_ROLES)
        q = q.filter(cond if editorial else ~cond)
        avg, cnt = q.one()
        return (round(float(avg), 1) if avg is not None else None), cnt

    def recalc(self) -> None:
        db.session.flush()
        self.user_score, self.user_count = self._aggregate(editorial=False)
        self.critic_score, self.critic_count = self._aggregate(editorial=True)

    def criteria_averages(self, editorial: bool) -> dict | None:
        cols = [func.avg(getattr(Review, k)) for k in CRITERIA_KEYS]
        cond = User.role.in_(User.EDITORIAL_ROLES)
        row = (db.session.query(*cols)
               .join(User, Review.user_id == User.id)
               .filter(Review.release_id == self.id)
               .filter(cond if editorial else ~cond)
               .one())
        if row[0] is None:
            return None
        return {k: round(float(v), 1) for k, v in zip(CRITERIA_KEYS, row)}


class Review(db.Model):
    __tablename__ = "reviews"
    __table_args__ = (db.UniqueConstraint("user_id", "release_id", name="uq_review_user_release"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    release_id = db.Column(db.Integer, db.ForeignKey("releases.id"), nullable=False, index=True)
    rhymes = db.Column(db.SmallInteger, nullable=False)
    structure = db.Column(db.SmallInteger, nullable=False)
    style = db.Column(db.SmallInteger, nullable=False)
    charisma = db.Column(db.SmallInteger, nullable=False)
    vibe = db.Column(db.SmallInteger, nullable=False)
    score = db.Column(db.SmallInteger, nullable=False, index=True)
    text = db.Column(db.Text, default="")
    likes_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user = db.relationship("User", back_populates="reviews")
    release = db.relationship("Release", back_populates="reviews")
    likes = db.relationship("ReviewLike", back_populates="review", lazy="dynamic",
                            cascade="all, delete-orphan")

    def apply_points(self, **points) -> None:
        for key in CRITERIA_KEYS:
            setattr(self, key, int(points[key]))
        self.score = calc_score(*(getattr(self, k) for k in CRITERIA_KEYS))

    @property
    def points(self) -> dict:
        return {k: getattr(self, k) for k in CRITERIA_KEYS}


class ReviewLike(db.Model):
    __tablename__ = "review_likes"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"), primary_key=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    review = db.relationship("Review", back_populates="likes")
