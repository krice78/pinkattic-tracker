from decimal import Decimal

from app.models import Category, Item, User


def add_item(client, **overrides):
    data = {
        "name": "Vintage Lamp",
        "quantity": "1",
        "cost_price": "10.00",
    }
    data.update(overrides)
    return client.post("/items/add", data=data, follow_redirects=True)


def create_category(client, name="Home Decor"):
    return client.post("/categories/add", data={"name": name}, follow_redirects=True)


def test_list_categories_empty(logged_in_client):
    response = logged_in_client.get("/categories/")

    assert response.status_code == 200
    assert b"No categories yet" in response.data


def test_create_category(logged_in_client, db):
    response = create_category(logged_in_client, "Home Decor")

    assert response.status_code == 200
    category = Category.query.filter_by(name="Home Decor").first()
    assert category is not None


def test_create_category_duplicate_name_rejected(logged_in_client, db):
    create_category(logged_in_client, "Home Decor")
    create_category(logged_in_client, "Home Decor")

    assert Category.query.filter_by(name="Home Decor").count() == 1


def test_assign_category_to_item(logged_in_client, db):
    add_item(logged_in_client)
    create_category(logged_in_client, "Home Decor")

    item = Item.query.filter_by(name="Vintage Lamp").first()
    category = Category.query.filter_by(name="Home Decor").first()

    response = logged_in_client.post(f"/categories/assign/{item.id}", data={
        "category_id": str(category.id),
    }, follow_redirects=True)

    assert response.status_code == 200
    assert db.session.get(Item, item.id).category_id == category.id


def test_assign_category_none_clears_it(logged_in_client, db):
    add_item(logged_in_client)
    create_category(logged_in_client, "Home Decor")

    item = Item.query.filter_by(name="Vintage Lamp").first()
    category = Category.query.filter_by(name="Home Decor").first()

    logged_in_client.post(f"/categories/assign/{item.id}", data={
        "category_id": str(category.id),
    }, follow_redirects=True)
    assert db.session.get(Item, item.id).category_id == category.id

    logged_in_client.post(f"/categories/assign/{item.id}", data={
        "category_id": "0",
    }, follow_redirects=True)
    assert db.session.get(Item, item.id).category_id is None


def test_cannot_assign_category_to_other_users_item(logged_in_client, db):
    other = User(email="other@example.com")
    other.set_password("password123")
    db.session.add(other)
    db.session.commit()

    other_item = Item(user_id=other.id, name="Not Yours", quantity=1, cost_price=Decimal("5.00"))
    db.session.add(other_item)
    db.session.commit()

    create_category(logged_in_client, "Home Decor")
    category = Category.query.filter_by(name="Home Decor").first()

    response = logged_in_client.post(f"/categories/assign/{other_item.id}", data={
        "category_id": str(category.id),
    }, follow_redirects=True)

    assert response.status_code == 200
    assert db.session.get(Item, other_item.id).category_id is None


def test_categories_are_scoped_per_user(logged_in_client, db):
    create_category(logged_in_client, "Home Decor")

    other = User(email="other@example.com")
    other.set_password("password123")
    db.session.add(other)
    db.session.commit()
    db.session.add(Category(user_id=other.id, name="Jewelry"))
    db.session.commit()

    response = logged_in_client.get("/categories/")

    assert b"Home Decor" in response.data
    assert b"Jewelry" not in response.data
