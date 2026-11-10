from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..forms import AdminReleaseForm, ArtistForm
from ..models import Artist, Release, Review, User
from ..utils import admin_required, unique_slug
from .releases import fill_release

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@login_required
@admin_required
def _guard():
    """Все маршруты админки — только для администраторов."""


@bp.route("/")
def dashboard():
    stats = {
        "Релизов": Release.query.count(),
        "На модерации": Release.query.filter_by(status="pending").count(),
        "Исполнителей": Artist.query.count(),
        "Оценок": Review.query.count(),
        "Пользователей": User.query.count(),
    }
    pending = Release.query.filter_by(status="pending").order_by(Release.created_at).all()
    return render_template("admin/dashboard.html", stats=stats, pending=pending)


# ---------- Релизы ----------

@bp.route("/releases")
def releases():
    q = (request.args.get("q") or "").strip()
    status = request.args.get("status") or ""
    query = Release.query.join(Artist)
    if q:
        query = query.filter(Release.title.ilike(f"%{q}%") | Artist.name.ilike(f"%{q}%"))
    if status in Release.STATUSES:
        query = query.filter(Release.status == status)
    page = query.order_by(Release.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=50, error_out=False)
    return render_template("admin/releases.html", page=page, q=q, status=status)


@bp.route("/releases/new", methods=["GET", "POST"])
@bp.route("/releases/<int:release_id>/edit", methods=["GET", "POST"])
def release_form(release_id=None):
    release = db.get_or_404(Release, release_id) if release_id else None
    form = AdminReleaseForm(obj=release)
    if request.method == "GET" and release:
        form.artist.data = release.artist.name
    if form.validate_on_submit():
        is_new = release is None
        if is_new:
            release = Release(submitted_by=current_user)
        with db.session.no_autoflush:
            fill_release(release, form)
        release.status = form.status.data
        if is_new:
            db.session.add(release)
        db.session.commit()
        flash("Релиз сохранён.", "success")
        return redirect(url_for("releases.detail", slug=release.slug))
    return render_template("admin/release_form.html", form=form, release=release)


@bp.route("/releases/<int:release_id>/status", methods=["POST"])
def release_status(release_id):
    release = db.get_or_404(Release, release_id)
    status = request.form.get("status")
    if status in Release.STATUSES:
        release.status = status
        db.session.commit()
        flash(f"«{release.title}»: {release.status_label.lower()}.", "success")
    return redirect(request.referrer or url_for(".dashboard"))


@bp.route("/releases/<int:release_id>/delete", methods=["POST"])
def release_delete(release_id):
    release = db.get_or_404(Release, release_id)
    db.session.delete(release)
    db.session.commit()
    flash(f"Релиз «{release.title}» удалён.", "info")
    return redirect(url_for(".releases"))


# ---------- Исполнители ----------

@bp.route("/artists")
def artists():
    q = (request.args.get("q") or "").strip()
    query = (db.session.query(Artist, func.count(Release.id))
             .outerjoin(Release).group_by(Artist.id))
    if q:
        query = query.filter(Artist.name.ilike(f"%{q}%"))
    page = query.order_by(Artist.name).paginate(
        page=request.args.get("page", 1, type=int), per_page=50, error_out=False)
    return render_template("admin/artists.html", page=page, q=q)


@bp.route("/artists/new", methods=["GET", "POST"])
@bp.route("/artists/<int:artist_id>/edit", methods=["GET", "POST"])
def artist_form(artist_id=None):
    artist = db.get_or_404(Artist, artist_id) if artist_id else None
    form = ArtistForm(obj=artist)
    if form.validate_on_submit():
        if artist is None:
            artist = Artist()
            db.session.add(artist)
        name_changed = artist.name != form.name.data.strip()
        form.populate_obj(artist)
        artist.name = artist.name.strip()
        if name_changed or not artist.slug:
            artist.slug = unique_slug(Artist, artist.name, exclude_id=artist.id)
        db.session.commit()
        flash("Исполнитель сохранён.", "success")
        return redirect(url_for("artists.detail", slug=artist.slug))
    return render_template("admin/artist_form.html", form=form, artist=artist)


@bp.route("/artists/<int:artist_id>/delete", methods=["POST"])
def artist_delete(artist_id):
    artist = db.get_or_404(Artist, artist_id)
    if artist.releases.count():
        flash("Сначала удалите или перенесите релизы исполнителя.", "error")
    else:
        db.session.delete(artist)
        db.session.commit()
        flash("Исполнитель удалён.", "info")
    return redirect(url_for(".artists"))


# ---------- Пользователи и рецензии ----------

@bp.route("/users")
def users():
    q = (request.args.get("q") or "").strip()
    query = User.query
    if q:
        query = query.filter(User.username.ilike(f"%{q}%") | User.email.ilike(f"%{q}%"))
    page = query.order_by(User.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=50, error_out=False)
    return render_template("admin/users.html", page=page, q=q)


@bp.route("/users/<int:user_id>/role", methods=["POST"])
def user_role(user_id):
    user = db.get_or_404(User, user_id)
    role = request.form.get("role")
    if user.id == current_user.id:
        flash("Нельзя менять собственную роль.", "error")
    elif role in User.ROLES:
        user.role = role
        # роль влияет на разделение «слушатели / критики» — пересчитываем
        for release in Release.query.join(Review).filter(Review.user_id == user.id):
            release.recalc()
        db.session.commit()
        flash(f"{user.username}: роль «{user.role_label}».", "success")
    return redirect(request.referrer or url_for(".users"))


@bp.route("/reviews")
def reviews():
    page = Review.query.order_by(Review.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=50, error_out=False)
    return render_template("admin/reviews.html", page=page)


@bp.route("/reviews/<int:review_id>/delete", methods=["POST"])
def review_delete(review_id):
    review = db.get_or_404(Review, review_id)
    release = review.release
    db.session.delete(review)
    release.recalc()
    db.session.commit()
    flash("Оценка удалена.", "info")
    return redirect(request.referrer or url_for(".reviews"))
