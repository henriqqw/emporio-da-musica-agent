from datetime import date


def test_loads_every_table(store):
    assert len(store.categories) == 9
    assert len(store.products) == 65
    assert len(store.promotions) == 25
    assert len(store.customers) == 50
    assert len(store.orders) == 20


def test_product_fields_are_typed(store):
    gd20 = store.products[95]
    assert gd20.name == "Takamine GD20 Dreadnought Natural"
    assert gd20.price == 2199.0
    assert gd20.stock == 5
    assert gd20.specs["color"] == "Natural"


def test_order_has_items_and_optional_fields(store):
    order = store.orders[15]
    assert [(i.product_id, i.quantity) for i in order.items] == [(82, 1), (106, 1)]
    assert order.tracking_code is None
    assert order.estimated_delivery is None

    shipped = store.orders[8]
    assert shipped.tracking_code == "BRJL5544332BR"
    assert shipped.estimated_delivery == date(2026, 2, 28)


def test_promotion_active_flag(store):
    active = {p.product_id for p in store.promotions if p.is_active}
    assert active == {127, 121, 90, 94}
