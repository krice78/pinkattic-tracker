from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo

from .. import db
from ..models import User


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


@auth_bp.get("/register")
def register_get():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegisterForm()
    return render_template("auth/register.html", form=form)


@auth_bp.post("/register")
def register_post():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegisterForm()
    if not form.validate_on_submit():
        return render_template("auth/register.html", form=form)

    email = form.email.data.strip().lower()

    existing = User.query.filter_by(email=email).first()
    if existing:
        flash("That email is already registered. Please log in.", "warning")
        return redirect(url_for("auth.login_get"))

    user = User(email=email)
    user.set_password(form.password.data)

    db.session.add(user)
    db.session.commit()

    login_user(user)
    flash("Account created! You’re logged in.", "success")
    return redirect(url_for("main.index"))


@auth_bp.get("/login")
def login_get():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    return render_template("auth/login.html", form=form)


@auth_bp.post("/login")
def login_post():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if not form.validate_on_submit():
        return render_template("auth/login.html", form=form)

    email = form.email.data.strip().lower()
    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(form.password.data):
        flash("Invalid email or password.", "danger")
        return render_template("auth/login.html", form=form)

    login_user(user)
    next_url = request.args.get("next")
    flash("Welcome back!", "success")
    return redirect(next_url or url_for("main.index"))


@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("auth.login_get"))
