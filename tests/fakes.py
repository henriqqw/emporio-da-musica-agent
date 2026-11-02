"""Scripted stand-in for the Anthropic client, so no test needs network or an API key."""

from types import SimpleNamespace

USAGE = SimpleNamespace(input_tokens=10, cache_read_input_tokens=0, output_tokens=5)


def text_response(text):
    return SimpleNamespace(
        stop_reason="end_turn",
        stop_details=None,
        content=[SimpleNamespace(type="text", text=text)],
        usage=USAGE,
    )


def tool_response(name, arguments, tool_id="t1"):
    block = SimpleNamespace(type="tool_use", id=tool_id, name=name, input=arguments)
    return SimpleNamespace(stop_reason="tool_use", stop_details=None, content=[block], usage=USAGE)


def refusal_response():
    return SimpleNamespace(
        stop_reason="refusal", stop_details={"category": None}, content=[], usage=USAGE
    )


class FakeClient:
    """Returns scripted responses (or raises scripted errors) and records requests."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.requests = []
        self.messages = self

    def create(self, **request):
        self.requests.append(request | {"messages": list(request["messages"])})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
