from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length

from .. import db
from ..models import Category, Item

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")


class CategoryForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=255)])
    submit = SubmitField("Add Category")


class AssignCategoryForm(FlaskForm):
    category_id = SelectField("Category", coerce=int)
    submit = SubmitField("Assign")


def _user_categories():
    return Category.query.filter_by(user_id=current_user.id).order_by(Category.name).all()


@categories_bp.get("/")
@login_required
def list_categories():
    form = CategoryForm()
    return render_template("categories.html", categories=_user_categories(), form=form)


@categories_bp.post("/add")
@login_required
def create_category():
    form = CategoryForm()
    if not form.validate_on_submit():
        flash("Please correct the errors in the form.", "warning")
        return redirect(url_for("categories.list_categories"))

    name = form.name.data.strip()
    existing = Category.query.filter_by(user_id=current_user.id, name=name).first()
    if existing:
        flash("You already have a category with that name.", "warning")
        return redirect(url_for("categories.list_categories"))

    category = Category(user_id=current_user.id, name=name)
    db.session.add(category)
    db.session.commit()

    flash("Category added.", "success")
    return redirect(url_for("categories.list_categories"))


@categories_bp.post("/assign/<int:item_id>")
@login_required
def assign_category(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash("You do not have permission to modify this item.", "danger")
        return redirect(url_for("main.index"))

    form = AssignCategoryForm()
    form.category_id.choices = [(0, "-- None --")] + [(c.id, c.name) for c in _user_categories()]

    if not form.validate_on_submit():
        flash("Please choose a valid category.", "warning")
        return redirect(url_for("items.edit_get", item_id=item.id))

    item.category_id = form.category_id.data or None
    db.session.commit()

    flash("Category updated.", "success")
    return redirect(url_for("items.edit_get", item_id=item.id))
