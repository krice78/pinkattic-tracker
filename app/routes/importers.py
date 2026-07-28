import csv
import io
import os
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import SubmitField

from .. import db
from ..models import Category, Item

importers_bp = Blueprint("importers", __name__, url_prefix="/import")

IMPORT_DIR_NAME = "imports"

# (item_field, label, required)
MAPPABLE_FIELDS = [
    ("name", "Name", True),
    ("cost_price", "Cost Price", True),
    ("quantity", "Quantity", False),
    ("selling_price", "Selling Price", False),
    ("source", "Source", False),
    ("platform", "Platform", False),
    ("sku", "SKU", False),
    ("listing_id", "Listing ID", False),
    ("thumbnail_url", "Thumbnail URL", False),
    ("date_listed", "Date Listed", False),
    ("category", "Category", False),
]


class UploadForm(FlaskForm):
    csv_file = FileField("CSV File", validators=[FileRequired(), FileAllowed(["csv"], "CSV files only.")])
    submit = SubmitField("Upload")


def _import_dir():
    path = os.path.join(current_app.instance_path, IMPORT_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def _import_path(import_id):
    return os.path.join(_import_dir(), f"{import_id}.csv")


def _read_rows(import_id):
    with open(_import_path(import_id), newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return [], []
    return rows[0], rows[1:]


def parse_row(headers, row, mapping):
    """Map one CSV row to Item kwargs using a {item_field: csv_column} mapping.

    Returns (kwargs, errors). kwargs always has all mappable keys (None when
    blank/unmapped); errors is a list of human-readable problems with the row.
    kwargs["category_name"] is not an Item field - callers resolve/create the
    Category separately.
    """
    values = dict(zip(headers, row))
    errors = []
    kwargs = {}

    def get(field):
        column = mapping.get(field)
        if not column:
            return None
        return (values.get(column) or "").strip() or None

    name = get("name")
    if not name:
        errors.append("Name is required.")
    kwargs["name"] = name

    cost_raw = get("cost_price")
    if not cost_raw:
        errors.append("Cost price is required.")
        kwargs["cost_price"] = None
    else:
        try:
            kwargs["cost_price"] = Decimal(cost_raw.replace("$", "").replace(",", ""))
        except InvalidOperation:
            errors.append(f"Cost price '{cost_raw}' is not a valid number.")
            kwargs["cost_price"] = None

    quantity_raw = get("quantity")
    if quantity_raw is None:
        kwargs["quantity"] = 1
    else:
        try:
            kwargs["quantity"] = int(quantity_raw)
        except ValueError:
            errors.append(f"Quantity '{quantity_raw}' is not a whole number.")
            kwargs["quantity"] = None

    selling_price_raw = get("selling_price")
    if selling_price_raw is None:
        kwargs["selling_price"] = None
    else:
        try:
            kwargs["selling_price"] = Decimal(selling_price_raw.replace("$", "").replace(",", ""))
        except InvalidOperation:
            errors.append(f"Selling price '{selling_price_raw}' is not a valid number.")
            kwargs["selling_price"] = None

    date_raw = get("date_listed")
    if date_raw is None:
        kwargs["date_listed"] = None
    else:
        parsed_date = None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                parsed_date = datetime.strptime(date_raw, fmt)
                break
            except ValueError:
                continue
        if parsed_date is None:
            errors.append(f"Date listed '{date_raw}' is not a recognized date (use YYYY-MM-DD or MM/DD/YYYY).")
        kwargs["date_listed"] = parsed_date

    kwargs["source"] = get("source")
    kwargs["platform"] = get("platform")
    kwargs["sku"] = get("sku")
    kwargs["listing_id"] = get("listing_id")
    kwargs["thumbnail_url"] = get("thumbnail_url")
    kwargs["category_name"] = get("category")

    return kwargs, errors


def _cleanup_import():
    import_id = session.pop("import_id", None)
    session.pop("import_headers", None)
    session.pop("import_mapping", None)
    if import_id:
        path = _import_path(import_id)
        if os.path.exists(path):
            os.remove(path)


@importers_bp.get("/")
@login_required
def upload_get():
    form = UploadForm()
    return render_template("import_upload.html", form=form)


@importers_bp.post("/upload")
@login_required
def upload_post():
    form = UploadForm()
    if not form.validate_on_submit():
        flash("Please choose a valid CSV file.", "warning")
        return redirect(url_for("importers.upload_get"))

    raw = form.csv_file.data.read().decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(raw)))
    if not rows or not rows[0]:
        flash("That CSV file appears to be empty.", "warning")
        return redirect(url_for("importers.upload_get"))

    import_id = uuid.uuid4().hex
    with open(_import_path(import_id), "w", newline="", encoding="utf-8") as f:
        f.write(raw)

    session["import_id"] = import_id
    session["import_headers"] = rows[0]
    session.pop("import_mapping", None)

    return redirect(url_for("importers.map_get"))


