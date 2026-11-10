from datetime import date, timedelta

from flask import Blueprint, render_template, request
from sqlalchemy import func, or_

from ..extensions import db
from ..models import Artist, Release, Review, User

bp = Blueprint("main", __name__)

PERIODS = {"month": ("За месяц", 30), "year": ("За год", 365), "all": ("За всё время", None)}


def top_query(period: str = "month", rtype: str | None = None, by: str = "users"):
    score_col = Release.critic_score if by == "critics" else Release.user_score
    count_col = Release.critic_count if by == "critics" else Release.user_count
    q = Release.published().filter(score_col.isnot(None))
    days = PERIODS.get(period, PERIODS["month"])[1]
    if days:
        q = q.filter(Release.release_date >= date.today() - timedelta(days=days))
    if rtype in Release.TYPES:
        q = q.filter(Release.type == rtype)
    return q.order_by(score_col.desc(), count_col.desc(), Release.id.desc())


@bp.route("/")
def index():
    new_releases = (Release.published()
                    .order_by(Release.release_date.desc().nulls_last(), Release.id.desc())
                    .limit(12).all())
    top_month = top_query("month").limit(6).all()
    if not top_month:
        top_month = top_query("all").limit(6).all()
    latest_reviews = (Review.query.join(Release)
                      .filter(Release.status == "published", Review.text != "")
                      .order_by(Review.created_at.desc()).limit(6).all())
    stats = {
        "releases": Release.published().count(),
        "reviews": db.session.query(func.count(Review.id)).scalar(),
        "users": db.session.query(func.count(User.id)).scalar(),
    }
    return render_template("index.html", new_releases=new_releases, top_month=top_month,
                           latest_reviews=latest_reviews, stats=stats)


@bp.route("/top")
def top():
    period = request.args.get("period", "month")
    if period not in PERIODS:
        period = "month"
    rtype = request.args.get("type") or None
    by = "critics" if request.args.get("by") == "critics" else "users"
    releases = top_query(period, rtype, by).limit(100).all()
    return render_template("top.html", releases=releases, period=period, rtype=rtype,
                           by=by, periods=PERIODS)


@bp.route("/search")
def search():
    q = (request.args.get("q") or "").strip()[:100]
    releases = artists = users = []
    if len(q) >= 2:
        like = f"%{q}%"
        releases = (Release.published().join(Artist)
                    .filter(or_(Release.title.ilike(like), Artist.name.ilike(like)))
                    .order_by(Release.release_date.desc().nulls_last()).limit(30).all())
        artists = Artist.query.filter(Artist.name.ilike(like)).order_by(Artist.name).limit(20).all()
        users = User.query.filter(User.username.ilike(like)).order_by(User.username).limit(20).all()
    return render_template("search.html", q=q, releases=releases, artists=artists, users=users)


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/healthz")
def healthz():
    db.session.execute(db.text("SELECT 1"))
    return {"status": "ok"}
