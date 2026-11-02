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


def test_definitions_use_the_openai_function_format(toolbox):
    functions = [d["function"] for d in toolbox.definitions]
    assert all(d["type"] == "function" for d in toolbox.definitions)
    assert [f["name"] for f in functions] == ["search_products", "get_order", "register_complaint"]
    for function in functions:
        assert function["parameters"]["type"] == "object"
        # session data is never a parameter the model can set
        assert not {"phone", "message_id"} & set(function["parameters"]["properties"])


def test_search_products_returns_prices_from_code(toolbox):
    result = toolbox.run("search_products", {"query": "takamine gd20"}, _context())
    gd20 = result["products"][0]
    assert gd20["name"] == "Takamine GD20 Dreadnought Natural"
    assert gd20["pix_price"] == 2089.05
    assert gd20["card"] == {"price": 2199.0, "max_installments": 12, "installment_value": 183.25}
    assert gd20["promotion"] is None


def test_search_products_includes_alternatives_for_unavailable(toolbox):
    result = toolbox.run("search_products", {"query": "Giannini GF-3D"}, _context())
    assert result["products"][0]["availability"] == "esgotado"
    assert len(result["alternatives"]) == 3
    assert "alternatives" not in toolbox.run("search_products", {"query": "gd20"}, _context())


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


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("search_products", "takamine"),  # not an object
        ("search_products", {"query": "x", "color": "azul"}),  # unknown parameter
        ("search_products", {"max_price": "1000"}),  # number sent as string
        ("search_products", {"max_price": True}),  # bool is not a number
        ("search_products", {"max_price": -1}),  # negative price
        ("search_products", {"category": "Pianos de cauda"}),  # not in the enum
        ("search_products", {"query": "x", "include_unavailable": "sim"}),
        ("get_order", {}),  # missing e-mail
        ("get_order", {"email": ANA_EMAIL, "order_id": 8.5}),  # not an integer
        ("register_complaint", {"summary": "Atraso.", "category": "urgente"}),
    ],
)
def test_invalid_arguments_are_rejected_with_a_clear_message(toolbox, name, arguments):
    with pytest.raises(ToolError) as error:
        toolbox.run(name, arguments, _context())
    assert str(error.value)  # goes back to the model so it can fix the call


def test_optional_parameters_sent_as_null_are_ignored(toolbox):
    result = toolbox.run(
        "search_products", {"query": "takamine gd20", "category": None}, _context()
    )
    assert result["products"][0]["id"] == 95


def test_unknown_tool(toolbox):
    with pytest.raises(ToolError):
        toolbox.run("delete_everything", {}, _context())
