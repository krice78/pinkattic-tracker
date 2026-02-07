from decimal import Decimal
from flask import Blueprint, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional

from .. import db
from ..models import Item

items_bp = Blueprint("items", __name__, url_prefix="/items")


class ItemForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    quantity = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=1)], default=1)
    cost_price = DecimalField("Cost Price", validators=[DataRequired()], places=2)
    selling_price = DecimalField("Selling Price", validators=[Optional()], places=2)
    submit = SubmitField("Add Item")


@items_bp.post("/add")
@login_required
def add_item():
    form = ItemForm()
    if not form.validate_on_submit():
        flash("Please correct the errors in the form.", "warning")
        return redirect(url_for("main.index"))

    item = Item(
        user_id=current_user.id,
        name=form.name.data.strip(),
        quantity=int(form.quantity.data),
        cost_price=Decimal(form.cost_price.data),
        selling_price=Decimal(form.selling_price.data) if form.selling_price.data is not None else None
    )

    db.session.add(item)
    db.session.commit()

    flash("Item added.", "success")
    return redirect(url_for("main.index"))