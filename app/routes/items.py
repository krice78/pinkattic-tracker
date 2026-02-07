from decimal import Decimal
from flask import Blueprint, redirect, url_for, flash, request, render_template
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
    source = StringField("Source", validators=[Optional()])
    selling_price = DecimalField("Selling Price", validators=[Optional()], places=2)
    platform = StringField("Platform", validators=[Optional()])
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
        source=form.source.data.strip() if form.source.data else None,
        selling_price=Decimal(form.selling_price.data) if form.selling_price.data is not None else None,
        platform=form.platform.data.strip() if form.platform.data else None
    )

    db.session.add(item)
    db.session.commit()

    flash("Item added.", "success")
    return redirect(url_for("main.index"))

@items_bp.post("/edit/<int:item_id>")
@login_required
def edit_post(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash("You do not have permission to edit this item.", "danger")
        return redirect(url_for("main.index"))
    
    form = ItemForm()
    if not form.validate_on_submit():
        flash("Please correct the errors in the form.", "warning")
        return render_template("edit_item.html", form=form, item=item)
    
    item.name = form.name.data.strip()
    item.quantity = int(form.quantity.data)
    item.cost_price = Decimal(form.cost_price.data)
    item.source = form.source.data.strip() if form.source.data else None
    item.platform = form.platform.data.strip() if form.platform.data else None
    item.selling_price = Decimal(form.selling_price.data) if form.selling_price.data is not None else None
    
    db.session.commit()
    flash("Item updated.", "success")
    return redirect(url_for("main.index"))


@items_bp.post("/delete<int:item_id>/delete")
@login_required
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash("You do not have permission to delete this item.", "danger")
        return redirect(url_for("main.index"))
    
    db.session.delete(item)
    db.session.commit()
    flash("Item deleted.", "success")
    return redirect(url_for("main.index"))