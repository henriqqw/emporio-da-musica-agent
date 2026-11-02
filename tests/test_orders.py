from datetime import date

import pytest

from emporio.orders import OrderService, payment_label
from tests.constants import ANA_EMAIL, ANA_PHONE, LETICIA_EMAIL, LETICIA_PHONE, REFERENCE_DATE

ANA = (ANA_PHONE, ANA_EMAIL)
LETICIA = (LETICIA_PHONE, LETICIA_EMAIL)


@pytest.fixture(scope="module")
def orders(store):
    return OrderService(store)


def test_identified_customer_sees_shipped_order_flagged_late(orders):
    # A8: shipped, estimated 2026-02-28, reference date 2026-03-25
    result = orders.lookup(*ANA, today=REFERENCE_DATE)
    assert result.error is None
    assert result.customer.name.startswith("Ana Carolina")
    (view,) = result.orders
    assert view.order.id == 8
    assert view.status_label == "enviado"
    assert view.order.tracking_code == "BRJL5544332BR"
    assert view.delivery_late is True
    assert view.after_sales is None


def test_wrong_email_reveals_nothing(orders):
    # A9
    result = orders.lookup(ANA[0], "outra@pessoa.com", today=REFERENCE_DATE)
    assert result.error == "not_identified"
    assert result.customer is None
    assert result.orders == ()


def test_email_and_phone_must_belong_to_the_same_customer(orders):
    # customers 11 and 43 share the e-mail bruno.martins@jmail.com
    assert orders.lookup("67985432109", "bruno.martins@jmail.com", REFERENCE_DATE).customer.id == 11
    assert (
        orders.lookup("67994563456", "Bruno.Martins@jmail.com ", REFERENCE_DATE).customer.id == 43
    )


def test_order_of_another_customer_looks_missing(orders):
    result = orders.lookup(*ANA, today=REFERENCE_DATE, order_id=1)
    assert result.error == "order_not_found"
    assert result.orders == ()


def test_after_sales_windows_for_delivered_order(orders):
    # A10: order 7 bought 2026-02-03, received 2026-02-17
    (view,) = orders.lookup(*LETICIA, today=REFERENCE_DATE, order_id=7).orders
    sales = view.after_sales
    assert sales.received_on == date(2026, 2, 17)
    assert (sales.regret.until, sales.regret.open) == (date(2026, 2, 24), False)
    assert sales.preference_exchange.until == date(2026, 2, 24)
    assert (sales.defect_exchange.until, sales.defect_exchange.open) == (date(2026, 3, 5), False)
    assert (sales.legal_warranty.until, sales.legal_warranty.open) == (date(2026, 5, 18), True)


def test_last_day_of_a_window_is_still_open(orders):
    (view,) = orders.lookup(*LETICIA, today=date(2026, 2, 24), order_id=7).orders
    assert view.after_sales.regret.open is True


def test_customer_orders_most_recent_first(orders):
    # customer 3 has orders 1 (2025-10-15) and 19 (2026-02-22, cancelled)
    result = orders.lookup("(67) 98432-1098", "pedro.oliveira@jmail.com", REFERENCE_DATE)
    assert [v.order.id for v in result.orders] == [19, 1]
    assert result.orders[0].order.notes == "Pagamento não confirmado dentro do prazo"


def test_owns_order(orders):
    assert orders.owns_order(ANA[0], 8)
    assert not orders.owns_order(ANA[0], 7)
    assert not orders.owns_order(ANA[0], 999)


@pytest.mark.parametrize(
    ("method", "label"),
    [("pix", "PIX"), ("credit_12x", "cartão de crédito em 12x"), ("boleto", "boleto")],
)
def test_payment_labels(method, label):
    assert payment_label(method) == label
