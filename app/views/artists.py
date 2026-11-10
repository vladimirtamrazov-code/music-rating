from flask import Blueprint, render_template, request
from sqlalchemy import func

from ..extensions import db
from ..models import Artist, Release

bp = Blueprint("artists", __name__, url_prefix="/artists")


@bp.route("/")
def catalog():
    q = (request.args.get("q") or "").strip()[:100]
    counts = (db.session.query(Release.artist_id, func.count(Release.id).label("n"),
                               func.avg(Release.user_score).label("avg"))
              .filter(Release.status == "published")
              .group_by(Release.artist_id).subquery())
    query = (db.session.query(Artist, counts.c.n, counts.c.avg)
             .join(counts, counts.c.artist_id == Artist.id))
    if q:
        query = query.filter(Artist.name.ilike(f"%{q}%"))
    page = query.order_by(Artist.name).paginate(
        page=request.args.get("page", 1, type=int), per_page=48, error_out=False)
    return render_template("artists/catalog.html", page=page, q=q)


@bp.route("/<slug>")
def detail(slug):
    artist = Artist.query.filter_by(slug=slug).first_or_404()
    releases = (artist.releases.filter(Release.status == "published")
                .order_by(Release.release_date.desc().nulls_last()).all())
    rated = [r.user_score for r in releases if r.user_score is not None]
    avg = round(sum(rated) / len(rated), 1) if rated else None
    best = max((r for r in releases if r.user_score is not None),
               key=lambda r: r.user_score, default=None)
    return render_template("artists/detail.html", artist=artist, releases=releases,
                           avg=avg, best=best)
