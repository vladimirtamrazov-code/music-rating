from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import (BooleanField, DateField, IntegerField, PasswordField,
                     SelectField, StringField, TextAreaField)
from wtforms.validators import (DataRequired, Email, EqualTo, Length,
                                NumberRange, Optional, Regexp, ValidationError)

from .models import Release, User
from .scoring import MAX_POINTS, MIN_POINTS


def http_url(form, field):
    if field.data and not field.data.lower().startswith(("http://", "https://")):
        raise ValidationError("Ссылка должна начинаться с http:// или https://")


class RegisterForm(FlaskForm):
    username = StringField("Никнейм", validators=[
        DataRequired(), Length(3, 32),
        Regexp(r"^[A-Za-z0-9_.-]+$", message="Только латиница, цифры, «_», «.» и «-»"),
    ])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Пароль", validators=[DataRequired(), Length(8, 128)])
    password2 = PasswordField("Повторите пароль", validators=[
        DataRequired(), EqualTo("password", message="Пароли не совпадают"),
    ])

    def validate_username(self, field):
        if User.query.filter(func.lower(User.username) == field.data.lower()).first():
            raise ValidationError("Этот никнейм уже занят")

    def validate_email(self, field):
        if User.query.filter(func.lower(User.email) == field.data.lower()).first():
            raise ValidationError("Этот email уже зарегистрирован")


class LoginForm(FlaskForm):
    login = StringField("Никнейм или email", validators=[DataRequired(), Length(max=120)])
    password = PasswordField("Пароль", validators=[DataRequired()])
    remember = BooleanField("Запомнить меня", default=True)


def _points_field(label):
    return IntegerField(label, default=5, validators=[
        DataRequired(), NumberRange(MIN_POINTS, MAX_POINTS)])


class ReviewForm(FlaskForm):
    rhymes = _points_field("Рифмы и образы")
    structure = _points_field("Структура и ритмика")
    style = _points_field("Реализация стиля")
    charisma = _points_field("Индивидуальность и харизма")
    vibe = _points_field("Атмосфера и вайб")
    text = TextAreaField("Рецензия (необязательно)", validators=[Optional(), Length(max=5000)])


class ReleaseForm(FlaskForm):
    artist = StringField("Исполнитель", validators=[DataRequired(), Length(max=120)])
    feat = StringField("Гости (feat.)", validators=[Optional(), Length(max=200)])
    title = StringField("Название", validators=[DataRequired(), Length(max=200)])
    type = SelectField("Тип", choices=list(Release.TYPES.items()))
    genre = SelectField("Жанр", choices=[(g, g) for g in Release.GENRES])
    release_date = DateField("Дата выхода", validators=[Optional()])
    cover_url = StringField("Ссылка на обложку", validators=[Optional(), Length(max=500), http_url])
    description = TextAreaField("Описание", validators=[Optional(), Length(max=5000)])
    tracklist = TextAreaField("Треклист (по треку в строке)", validators=[Optional(), Length(max=5000)])


class AdminReleaseForm(ReleaseForm):
    status = SelectField("Статус", choices=list(Release.STATUSES.items()))


class ArtistForm(FlaskForm):
    name = StringField("Имя", validators=[DataRequired(), Length(max=120)])
    photo_url = StringField("Ссылка на фото", validators=[Optional(), Length(max=500), http_url])
    bio = TextAreaField("Описание", validators=[Optional(), Length(max=5000)])


class ProfileForm(FlaskForm):
    avatar_url = StringField("Ссылка на аватар", validators=[Optional(), Length(max=500), http_url])
    bio = TextAreaField("О себе", validators=[Optional(), Length(max=1000)])


class PasswordForm(FlaskForm):
    current = PasswordField("Текущий пароль", validators=[DataRequired()])
    new = PasswordField("Новый пароль", validators=[DataRequired(), Length(8, 128)])
    new2 = PasswordField("Повторите новый пароль", validators=[
        DataRequired(), EqualTo("new", message="Пароли не совпадают"),
    ])
