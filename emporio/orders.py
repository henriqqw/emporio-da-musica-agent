"""Order lookup behind customer identification (spec 5.2, rules R-ORD-*, R-RET-*)."""

from dataclasses import dataclass
from datetime import date, timedelta

from emporio.data import Customer, Order, StoreData
from emporio.phone import normalize_phone

MAX_ORDERS_LISTED = 5
REGRET_DAYS = 7  # R-RET-1, from receipt
PREFERENCE_EXCHANGE_DAYS = 7  # R-RET-3, from receipt
DEFECT_EXCHANGE_DAYS = 30  # R-RET-2, from purchase
LEGAL_WARRANTY_DAYS = 90  # R-WAR-1, from receipt

STATUS_LABELS = {  # R-ORD-2
    "pending": "recebido, aguardando confirmação do pagamento",
    "confirmed": "pagamento confirmado, em separação",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}
_PAYMENT_LABELS = {"pix": "PIX", "debit": "cartão de débito", "boleto": "boleto"}


@dataclass(frozen=True)
class Window:
    until: date
    open: bool


@dataclass(frozen=True)
class AfterSales:
    """Return/exchange/warranty deadlines; only for delivered orders."""

    received_on: date
    regret: Window
    preference_exchange: Window
    defect_exchange: Window
    legal_warranty: Window


@dataclass(frozen=True)
class OrderView:
    order: Order
    status_label: str
    payment_label: str
    items: tuple[tuple[str, int], ...]  # (product name, quantity)
    delivery_late: bool
    after_sales: AfterSales | None


@dataclass(frozen=True)
class OrderLookup:
    customer: Customer | None
    orders: tuple[OrderView, ...] = ()
    error: str | None = None  # "not_identified" | "order_not_found"


class OrderService:
    def __init__(self, store: StoreData) -> None:
        self._store = store
        self._customers = {
            (normalize_phone(c.phone), c.email.strip().lower()): c for c in store.customers
        }
        self._customer_ids_by_phone: dict[str, set[int]] = {}
        for c in store.customers:
            self._customer_ids_by_phone.setdefault(normalize_phone(c.phone), set()).add(c.id)

    def lookup(
        self, phone: str, email: str, today: date, order_id: int | None = None
    ) -> OrderLookup:
        """Orders of the customer identified by phone + e-mail (R-ORD-1).

        An order of another customer gets the same answer as a missing one, so the
        tool never reveals that an order number exists.
        """
        customer = self._customers.get((normalize_phone(phone), email.strip().lower()))
        if customer is None:
            return OrderLookup(customer=None, error="not_identified")

        orders = sorted(
            (o for o in self._store.orders.values() if o.customer_id == customer.id),
            key=lambda o: (o.order_date, o.id),
            reverse=True,
        )
        if order_id is not None:
            orders = [o for o in orders if o.id == order_id]
            if not orders:
                return OrderLookup(customer=customer, error="order_not_found")

        views = tuple(self._view(o, today) for o in orders[:MAX_ORDERS_LISTED])
        return OrderLookup(customer=customer, orders=views)

    def owns_order(self, phone: str, order_id: int) -> bool:
        """Whether the order belongs to a customer registered with this phone."""
        order = self._store.orders.get(order_id)
        if order is None:
            return False
        return order.customer_id in self._customer_ids_by_phone.get(normalize_phone(phone), set())

    def _view(self, order: Order, today: date) -> OrderView:
        products = self._store.products
        return OrderView(
            order=order,
            status_label=STATUS_LABELS[order.status],
            payment_label=payment_label(order.payment_method),
            items=tuple((products[i.product_id].name, i.quantity) for i in order.items),
            delivery_late=(
                order.status == "shipped"
                and order.estimated_delivery is not None
                and order.estimated_delivery < today
            ),
            after_sales=after_sales(order, today),
        )


def payment_label(method: str) -> str:
    if method.startswith("credit_"):
        return f"cartão de crédito em {method.removeprefix('credit_')}"
    return _PAYMENT_LABELS.get(method, method)


def after_sales(order: Order, today: date) -> AfterSales | None:
    """Deadlines counted in calendar days, last day included.

    The data has no actual delivery date, so receipt = estimated delivery (R-ORD-5).
    """
    if order.status != "delivered" or order.estimated_delivery is None:
        return None
    received = order.estimated_delivery

    def window(start: date, days: int) -> Window:
        until = start + timedelta(days=days)
        return Window(until=until, open=today <= until)

    return AfterSales(
        received_on=received,
        regret=window(received, REGRET_DAYS),
        preference_exchange=window(received, PREFERENCE_EXCHANGE_DAYS),
        defect_exchange=window(order.order_date, DEFECT_EXCHANGE_DAYS),
        legal_warranty=window(received, LEGAL_WARRANTY_DAYS),
    )
