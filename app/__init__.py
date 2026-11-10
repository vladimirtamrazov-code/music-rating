import logging

from flask import Flask, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import csrf, db, login_manager
from .scoring import ALL_CRITERIA, CRITERIA, MAX_SCORE, VIBE, score_tier
from .utils import plural, ru_date

log = logging.getLogger(__name__)


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    # Render проксирует запросы — доверяем одному прокси для схемы/хоста
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from .views import admin, api, artists, auth, main, releases, users
    for bp in (main.bp, auth.bp, releases.bp, artists.bp, users.bp, admin.bp, api.bp):
        app.register_blueprint(bp)

    _register_template_helpers(app)
    _register_error_handlers(app)

    from . import cli
    cli.register(app)

    with app.app_context():
        _init_database(app)

    return app


def _init_database(app: Flask) -> None:
    from .bootstrap import ensure_admin, seed_demo
    db.create_all()
    ensure_admin(app)
    if app.config["SEED_DEMO"]:
        seed_demo()
    # При gunicorn --preload соединения мастер-процесса не должны попасть в воркеры
    # (in-memory SQLite в тестах при этом потерял бы данные — его не трогаем)
    if db.engine.dialect.name != "sqlite":
        db.engine.dispose()


def _register_template_helpers(app: Flask) -> None:
    from .models import Release

    @app.context_processor
    def inject_globals():
        return {
            "site_name": app.config["SITE_NAME"],
            "CRITERIA": CRITERIA,
            "VIBE": VIBE,
            "ALL_CRITERIA": ALL_CRITERIA,
            "MAX_SCORE": MAX_SCORE,
            "RELEASE_TYPES": Release.TYPES,
            "GENRES": Release.GENRES,
        }

    app.jinja_env.filters["tier"] = score_tier
    app.jinja_env.filters["ru_date"] = ru_date
    app.jinja_env.globals["plural"] = plural

    @app.template_global()
    def page_url(page_num: int) -> str:
        """Ссылка на ту же страницу с другим номером страницы пагинации."""
        args = request.args.to_dict()
        args["page"] = page_num
        return url_for(request.endpoint, **(request.view_args or {}), **args)

    @app.template_filter("score")
    def fmt_score(value):
        if value is None:
            return "—"
        return f"{value:.0f}" if float(value).is_integer() else f"{value:.1f}"


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(_):
        return render_template("errors/error.html", code=403,
                               message="Доступ запрещён"), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template("errors/error.html", code=404,
                               message="Страница не найдена"), 404

    @app.errorhandler(500)
    def server_error(_):
        db.session.rollback()
        return render_template("errors/error.html", code=500,
                               message="Что-то пошло не так. Мы уже разбираемся."), 500
