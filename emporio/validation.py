"""Tool-argument validation against the tools' own JSON schemas (ADR-05, ADR-13).

Not every OpenAI-compatible provider enforces tool schemas, so every call is checked
here; the schema stays the single source of truth.
"""

from typing import Any


class ToolError(Exception):
    """Invalid call; the message goes back to the model as an error tool result."""


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
