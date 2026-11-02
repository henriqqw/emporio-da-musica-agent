import pytest

from emporio.tools import ToolContext, ToolError
from tests.constants import ANA_EMAIL, ANA_PHONE, LETICIA_EMAIL, LETICIA_PHONE, STORE_NOW


def _context(phone=ANA_PHONE, message_id="m1"):
    return ToolContext(phone=phone, message_id=message_id, now=STORE_NOW)


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
    assert gd20["pix_price"] == "R$ 2.089,05"
    assert gd20["card"] == {
        "price": "R$ 2.199,00",
        "max_installments": 12,
        "installment_value": "R$ 183,25",
        "combined_payment_allowed": True,
    }
    assert gd20["promotion"] is None


def test_search_products_includes_alternatives_for_unavailable(toolbox):
    result = toolbox.run("search_products", {"query": "Giannini GF-3D"}, _context())
    assert result["products"][0]["availability"] == "esgotado"
    assert len(result["alternatives"]) == 3
    assert "alternatives" not in toolbox.run("search_products", {"query": "gd20"}, _context())


def test_combined_payment_is_decided_by_code(toolbox):
    # A14: ukulele Kalani KAL-700T, R$ 359 -> R$ 323,10 with 10% off: below R$ 2.000
    ukulele = toolbox.run("search_products", {"query": "KAL-700T"}, _context())["products"][0]
    assert ukulele["card"]["price"] == "R$ 323,10"
    assert ukulele["card"]["combined_payment_allowed"] is False


def test_empty_search_lists_categories_in_stock(toolbox):
    # A13: no saxophones; the agent must not claim other wind instruments
    result = toolbox.run("search_products", {"query": "saxofone"}, _context())
    assert result["total_found"] == 0
    assert "Instrumentos de Sopro (Madeiras)" not in result["categories_in_stock"]
    found = toolbox.run("search_products", {"query": "gd20"}, _context())
    assert "categories_in_stock" not in found


def test_search_by_minimum_price_alone(toolbox):
    result = toolbox.run("search_products", {"min_price": 15000}, _context())
    assert {p["id"] for p in result["products"]} == {131, 143}  # Gibson Les Paul, Nord


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
    context = _context(phone=LETICIA_PHONE)
    result = toolbox.run("get_order", {"email": LETICIA_EMAIL, "order_id": 7}, context)
    sales = result["orders"][0]["after_sales"]
    assert sales["regret_open"] is False
    assert sales["legal_warranty_until"] == "18/05/2026"


def test_register_complaint_links_only_own_orders(toolbox):
    args = {"summary": "Entrega atrasada.", "category": "atraso_entrega"}
    own = toolbox.run("register_complaint", args | {"order_id": 8}, _context(message_id="a"))
    assert own["order_linked"] is True
    assert own["protocol"] == "REC-20260325-0001"
    assert own["response_deadline"] == "26/03/2026 às 14:30"

    foreign = toolbox.run("register_complaint", args | {"order_id": 1}, _context(message_id="b"))
    assert foreign["order_linked"] is False


def test_redelivered_complaint_returns_what_was_stored(toolbox):
    args = {"summary": "Entrega atrasada.", "category": "atraso_entrega"}
    first = toolbox.run("register_complaint", args | {"order_id": 8}, _context(message_id="a"))
    # same message delivered again, the model now omits the order: stored record wins
    again = toolbox.run("register_complaint", args, _context(message_id="a"))
    assert again == first


def test_register_complaint_invalid_input_is_a_tool_error(toolbox):
    with pytest.raises(ToolError):
        toolbox.run("register_complaint", {"summary": "", "category": "outro"}, _context())


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("search_products", "takamine", "objeto JSON"),  # not an object
        ("search_products", {"query": "x", "color": "azul"}, "desconhecidos: color"),
        ("search_products", {"max_price": "1000"}, "max_price deve ser do tipo number"),
        ("search_products", {"max_price": True}, "max_price deve ser do tipo number"),
        ("search_products", {"max_price": -1}, "não podem ser negativos"),
        ("search_products", {"category": "Pianos de cauda"}, "category deve ser um de"),
        ("search_products", {"query": "x", "include_unavailable": "sim"}, "tipo boolean"),
        ("get_order", {}, "obrigatórios ausentes: email"),
        ("get_order", {"email": ANA_EMAIL, "order_id": 8.5}, "order_id deve ser do tipo integer"),
        ("register_complaint", {"summary": "Atraso.", "category": "urgente"}, "category deve ser"),
    ],
)
def test_invalid_arguments_are_rejected_with_a_clear_message(toolbox, name, arguments, message):
    # the message goes back to the model so it can fix the call
    with pytest.raises(ToolError, match=message):
        toolbox.run(name, arguments, _context())


def test_optional_parameters_sent_as_null_are_ignored(toolbox):
    result = toolbox.run(
        "search_products", {"query": "takamine gd20", "category": None}, _context()
    )
    assert result["products"][0]["id"] == 95


def test_unknown_tool(toolbox):
    with pytest.raises(ToolError):
        toolbox.run("delete_everything", {}, _context())
