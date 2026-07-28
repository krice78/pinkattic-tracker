import csv
import io
import os
import re
import uuid
from datetime import datetime, UTC
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
    ("cost_price", "Cost Price", False),
    ("quantity", "Quantity", False),
    ("selling_price", "Selling Price", False),
    ("source", "Source", False),
    ("platform", "Platform", False),
    ("sku", "SKU", False),
    ("listing_id", "Listing ID", False),
    ("thumbnail_url", "Thumbnail URL", False),
    ("date_listed", "Date Listed", False),
    ("sold_date", "Sold Date", False),
    ("category", "Category", False),
]

# Matched against the uploaded filename (case-insensitive) to guess the
# platform when the CSV itself has no platform column - most marketplace
# exports are single-platform, so the filename is usually a reliable signal.
PLATFORM_FILENAME_KEYWORDS = {
    "ebay": "eBay",
    "etsy": "Etsy",
    "poshmark": "Poshmark",
    "mercari": "Mercari",
    "depop": "Depop",
    "vinted": "Vinted",
    "offerup": "OfferUp",
    "whatnot": "Whatnot",
    "grailed": "Grailed",
    "facebook": "Facebook Marketplace",
}


def _guess_platform_from_filename(filename):
    if not filename:
        return None
    lowered = filename.lower()
    for keyword, display_name in PLATFORM_FILENAME_KEYWORDS.items():
        if keyword in lowered:
            return display_name
    return None


# Common column names (case/punctuation-insensitive) for each field, checked
# in priority order, used to pre-select a likely mapping. Always overridable
# via the dropdown - this only saves re-picking the obvious ones every time.
FIELD_ALIASES = {
    "name": ["name", "item name", "title", "item title", "product name", "product"],
    "cost_price": ["cost price", "cost", "purchase price", "price paid", "what i paid", "item cost"],
    "quantity": ["quantity", "qty"],
    "selling_price": ["sold for", "selling price", "sale price", "price sold", "amount sold"],
    "source": ["source", "purchased from", "where bought"],
    "platform": ["platform", "marketplace", "site"],
    "sku": ["sku", "custom label", "custom sku"],
    "listing_id": ["listing id", "item number", "item id"],
    "thumbnail_url": ["thumbnail", "thumbnail url", "image", "image url", "photo", "photo url"],
    "date_listed": ["date listed", "listed date", "list date"],
    "sold_date": ["sold date", "sale date", "date sold"],
    "category": ["category", "item category", "type"],
}


def _normalize_header(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _guess_mapping(headers):
    normalized_to_header = {_normalize_header(h): h for h in headers}
    guesses = {}
    for field_key, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            match = normalized_to_header.get(alias)
            if match:
                guesses[field_key] = match
                break
    return guesses


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


DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%b-%d-%y",  # eBay's report format, e.g. "May-09-26"
    "%b-%d-%Y",
)


