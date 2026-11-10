from datetime import date

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..forms import ReleaseForm, ReviewForm
from ..models import Artist, Release, Review, ReviewLike
from ..scoring import CRITERIA_KEYS
from ..utils import unique_slug

bp = Blueprint("releases", __name__, url_prefix="/releases")

SORTS = {
    "new": ("Сначала новые", lambda: (Release.release_date.desc().nulls_last(), Release.id.desc())),
    "score": ("По оценке", lambda: (Release.user_score.desc().nulls_last(), Release.user_count.desc())),
    "critics": ("По оценке критиков", lambda: (Release.critic_score.desc().nulls_last(), Release.id.desc())),
    "popular": ("По числу оценок", lambda: (Release.user_count.desc(), Release.id.desc())),
    "added": ("Недавно добавленные", lambda: (Release.created_at.desc(),)),
}


def find_or_create_artist(name: str) -> Artist:
    name = name.strip()
    artist = Artist.query.filter(func.lower(Artist.name) == name.lower()).first()
    if artist is None:
        artist = Artist(name=name, slug=unique_slug(Artist, name))
        db.session.add(artist)
    return artist


def fill_release(release: Release, form: ReleaseForm) -> None:
    """Заполнить релиз из формы. Новый релиз добавляйте в сессию ПОСЛЕ вызова:
    до этого у него нет slug, и автофлаш при генерации slug упал бы."""
    release.artist = find_or_create_artist(form.artist.data)
    for field in ("title", "feat", "type", "genre", "release_date", "cover_url",
                  "description", "tracklist"):
        value = getattr(form, field).data
        setattr(release, field, value.strip() if isinstance(value, str) else value)
    if not release.slug:
        release.slug = unique_slug(Release, f"{release.artist.name} {release.title}")


def get_visible_release(slug: str) -> Release:
    release = Release.query.filter_by(slug=slug).first_or_404()
    if release.status != "published":
        allowed = current_user.is_authenticated and (
            current_user.is_admin or release.submitted_by_id == current_user.id)
        if not allowed:
            abort(404)
    return release


@bp.route("/")
def catalog():
    q = Release.published()
    rtype = request.args.get("type") or ""
    genre = request.args.get("genre") or ""
    year = request.args.get("year", type=int)
    sort = request.args.get("sort", "new")
    if sort not in SORTS:
        sort = "new"
    if rtype in Release.TYPES:
        q = q.filter(Release.type == rtype)
    if genre in Release.GENRES:
        q = q.filter(Release.genre == genre)
    if year and not 1900 <= year <= 2100:
        year = None
    if year:
        q = q.filter(Release.release_date.between(date(year, 1, 1), date(year, 12, 31)))
    page = q.order_by(*SORTS[sort][1]()).paginate(
        page=request.args.get("page", 1, type=int), per_page=24, error_out=False)
    this_year = date.today().year
    return render_template("releases/catalog.html", page=page, rtype=rtype, genre=genre,
                           year=year, sort=sort, sorts=SORTS,
                           years=range(this_year, this_year - 30, -1))


@bp.route("/<slug>")
def detail(slug):
    release = get_visible_release(slug)
    order = request.args.get("order", "top")
    reviews_q = release.reviews.join(Review.user)
    if order == "new":
        reviews_q = reviews_q.order_by(Review.created_at.desc())
    else:
        order = "top"
        reviews_q = reviews_q.order_by(Review.likes_count.desc(), Review.created_at.desc())
    reviews = reviews_q.all()

    my_review = None
    liked_ids = set()
    if current_user.is_authenticated:
        my_review = release.reviews.filter_by(user_id=current_user.id).first()
        liked_ids = {rid for (rid,) in db.session.query(ReviewLike.review_id)
                     .join(Review).filter(Review.release_id == release.id,
                                          ReviewLike.user_id == current_user.id)}
    form = ReviewForm(obj=my_review)
    more_from_artist = (Release.published()
                        .filter(Release.artist_id == release.artist_id, Release.id != release.id)
                        .order_by(Release.release_date.desc().nulls_last()).limit(6).all())
    return render_template(
        "releases/detail.html", release=release, reviews=reviews, order=order,
        my_review=my_review, form=form, liked_ids=liked_ids,
        user_criteria=release.criteria_averages(editorial=False),
        critic_criteria=release.criteria_averages(editorial=True),
        more_from_artist=more_from_artist)


@bp.route("/<slug>/rate", methods=["POST"])
@login_required
def rate(slug):
    release = get_visible_release(slug)
    if release.status != "published":
        flash("Оценивать можно только опубликованные релизы.", "error")
        return redirect(url_for(".detail", slug=slug))
    form = ReviewForm()
    if not form.validate_on_submit():
        for errors in form.errors.values():
            for e in errors:
                flash(e, "error")
        return redirect(url_for(".detail", slug=slug) + "#rate")

    review = release.reviews.filter_by(user_id=current_user.id).first()
    is_new = review is None
    if is_new:
        review = Review(user=current_user, release=release)
        db.session.add(review)
    review.apply_points(**{k: getattr(form, k).data for k in CRITERIA_KEYS})
    review.text = (form.text.data or "").strip()
    release.recalc()
    db.session.commit()
    flash(f"Оценка {'сохранена' if is_new else 'обновлена'}: {review.score}/90", "success")
    return redirect(url_for(".detail", slug=slug) + f"#review-{review.id}")


@bp.route("/<slug>/review/delete", methods=["POST"])
@login_required
def delete_my_review(slug):
    release = get_visible_release(slug)
    review = release.reviews.filter_by(user_id=current_user.id).first_or_404()
    db.session.delete(review)
    release.recalc()
    db.session.commit()
    flash("Ваша оценка удалена.", "info")
    return redirect(url_for(".detail", slug=slug))


@bp.route("/suggest", methods=["GET", "POST"])
@login_required
def suggest():
    form = ReleaseForm()
    if form.validate_on_submit():
        release = Release(submitted_by=current_user,
                          status="published" if current_user.is_admin else "pending")
        with db.session.no_autoflush:
            fill_release(release, form)
        db.session.add(release)
        db.session.commit()
        if release.status == "published":
            flash("Релиз опубликован.", "success")
        else:
            flash("Спасибо! Релиз отправлен на модерацию.", "success")
        return redirect(url_for(".detail", slug=release.slug))
    return render_template("releases/suggest.html", form=form)
