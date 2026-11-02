"""Scripted stand-in for the OpenAI client, so no test needs network or an API key.

Responses are built from the SDK's real types, so a shape mismatch with the API
fails here and not in production.
"""

import json

from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
    Function,
)

USAGE = CompletionUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)


def _completion(message: ChatCompletionMessage, finish_reason: str) -> ChatCompletion:
    return ChatCompletion(
        id="fake",
        object="chat.completion",
        created=0,
        model="fake-model",
        choices=[Choice(index=0, finish_reason=finish_reason, message=message)],
        usage=USAGE,
    )


def text_response(text: str) -> ChatCompletion:
    message = ChatCompletionMessage(role="assistant", content=text)
    return _completion(message, "stop")


def tool_response(name: str, arguments: dict | str, tool_id: str = "call_1") -> ChatCompletion:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    call = ChatCompletionMessageFunctionToolCall(
        id=tool_id, type="function", function=Function(name=name, arguments=raw)
    )
    message = ChatCompletionMessage(role="assistant", content=None, tool_calls=[call])
    return _completion(message, "tool_calls")


def filtered_response() -> ChatCompletion:
    message = ChatCompletionMessage(role="assistant", content=None)
    return _completion(message, "content_filter")


class FakeClient:
    """Returns scripted responses (or raises scripted errors) and records requests."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.requests = []
        self.chat = self
        self.completions = self

    def create(self, **request):
        self.requests.append(request | {"messages": list(request["messages"])})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
