"""Tool definitions for the model and their dispatch (spec section 5).

Thin layer: validates input, injects session data (phone, message_id, time) that
the model must never control, calls the domain and turns the result into compact
JSON-ready dicts. Every argument is validated here against the tool's own JSON
schema, because not every provider enforces schemas (ADR-05, ADR-13).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from emporio.catalog import Catalog, Offer
from emporio.complaints import CATEGORIES, MAX_SUMMARY_LENGTH, ComplaintStore
from emporio.orders import OrderService, OrderView, Window


class ToolError(Exception):
    """Invalid call; the message goes back to the model as an error tool result."""


@dataclass(frozen=True)
class ToolContext:
    """Data owned by the channel/session, injected into every tool call."""

    phone: str
    message_id: str
    now: datetime


def tool_definitions(category_names: list[str]) -> list[dict[str, Any]]:
    """OpenAI function-calling format. Fixed and ordered, so the request prefix is stable.

    Kept to the JSON Schema subset every OpenAI-compatible provider accepts (no
    `strict`, no `additionalProperties`); validate_arguments enforces the rest.
    """
    return [
        _function(
            "search_products",
            "Busca instrumentos no catálogo da loja com preço, promoção, PIX, parcelamento e "
            "disponibilidade atuais. Use SEMPRE antes de falar de preço, estoque ou promoção "
            "de qualquer produto, e para sugerir alternativas. Informe ao menos um entre "
            "query, category e max_price.",
            {
                "query": {
                    "type": "string",
                    "description": "Marca, modelo ou tipo, ex.: 'takamine gd20', '7 cordas'.",
                },
                "category": {"type": "string", "enum": category_names},
                "min_price": {"type": "number", "description": "Preço mínimo em R$."},
                "max_price": {"type": "number", "description": "Preço máximo em R$."},
                "include_unavailable": {
                    "type": "boolean",
                    "description": "Incluir esgotados, descontinuados e em breve.",
                },
            },
        ),
        _function(
            "get_order",
            "Consulta pedidos do cliente desta conversa. O telefone já vem do canal; peça ao "
            "cliente o e-mail cadastrado antes de chamar. Sem order_id, lista os pedidos mais "
            "recentes. Retorna status, rastreio e prazos de troca/devolução.",
            {
                "email": {"type": "string", "description": "E-mail informado pelo cliente."},
                "order_id": {"type": "integer", "description": "Número do pedido."},
            },
            required=["email"],
        ),
        _function(
            "register_complaint",
            "Registra uma reclamação para a equipe responder em até 24 horas úteis. Só chame "
            "depois de resumir a reclamação ao cliente e ele confirmar. Retorna o protocolo e "
            "o prazo, que devem ser informados ao cliente.",
            {
                "summary": {
                    "type": "string",
                    "description": f"Resumo objetivo, até {MAX_SUMMARY_LENGTH} caracteres.",
                },
                "category": {"type": "string", "enum": list(CATEGORIES)},
                "order_id": {"type": "integer", "description": "Pedido relacionado, se houver."},
            },
            required=["summary", "category"],
        ),
    ]


def _function(
    name: str, description: str, properties: dict[str, Any], required: list[str] | None = None
) -> dict[str, Any]:
    parameters: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": parameters},
    }


class Toolbox:
    def __init__(self, catalog: Catalog, orders: OrderService, complaints: ComplaintStore) -> None:
        self._catalog = catalog
        self._orders = orders
        self._complaints = complaints
        self.definitions = tool_definitions(catalog.category_names)
        functions = (d["function"] for d in self.definitions)
        self._schemas = {f["name"]: f["parameters"] for f in functions}

    def run(self, name: str, arguments: Any, context: ToolContext) -> dict[str, Any]:
        handlers = {
            "search_products": self._search_products,
            "get_order": self._get_order,
            "register_complaint": self._register_complaint,
        }
        if name not in handlers:
            raise ToolError(f"Ferramenta desconhecida: {name}")
        return handlers[name](validate_arguments(self._schemas[name], arguments), context)

    def _search_products(self, args: dict[str, Any], _: ToolContext) -> dict[str, Any]:
        if not any(args.get(key) for key in ("query", "category", "max_price")):
            raise ToolError("Informe ao menos um entre query, category e max_price.")
        if any(args.get(key, 0) < 0 for key in ("min_price", "max_price")):
            raise ToolError("Preços não podem ser negativos.")
        result = self._catalog.search(
            query=args.get("query"),
            category=args.get("category"),
            min_price=args.get("min_price"),
            max_price=args.get("max_price"),
            include_unavailable=bool(args.get("include_unavailable", False)),
        )
        return {
            "total_found": result.total_found,
            "products": [_offer_json(offer) for offer in result.offers],
        }

    def _get_order(self, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        lookup = self._orders.lookup(
            phone=context.phone,
            email=args["email"],
            today=context.now.date(),
            order_id=args.get("order_id"),
        )
        if lookup.error:
            return {"error": lookup.error}
        return {
            "customer_first_name": lookup.customer.name.split()[0],
            "orders": [_order_json(view) for view in lookup.orders],
        }

    def _register_complaint(self, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        order_id = args.get("order_id")
        order_linked = order_id is not None and self._orders.owns_order(context.phone, order_id)
        try:
            complaint = self._complaints.register(
                phone=context.phone,
                message_id=context.message_id,
                category=args["category"],
                summary=args["summary"],
                order_id=order_id if order_linked else None,
                now=context.now,
            )
        except ValueError as error:
            raise ToolError(str(error)) from error
        return {
            "protocol": complaint.protocol,
            "response_deadline": complaint.response_deadline,
            "order_linked": order_linked,
        }


_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
}


def validate_arguments(schema: dict[str, Any], arguments: Any) -> dict[str, Any]:
    """Check arguments against the subset of JSON Schema the tools use.

    Optional parameters sent as null are dropped. Messages are in Portuguese and
    specific, so the model can fix the call on its next attempt.
    """
    if not isinstance(arguments, dict):
        raise ToolError("Os argumentos devem ser um objeto JSON.")
    properties = schema["properties"]
    unknown = sorted(set(arguments) - set(properties))
    if unknown:
        raise ToolError(f"Parâmetros desconhecidos: {', '.join(unknown)}.")
    missing = [name for name in schema.get("required", []) if arguments.get(name) in (None, "")]
    if missing:
        raise ToolError(f"Parâmetros obrigatórios ausentes: {', '.join(missing)}.")

    valid = {}
    for name, value in arguments.items():
        if value is None:
            continue
        spec = properties[name]
        expected = spec["type"]
        # bool is a subclass of int in Python: never accept it as a number, and vice versa
        wrong_bool = isinstance(value, bool) != (expected == "boolean")
        if wrong_bool or not isinstance(value, _JSON_TYPES[expected]):
            raise ToolError(f"O parâmetro {name} deve ser do tipo {expected}.")
        if "enum" in spec and value not in spec["enum"]:
            raise ToolError(f"O parâmetro {name} deve ser um de: {', '.join(spec['enum'])}.")
        valid[name] = value
    return valid


def _offer_json(offer: Offer) -> dict[str, Any]:
    price = offer.price
    promotion = price.promotion
    return {
        "id": offer.product.id,
        "name": offer.product.name,
        "category": offer.category,
        "description": offer.product.description,
        "specs": offer.product.specs,
        "availability": offer.availability,
        "table_price": price.table_price,
        "promotion": (
            {
                "name": promotion.name,
                "discount_percent": promotion.discount_percent,
                "price": promotion.price,
            }
            if promotion
            else None
        ),
        "expired_promotions": list(offer.expired_promotions),
        "pix_price": price.pix_price,
        "card": {
            "price": price.card_price,
            "max_installments": price.max_installments,
            "installment_value": price.installment_value,
        },
    }


def _order_json(view: OrderView) -> dict[str, Any]:
    order = view.order
    data: dict[str, Any] = {
        "order_id": order.id,
        "date": order.order_date.isoformat(),
        "status": order.status,
        "status_label": view.status_label,
        "total": order.total,
        "payment_method": view.payment_label,
        "items": [{"name": name, "quantity": qty} for name, qty in view.items],
        "tracking_code": order.tracking_code,
        "estimated_delivery": (
            order.estimated_delivery.isoformat() if order.estimated_delivery else None
        ),
        "delivery_late": view.delivery_late,
        "notes": order.notes,
    }
    if view.after_sales:
        sales = view.after_sales
        data["after_sales"] = {
            "received_on": sales.received_on.isoformat(),
            **_window_json("regret", sales.regret),
            **_window_json("preference_exchange", sales.preference_exchange),
            **_window_json("defect_exchange", sales.defect_exchange),
            **_window_json("legal_warranty", sales.legal_warranty),
        }
    return data


def _window_json(name: str, window: Window) -> dict[str, Any]:
    return {f"{name}_until": window.until.isoformat(), f"{name}_open": window.open}