@importers_bp.get("/map")
@login_required
def map_get():
    if not session.get("import_id") or not session.get("import_headers"):
        flash("Please upload a CSV file first.", "warning")
        return redirect(url_for("importers.upload_get"))

    return render_template("import_map.html", headers=session["import_headers"], fields=MAPPABLE_FIELDS)


@importers_bp.post("/map")
@login_required
def map_post():
    if not session.get("import_id") or not session.get("import_headers"):
        flash("Please upload a CSV file first.", "warning")
        return redirect(url_for("importers.upload_get"))

    mapping = {}
    for field_key, _label, _required in MAPPABLE_FIELDS:
        column = request.form.get(f"map_{field_key}", "").strip()
        if column:
            mapping[field_key] = column

    missing_required = [label for key, label, required in MAPPABLE_FIELDS if required and key not in mapping]
    if missing_required:
        flash(f"Please map required fields: {', '.join(missing_required)}.", "warning")
        return redirect(url_for("importers.map_get"))

    session["import_mapping"] = mapping
    return redirect(url_for("importers.preview_get"))


@importers_bp.get("/preview")
@login_required
def preview_get():
    import_id = session.get("import_id")
    mapping = session.get("import_mapping")
    if not import_id or not mapping:
        flash("Please upload and map a CSV file first.", "warning")
        return redirect(url_for("importers.upload_get"))

    headers, data_rows = _read_rows(import_id)
    previews = []
    valid_count = 0
    for line_number, row in enumerate(data_rows, start=2):  # header is line 1
        kwargs, errors = parse_row(headers, row, mapping)
        if not errors:
            valid_count += 1
        previews.append({"line": line_number, "kwargs": kwargs, "errors": errors})

    return render_template("import_preview.html", previews=previews, valid_count=valid_count, total_count=len(previews))


@importers_bp.post("/confirm")
@login_required
def confirm_post():
    import_id = session.get("import_id")
    mapping = session.get("import_mapping")
    if not import_id or not mapping:
        flash("Please upload and map a CSV file first.", "warning")
        return redirect(url_for("importers.upload_get"))

    headers, data_rows = _read_rows(import_id)

    category_cache = {c.name.lower(): c for c in Category.query.filter_by(user_id=current_user.id).all()}

    imported = 0
    skipped = 0
    for row in data_rows:
        kwargs, errors = parse_row(headers, row, mapping)
        if errors:
            skipped += 1
            continue

        category_name = kwargs.pop("category_name", None)
        category_id = None
        if category_name:
            category = category_cache.get(category_name.lower())
            if not category:
                category = Category(user_id=current_user.id, name=category_name)
                db.session.add(category)
                db.session.flush()
                category_cache[category_name.lower()] = category
            category_id = category.id

        db.session.add(Item(user_id=current_user.id, category_id=category_id, **kwargs))
        imported += 1

    db.session.commit()
    _cleanup_import()

    flash(f"Imported {imported} item(s). Skipped {skipped} invalid row(s).", "success")
    return redirect(url_for("main.index"))


@importers_bp.post("/cancel")
@login_required
def cancel_post():
    _cleanup_import()
    flash("Import canceled.", "info")
    return redirect(url_for("importers.upload_get"))
