from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..forms import PasswordForm, ProfileForm
from ..models import Release, Review, User

bp = Blueprint("users", __name__)

BUCKETS = [(0, 29, "до 30"), (30, 44, "30–44"), (45, 64, "45–64"), (65, 79, "65–79"), (80, 90, "80–90")]


@bp.route("/u/<username>")
def profile(username):
    user = User.query.filter(func.lower(User.username) == username.lower()).first_or_404()
    base = user.reviews.join(Release).filter(Release.status == "published")
    page = base.order_by(Review.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=20, error_out=False)

    total, avg, likes = (db.session.query(func.count(Review.id), func.avg(Review.score),
                                          func.coalesce(func.sum(Review.likes_count), 0))
                         .filter(Review.user_id == user.id).one())
    histogram = []
    for lo, hi, label in BUCKETS:
        n = user.reviews.filter(Review.score.between(lo, hi)).count()
        histogram.append((label, n))
    max_bucket = max((n for _, n in histogram), default=0) or 1
    return render_template("users/profile.html", user=user, page=page,
                           total=total, avg=round(float(avg), 1) if avg else None,
                           likes=likes, histogram=histogram, max_bucket=max_bucket)


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    profile_form = ProfileForm(obj=current_user, prefix="p")
    password_form = PasswordForm(prefix="pw")

    if request.method == "POST":
        if "p-submit" in request.form and profile_form.validate_on_submit():
            current_user.bio = (profile_form.bio.data or "").strip()
            current_user.avatar_url = (profile_form.avatar_url.data or "").strip()
            db.session.commit()
            flash("Профиль обновлён.", "success")
            return redirect(url_for(".settings"))
        if "pw-submit" in request.form and password_form.validate_on_submit():
            if not current_user.check_password(password_form.current.data):
                flash("Текущий пароль неверный.", "error")
            else:
                current_user.set_password(password_form.new.data)
                db.session.commit()
                flash("Пароль изменён.", "success")
                return redirect(url_for(".settings"))
    return render_template("users/settings.html", profile_form=profile_form,
                           password_form=password_form)
