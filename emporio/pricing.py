"""Price rules from the policy manual (sections 3 and 6.2). Pure functions.

Money is computed with Decimal and rounded half-up to cents, so the agent
never shows a price that differs from what the store would charge.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from emporio.data import Promotion

PIX_DISCOUNT = Decimal("0.05")  # R-PRICE-4
MAX_INSTALLMENTS = 12
# (largest installment count of the tier, minimum installment value) - R-PAY-2
INSTALLMENT_TIERS = ((3, Decimal("50")), (6, Decimal("80")), (12, Decimal("100")))
COMBINED_PAYMENT_MIN = Decimal("2000")  # R-PAY-3: strictly above


@dataclass(frozen=True)
class AppliedPromotion:
    name: str
    discount_percent: float
    price: float


@dataclass(frozen=True)
class PriceQuote:
    table_price: float
    promotion: AppliedPromotion | None
    pix_price: float | None  # None when a promotion is active (not cumulative)
    card_price: float  # what the customer pays on card: promotional or table price
    max_installments: int
    installment_value: float


def quote(table_price: float, promotions: Iterable[Promotion]) -> PriceQuote:
    """Full price breakdown for one product, given that product's promotions."""
    table = _money(table_price)
    promo = best_active_promotion(promotions)

    if promo is None:
        card = table
        applied = None
        pix: Decimal | None = _round(table * (1 - PIX_DISCOUNT))
    else:
        card = _round(table * (1 - Decimal(str(promo.discount_percent)) / 100))
        applied = AppliedPromotion(promo.name, promo.discount_percent, float(card))
        pix = None

    installments = max_installments(card)
    return PriceQuote(
        table_price=float(table),
        promotion=applied,
        pix_price=float(pix) if pix is not None else None,
        card_price=float(card),
        max_installments=installments,
        installment_value=float(_round(card / installments)),
    )


def best_active_promotion(promotions: Iterable[Promotion]) -> Promotion | None:
    """Only active promotions count; if several, the highest discount wins (R-PRICE-2)."""
    active = [p for p in promotions if p.is_active]
    return max(active, key=lambda p: p.discount_percent, default=None)


def max_installments(price: Decimal | float) -> int:
    """Largest interest-free installment count whose value meets the tier minimum."""
    amount = _money(price)
    best = 1
    for n in range(2, MAX_INSTALLMENTS + 1):
        if amount / n >= _tier_minimum(n):
            best = n
    return best


def allows_combined_payment(price: Decimal | float) -> bool:
    return _money(price) > COMBINED_PAYMENT_MIN


def _tier_minimum(installments: int) -> Decimal:
    for tier_max, minimum in INSTALLMENT_TIERS:
        if installments <= tier_max:
            return minimum
    raise ValueError(f"installments above {MAX_INSTALLMENTS}: {installments}")


def _money(value: Decimal | float) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
