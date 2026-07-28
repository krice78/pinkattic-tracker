from decimal import Decimal

from app.models import Item, User


def add_item(client, **overrides):
    data = {
        "name": "Vintage Lamp",
        "quantity": "1",
        "cost_price": "10.00",
        "source": "Thrift store",
        "selling_price": "25.00",
        "platform": "Etsy",
    }
    data.update(overrides)
    return client.post("/items/add", data=data, follow_redirects=True)


def test_add_item_creates_item(logged_in_client, db):
    response = add_item(logged_in_client)

    assert response.status_code == 200
    item = Item.query.filter_by(name="Vintage Lamp").first()
    assert item is not None
    assert item.quantity == 1
    assert item.cost_price == Decimal("10.00")
    assert item.selling_price == Decimal("25.00")
    assert item.platform == "Etsy"


def test_edit_item_updates_fields(logged_in_client, db):
    add_item(logged_in_client)
    item = Item.query.filter_by(name="Vintage Lamp").first()

    response = logged_in_client.post(f"/items/edit/{item.id}", data={
        "name": "Vintage Lamp (repainted)",
        "quantity": "2",
        "cost_price": "12.50",
        "source": "Thrift store",
        "selling_price": "30.00",
        "platform": "eBay",
    }, follow_redirects=True)

    assert response.status_code == 200
    updated = db.session.get(Item, item.id)
    assert updated.name == "Vintage Lamp (repainted)"
    assert updated.quantity == 2
    assert updated.cost_price == Decimal("12.50")
    assert updated.platform == "eBay"


def test_delete_item_removes_it(logged_in_client, db):
    add_item(logged_in_client)
    item = Item.query.filter_by(name="Vintage Lamp").first()

    response = logged_in_client.post(f"/items/delete/{item.id}", follow_redirects=True)

    assert response.status_code == 200
    assert db.session.get(Item, item.id) is None


def test_mark_sold_toggles_status(logged_in_client, db):
    add_item(logged_in_client)
    item = Item.query.filter_by(name="Vintage Lamp").first()
    assert item.sold is False

    logged_in_client.post(f"/items/mark-sold/{item.id}", follow_redirects=True)
    assert db.session.get(Item, item.id).sold is True

    logged_in_client.post(f"/items/mark-sold/{item.id}", follow_redirects=True)
    assert db.session.get(Item, item.id).sold is False


def test_cannot_edit_other_users_item(logged_in_client, db):
    other = User(email="other@example.com")
    other.set_password("password123")
    db.session.add(other)
    db.session.commit()

    other_item = Item(user_id=other.id, name="Not Yours", quantity=1, cost_price=Decimal("5.00"))
    db.session.add(other_item)
    db.session.commit()

    response = logged_in_client.post(f"/items/edit/{other_item.id}", data={
        "name": "Hijacked",
        "quantity": "1",
        "cost_price": "5.00",
    }, follow_redirects=True)

    assert response.status_code == 200
    unchanged = db.session.get(Item, other_item.id)
    assert unchanged.name == "Not Yours"


def test_cannot_delete_other_users_item(logged_in_client, db):
    other = User(email="other2@example.com")
    other.set_password("password123")
    db.session.add(other)
    db.session.commit()

    other_item = Item(user_id=other.id, name="Not Yours Either", quantity=1, cost_price=Decimal("5.00"))
    db.session.add(other_item)
    db.session.commit()

    response = logged_in_client.post(f"/items/delete/{other_item.id}", follow_redirects=True)

    assert response.status_code == 200
    assert db.session.get(Item, other_item.id) is not None
