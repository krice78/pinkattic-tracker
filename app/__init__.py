from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

login_manager.login_view = "auth.login_get"


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = "dev-key-change-later"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pinkattic.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Blueprints
    from .routes.auth import auth_bp
    app.register_blueprint(auth_bp)
    
    from .routes.items import items_bp
    app.register_blueprint(items_bp)

    # Main blueprint
    from flask import Blueprint
    main_bp = Blueprint("main", __name__)

    @main_bp.get("/")
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login_get"))
        
        from .models import Item
        from .routes.items import ItemForm
        
        form = ItemForm()
        items = Item.query.filter_by(user_id=current_user.id).all()
        total_profit = sum(item.total_profit for item in items)
        total_invested = sum(float(item.cost_price) * item.quantity for item in items if not item.sold)
        items_sold = sum(1 for item in items if item.sold)
        
        return render_template("dashboard.html", 
                             items=items,
                             total_profit=total_profit,
                             total_invested=total_invested,
                             items_sold=items_sold
                             form=form)
        
    @main_bp.get("/login")
    def login_alias():
        return redirect(url_for("auth.login_get"))

    @main_bp.get("/dashboard")
    def dashboard_alias():
        return redirect(url_for("main.index"))

    app.register_blueprint(main_bp)
    
    

    return app