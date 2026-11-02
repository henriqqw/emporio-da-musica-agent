from datetime import datetime

import pytest

from emporio.catalog import Catalog
from emporio.complaints import ComplaintStore
from emporio.config import STORE_TZ
from emporio.orders import OrderService
from emporio.tools import Toolbox, ToolContext, ToolError

ANA_PHONE = "(67) 99654-7821"
ANA_EMAIL = "anacarol.ferreira@coldmail.com"


@pytest.fixture
def toolbox(store, tmp_path):
    return Toolbox(Catalog(store), OrderService(store), ComplaintStore(tmp_path / "c.jsonl"))


def _context(phone=ANA_PHONE, message_id="m1"):
    return ToolContext(
        phone=phone, message_id=message_id, now=datetime(2026, 3, 25, 14, 30, tzinfo=STORE_TZ)
    )


def test_definitions_are_strict_and_closed(toolbox):
    names = [d["name"] for d in toolbox.definitions]
    assert names == ["search_products", "get_order", "register_complaint"]
    for definition in toolbox.definitions:
        assert definition["strict"] is True
        assert definition["input_schema"]["additionalProperties"] is False
        # session data is never a parameter the model can set
        assert "phone" not in definition["input_schema"]["properties"]


def test_search_products_returns_prices_from_code(toolbox):
    result = toolbox.run("search_products", {"query": "takamine gd20"}, _context())
    gd20 = result["products"][0]
    assert gd20["name"] == "Takamine GD20 Dreadnought Natural"
    assert gd20["pix_price"] == 2089.05
    assert gd20["card"] == {"price": 2199.0, "max_installments": 12, "installment_value": 183.25}
    assert gd20["promotion"] is None


def test_search_products_needs_a_filter(toolbox):
    with pytest.raises(ToolError):
        toolbox.run("search_products", {}, _context())


def test_get_order_uses_phone_from_session(toolbox):
    result = toolbox.run("get_order", {"email": ANA_EMAIL}, _context())
    assert result["customer_first_name"] == "Ana"
    assert result["orders"][0]["order_id"] == 8
    assert result["orders"][0]["delivery_late"] is True

    # same e-mail from another phone: not identified
    other = toolbox.run("get_order", {"email": ANA_EMAIL}, _context(phone="67999999999"))
    assert other == {"error": "not_identified"}


def test_get_order_includes_after_sales_for_delivered(toolbox):
    context = _context(phone="67997890123")
    result = toolbox.run("get_order", {"email": "leticia.rocha@jmail.com", "order_id": 7}, context)
    sales = result["orders"][0]["after_sales"]
    assert sales["regret_open"] is False
    assert sales["legal_warranty_until"] == "2026-05-18"


def test_register_complaint_links_only_own_orders(toolbox):
    args = {"summary": "Entrega atrasada.", "category": "atraso_entrega"}
    own = toolbox.run("register_complaint", args | {"order_id": 8}, _context(message_id="a"))
    assert own["order_linked"] is True
    assert own["protocol"] == "REC-20260325-0001"
    assert own["response_deadline"] == "2026-03-26T14:30-04:00"

    foreign = toolbox.run("register_complaint", args | {"order_id": 1}, _context(message_id="b"))
    assert foreign["order_linked"] is False


def test_register_complaint_invalid_input_is_a_tool_error(toolbox):
    with pytest.raises(ToolError):
        toolbox.run("register_complaint", {"summary": "", "category": "outro"}, _context())


def test_unknown_tool(toolbox):
    with pytest.raises(ToolError):
        toolbox.run("delete_everything", {}, _context())
