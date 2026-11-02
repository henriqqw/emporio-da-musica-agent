"""Loads the store CSVs into typed, immutable records.

This is the only module that knows file names and column formats.
"""

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_FILE_PREFIX = "desafio_tecnico_ai_eng - "


@dataclass(frozen=True)
class Category:
    id: int
    name: str
    description: str


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    category_id: int
    description: str
    price: float
    stock: int
    status: str  # active | discontinued | coming_soon
    specs: dict[str, str]


@dataclass(frozen=True)
class Promotion:
    id: int
    product_id: int
    discount_percent: float
    name: str
    is_active: bool


@dataclass(frozen=True)
class Customer:
    id: int
    name: str
    phone: str
    email: str
    city: str


@dataclass(frozen=True)
class OrderItem:
    product_id: int
    quantity: int


@dataclass(frozen=True)
class Order:
    id: int
    customer_id: int
    order_date: date
    status: str  # pending | confirmed | shipped | delivered | cancelled
    total: float
    payment_method: str
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None
    items: tuple[OrderItem, ...]


@dataclass(frozen=True)
class StoreData:
    categories: dict[int, Category]
    products: dict[int, Product]
    promotions: tuple[Promotion, ...]
    customers: tuple[Customer, ...]
    orders: dict[int, Order]


def load_store_data(data_dir: Path) -> StoreData:
    items_by_order: dict[int, list[OrderItem]] = {}
    for row in _rows(data_dir, "order_items"):
        item = OrderItem(product_id=int(row["product_id"]), quantity=int(row["quantity"]))
        items_by_order.setdefault(int(row["order_id"]), []).append(item)

    return StoreData(
        categories={c.id: c for c in map(_category, _rows(data_dir, "categories"))},
        products={p.id: p for p in map(_product, _rows(data_dir, "products"))},
        promotions=tuple(map(_promotion, _rows(data_dir, "promotions"))),
        customers=tuple(map(_customer, _rows(data_dir, "customers"))),
        orders={
            o.id: o for o in (_order(row, items_by_order) for row in _rows(data_dir, "orders"))
        },
    )


def _rows(data_dir: Path, table: str) -> list[dict[str, str]]:
    path = data_dir / f"{_FILE_PREFIX}{table}.csv"
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _category(row: dict[str, str]) -> Category:
    return Category(id=int(row["category_id"]), name=row["name"], description=row["description"])


def _product(row: dict[str, str]) -> Product:
    return Product(
        id=int(row["product_id"]),
        name=row["name"],
        category_id=int(row["category_id"]),
        description=row["description"],
        price=float(row["price_brl"]),
        stock=int(row["stock_quantity"]),
        status=row["status"],
        specs=json.loads(row["specs"]) if row["specs"] else {},
    )


def _promotion(row: dict[str, str]) -> Promotion:
    return Promotion(
        id=int(row["promotion_id"]),
        product_id=int(row["product_id"]),
        discount_percent=float(row["discount_percent"]),
        name=row["description"],
        is_active=row["is_active"] == "1",
    )


def _customer(row: dict[str, str]) -> Customer:
    return Customer(
        id=int(row["customer_id"]),
        name=row["name"],
        phone=row["phone"],
        email=row["email"],
        city=row["city"],
    )


def _order(row: dict[str, str], items_by_order: dict[int, list[OrderItem]]) -> Order:
    order_id = int(row["order_id"])
    return Order(
        id=order_id,
        customer_id=int(row["customer_id"]),
        order_date=date.fromisoformat(row["order_date"]),
        status=row["status"],
        total=float(row["total_brl"]),
        payment_method=row["payment_method"],
        tracking_code=row["tracking_code"] or None,
        estimated_delivery=(
            date.fromisoformat(row["estimated_delivery"]) if row["estimated_delivery"] else None
        ),
        notes=row["notes"] or None,
        items=tuple(items_by_order.get(order_id, [])),
    )
