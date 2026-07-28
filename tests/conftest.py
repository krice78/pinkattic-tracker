import pytest

from app import create_app, db as _db


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-key",
    })

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


def register(client, email="user@example.com", password="password123"):
    return client.post("/auth/register", data={
        "email": email,
        "password": password,
        "confirm_password": password,
    }, follow_redirects=True)


@pytest.fixture
def logged_in_client(client):
    register(client)
    return client