def _parse_date(raw):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def parse_row(headers, row, mapping, default_platform=None, mark_sold=False):
    """Map one CSV row to Item kwargs using a {item_field: csv_column} mapping.

    Returns (kwargs, errors). kwargs always has all mappable keys (None when
    blank/unmapped); errors is a list of human-readable problems with the row.
    kwargs["category_name"] is not an Item field - callers resolve/create the
    Category separately. default_platform fills in "platform" when no column
    is mapped to it (or the cell is blank) - typically guessed from the
    uploaded filename, since most marketplace exports are single-platform.
    mark_sold marks every row sold=True, using a mapped Sold Date column when
    present and today otherwise - for importing a platform's "sold"/"orders"
    report, where every row is by definition already sold.
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
        # eBay/Etsy/Poshmark exports don't track what you paid - default to $0
        # and let the user fill it in later from the edit item page.
        kwargs["cost_price"] = Decimal("0.00")
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
        parsed_date = _parse_date(date_raw)
        if parsed_date is None:
            errors.append(f"Date listed '{date_raw}' is not a recognized date (try YYYY-MM-DD, MM/DD/YYYY, or Mon-DD-YY).")
        kwargs["date_listed"] = parsed_date

    if mark_sold:
        sold_date_raw = get("sold_date")
        if sold_date_raw is None:
            kwargs["sold_date"] = datetime.now(UTC)
        else:
            parsed_sold_date = _parse_date(sold_date_raw)
            if parsed_sold_date is None:
                errors.append(f"Sold date '{sold_date_raw}' is not a recognized date (try YYYY-MM-DD, MM/DD/YYYY, or Mon-DD-YY).")
            kwargs["sold_date"] = parsed_sold_date or datetime.now(UTC)
        kwargs["sold"] = True
    else:
        kwargs["sold"] = False
        kwargs["sold_date"] = None

    kwargs["source"] = get("source")
    kwargs["platform"] = get("platform") or default_platform
    kwargs["sku"] = get("sku")
    kwargs["listing_id"] = get("listing_id")
    kwargs["thumbnail_url"] = get("thumbnail_url")
    kwargs["category_name"] = get("category")

    return kwargs, errors


def _decode_csv(raw_bytes):
    if raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff"):
        return raw_bytes.decode("utf-16")
    return raw_bytes.decode("utf-8-sig", errors="replace")


def _cleanup_import():
    import_id = session.pop("import_id", None)
    session.pop("import_headers", None)
    session.pop("import_mapping", None)
    session.pop("import_platform_default", None)
    session.pop("import_mark_sold", None)
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

    raw = _decode_csv(form.csv_file.data.read())
    rows = list(csv.reader(io.StringIO(raw)))

    skipped_blank_rows = 0
    while rows and not any(cell.strip() for cell in rows[0]):
        rows.pop(0)
        skipped_blank_rows += 1

    if not rows:
        flash("That CSV file appears to be empty.", "warning")
        return redirect(url_for("importers.upload_get"))

    import_id = uuid.uuid4().hex
    with open(_import_path(import_id), "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)

    session["import_id"] = import_id
    session["import_headers"] = rows[0]
    session["import_platform_default"] = _guess_platform_from_filename(form.csv_file.data.filename)
    session.pop("import_mapping", None)

    if skipped_blank_rows:
        flash(f"Skipped {skipped_blank_rows} blank row(s) before the header row.", "info")

    return redirect(url_for("importers.map_get"))


@importers_bp.get("/map")
@login_required
def map_get():
    if not session.get("import_id") or not session.get("import_headers"):
        flash("Please upload a CSV file first.", "warning")
        return redirect(url_for("importers.upload_get"))

    return render_template(
        "import_map.html",
        headers=session["import_headers"],
        fields=MAPPABLE_FIELDS,
        mapping_guess=_guess_mapping(session["import_headers"]),
        platform_default=session.get("import_platform_default") or "",
    )


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
    session["import_platform_default"] = request.form.get("default_platform", "").strip() or None
    session["import_mark_sold"] = request.form.get("mark_sold") == "on"
    return redirect(url_for("importers.preview_get"))


@importers_bp.get("/preview")
@login_required
def preview_get():
    import_id = session.get("import_id")
    mapping = session.get("import_mapping")
    if not import_id or not mapping:
        flash("Please upload and map a CSV file first.", "warning")
        return redirect(url_for("importers.upload_get"))

    default_platform = session.get("import_platform_default")
    mark_sold = session.get("import_mark_sold", False)
    headers, data_rows = _read_rows(import_id)
    previews = []
    valid_count = 0
    for line_number, row in enumerate(data_rows, start=2):  # header is line 1
        kwargs, errors = parse_row(headers, row, mapping, default_platform=default_platform, mark_sold=mark_sold)
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

    default_platform = session.get("import_platform_default")
    mark_sold = session.get("import_mark_sold", False)
    headers, data_rows = _read_rows(import_id)

    category_cache = {c.name.lower(): c for c in Category.query.filter_by(user_id=current_user.id).all()}

    imported = 0
    skipped = 0
    for row in data_rows:
        kwargs, errors = parse_row(headers, row, mapping, default_platform=default_platform, mark_sold=mark_sold)
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
