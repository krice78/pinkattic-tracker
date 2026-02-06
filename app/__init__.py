from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

login_manager.login_view = "auth.login_get"  # where to send users if not logged in


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

    # Simple main blueprint so redirects work
    from flask import Blueprint, render_template
    from flask_login import current_user

    main_bp = Blueprint("main", __name__)

    @main_bp.get("/")
    def index():
        return render_template("index.html")

    app.register_blueprint(main_bp)

    return app
