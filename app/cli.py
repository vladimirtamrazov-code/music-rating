import click
from flask import Flask

from .bootstrap import seed_demo
from .extensions import db
from .models import Release, User


def register(app: Flask) -> None:
    @app.cli.command("create-admin")
    @click.argument("username")
    @click.argument("email")
    @click.password_option()
    def create_admin(username, email, password):
        """Создать администратора (или выдать роль существующему)."""
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, email=email)
            db.session.add(user)
        user.role = "admin"
        user.set_password(password)
        db.session.commit()
        click.echo(f"Администратор {username} готов.")

    @app.cli.command("seed")
    def seed():
        """Заполнить пустую базу демо-данными."""
        seed_demo()
        click.echo("Готово.")

    @app.cli.command("recalc")
    def recalc():
        """Пересчитать средние оценки всех релизов."""
        for r in Release.query.all():
            r.recalc()
        db.session.commit()
        click.echo("Пересчитано.")
