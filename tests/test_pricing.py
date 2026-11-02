import pytest

from emporio.data import Promotion
from emporio.pricing import (
    allows_combined_payment,
    best_active_promotion,
    format_brl,
    max_installments,
    quote,
)


def _promo(percent: float, active: bool, name: str = "Promo") -> Promotion:
    return Promotion(id=1, product_id=1, discount_percent=percent, name=name, is_active=active)


def test_no_promotion_gives_pix_discount_and_installments():
    # A2: Takamine GD20, its only promotion is inactive
    q = quote(2199.0, [_promo(12, active=False)])
    assert q.promotion is None
    assert q.pix_price == 2089.05
    assert q.card_price == 2199.0
    assert (q.max_installments, q.installment_value) == (12, 183.25)


def test_active_promotion_replaces_pix_discount():
    # A4: Crafter HT-100, 18% "Desconto Exclusivo" is active
    q = quote(2399.0, [_promo(18, active=True, name="Desconto Exclusivo")])
    assert q.promotion.name == "Desconto Exclusivo"
    assert q.pix_price is None
    assert q.card_price == 1967.18
    assert q.max_installments == 12


def test_highest_active_promotion_wins_and_inactive_ones_are_ignored():
    promos = [_promo(40, active=False), _promo(10, active=True), _promo(15, active=True)]
    assert best_active_promotion(promos).discount_percent == 15


@pytest.mark.parametrize(
    ("price", "expected"),
    [
        (99.99, 1),  # 2x would be 49.995 < 50
        (100.0, 2),  # 2x of 50.00
        (150.0, 3),  # 3x of 50.00
        (319.99, 3),  # 4x would be 79.9975 < 80
        (320.0, 4),  # 4x of 80.00
        (480.0, 6),  # 6x of 80.00
        (699.99, 6),  # 7x would be 99.998 < 100
        (700.0, 7),  # 7x of 100.00
        (1200.0, 12),
        (50000.0, 12),  # never above 12x
    ],
)
def test_installment_tiers(price, expected):
    assert max_installments(price) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (599.9, "R$ 599,90"),  # the live-run bug: must not become "R$ 599,99"
        (2089.05, "R$ 2.089,05"),
        (11499, "R$ 11.499,00"),
        (0.5, "R$ 0,50"),
        (1234567.891, "R$ 1.234.567,89"),
    ],
)
def test_format_brl(value, expected):
    assert format_brl(value) == expected


def test_combined_payment_only_above_2000():
    assert not allows_combined_payment(2000.0)
    assert allows_combined_payment(2000.01)
