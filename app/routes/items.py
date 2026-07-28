from decimal import Decimal
from datetime import datetime, UTC
from flask import Blueprint, redirect, url_for, flash, request, render_template
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, SubmitField, DateField
from wtforms.validators import DataRequired, NumberRange, Optional

from .. import db
from ..models import Item, Category
from .categories import AssignCategoryForm

items_bp = Blueprint("items", __name__, url_prefix="/items")


class ItemForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    quantity = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=1)], default=1)
    cost_price = DecimalField("Cost Price", validators=[DataRequired()], places=2)
    source = StringField("Source", validators=[Optional()])
    selling_price = DecimalField("Selling Price", validators=[Optional()], places=2)
    platform = StringField("Platform", validators=[Optional()])
    listing_id = StringField("Listing ID", validators=[Optional()])
    sku = StringField("SKU", validators=[Optional()])
    thumbnail_url = StringField("Thumbnail URL", validators=[Optional()])
    date_listed = DateField("Date Listed", validators=[Optional()])
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
        listing_id=form.listing_id.data.strip() if form.listing_id.data else None,
        sku=form.sku.data.strip() if form.sku.data else None,
        quantity=int(form.quantity.data),
        cost_price=Decimal(form.cost_price.data),
        source=form.source.data.strip() if form.source.data else None,
        selling_price=Decimal(form.selling_price.data) if form.selling_price.data is not None else None,
        platform=form.platform.data.strip() if form.platform.data else None,
        thumbnail_url=form.thumbnail_url.data.strip() if form.thumbnail_url.data else None,
        date_listed=form.date_listed.data if form.date_listed.data else None
    )

    db.session.add(item)
    db.session.commit()

    flash("Item added.", "success")
    return redirect(url_for("main.index"))

@items_bp.get("/edit/<int:item_id>")
@login_required
def edit_get(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash("You do not have permission to edit this item.", "danger")
        return redirect(url_for("main.index"))
    
    form = ItemForm()
    form.name.data = item.name
    form.quantity.data = item.quantity
    form.cost_price.data = item.cost_price
    form.source.data = item.source
    form.selling_price.data = item.selling_price
    form.platform.data = item.platform
    form.listing_id.data = item.listing_id
    form.sku.data = item.sku
    form.thumbnail_url.data = item.thumbnail_url
    form.date_listed.data = item.date_listed

    category_form = AssignCategoryForm()
    category_form.category_id.choices = [(0, "-- None --")] + [
        (c.id, c.name) for c in Category.query.filter_by(user_id=current_user.id).order_by(Category.name).all()
    ]
    category_form.category_id.data = item.category_id or 0

    return render_template("edit_item.html", form=form, item=item, category_form=category_form)


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
    item.listing_id = form.listing_id.data.strip() if form.listing_id.data else None
    item.sku = form.sku.data.strip() if form.sku.data else None
    item.thumbnail_url = form.thumbnail_url.data.strip() if form.thumbnail_url.data else None
    item.date_listed = form.date_listed.data if form.date_listed.data else None
    
    db.session.commit()
    flash("Item updated.", "success")
    return redirect(url_for("main.index"))


@items_bp.post("/delete/<int:item_id>")
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


@items_bp.post("/mark-sold/<int:item_id>")
@login_required
def mark_sold(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash("You do not have permission to modify this item.", "danger")
        return redirect(url_for("main.index"))
    
    item.sold = not item.sold
    if item.sold:
        item.sold_date = datetime.now(UTC)
        flash("Item marked as sold.", "success")
    else:
        item.sold_date = None
        flash("Item marked as in stock.", "success")
    
    db.session.commit()
    return redirect(url_for("main.index"))