from datetime import datetime, UTC
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    
    # Relationships
    categories = db.relationship("Category", back_populates="user", cascade="all, delete-orphan")
    items = db.relationship("Item", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    
    # Relationships
    user = db.relationship("User", back_populates="categories")
    items = db.relationship("Item", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Category {self.name}>"

# may want to add db column for fees or notes later
class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    cost_price = db.Column(db.Numeric(10, 2), nullable=False)  # What you paid
    selling_price = db.Column(db.Numeric(10, 2), nullable=True)  # What you're selling for
    platform = db.Column(db.String(255), nullable=True)  # Etsy eBay, Poshmark, etc
    sold = db.Column(db.Boolean, default=False)
    sold_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    
    # Relationships
    user = db.relationship("User", back_populates="items")
    category = db.relationship("Category", back_populates="items")

    @property
    def profit_per_item(self):
        if self.selling_price:
            return float(self.selling_price) - float(self.cost_price)
        return 0

    @property
    def total_profit(self):
        if self.sold and self.selling_price:
            return self.profit_per_item * self.quantity
        return 0

    def __repr__(self):
        return f"<Item {self.name}>"


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))