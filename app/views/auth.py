from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, or_

from ..extensions import db
from ..forms import LoginForm, RegisterForm
from ..models import User
from ..utils import is_safe_next

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _redirect_next():
    nxt = request.args.get("next")
    return redirect(nxt if is_safe_next(nxt) else url_for("main.index"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data.lower())
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        flash(f"Добро пожаловать, {user.username}! Можно оценивать релизы.", "success")
        return _redirect_next()
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        login = form.login.data.strip().lower()
        user = User.query.filter(or_(func.lower(User.username) == login,
                                     func.lower(User.email) == login)).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash("Вы вошли.", "success")
            return _redirect_next()
        flash("Неверный логин или пароль.", "error")
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Вы вышли из аккаунта.", "info")
    return redirect(url_for("main.index"))
