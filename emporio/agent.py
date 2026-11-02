"""Tool-use loop over any OpenAI-compatible Chat Completions API (spec 7, ADR-02, ADR-13).

The client is injected, so tests drive the loop with a fake. Every failure mode
(API error, content filter, empty reply, too many tool rounds) ends in the same
polite fallback, never in an exception reaching the customer.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, cast

import openai

from emporio.prompt import system_prompt
from emporio.tools import Toolbox, ToolContext, ToolError

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
FALLBACK_REPLY = (
    "Desculpa, tive um probleminha aqui e não consegui te responder agora. 😕 "
    "Você pode tentar de novo em instantes ou falar com a nossa equipe pelo telefone "
    "(67) 3341-4444 ou pelo e-mail contato@emporiodamusica.com.br."
)


# Why a reply fell back to FALLBACK_REPLY. Only PROVIDER_ERROR says nothing about the
# model's behaviour; evals and logs use the distinction.
PROVIDER_ERROR = "provider_error"  # API error, timeout, rate limit
MALFORMED_RESPONSE = "malformed_response"  # e.g. no choices from a compatible provider
FILTERED = "filtered"  # provider content filter or model refusal
EMPTY_REPLY = "empty_reply"
TOOL_LIMIT = "tool_limit"


@dataclass
class AgentReply:
    text: str
    tools_called: list[str] = field(default_factory=list)
    fallback_reason: str | None = None  # set when text is FALLBACK_REPLY


class Agent:
    def __init__(
        self,
        client: openai.OpenAI,
        toolbox: Toolbox,
        model: str,
        reasoning_effort: str | None = None,
    ) -> None:
        self._client = client
        self._toolbox = toolbox
        self._model = model
        # Sent only when configured: not every provider accepts the parameter.
        self._extra: dict[str, Any] = (
            {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
        )

    def respond(
        self, history: list[dict[str, Any]], context: ToolContext, customer_name: str | None
    ) -> AgentReply:
        """Answer the last user message in `history`, appending the assistant turns.

        `history` is the session's conversation and is only ever appended to; the system
        prompt is rebuilt on every request because it carries the current time.
        """
        prompt = system_prompt(context.now, customer_name, self._toolbox.categories_in_stock())
        system = {"role": "system", "content": prompt}
        reply = AgentReply(text="")

        for round_number in range(MAX_TOOL_ROUNDS + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    # Plain dicts in the API's wire format, as stored in the session; the
                    # SDK's TypedDicts would have to be threaded through the whole history.
                    messages=cast(Any, [system, *history]),
                    tools=cast(Any, self._toolbox.definitions),
                    **self._extra,
                )
                choice = response.choices[0]
                message = choice.message
            except openai.APIError:
                logger.exception("LLM request failed")
                return _fallback(reply, PROVIDER_ERROR)
            except Exception:  # a compatible provider sent something unexpected
                logger.exception("malformed LLM response")
                return _fallback(reply, MALFORMED_RESPONSE)

            _log_usage(choice.finish_reason, response.usage)
            if choice.finish_reason == "content_filter" or message.refusal:
                logger.warning("model refused or response was filtered")
                return _fallback(reply, FILTERED)

            if message.tool_calls and round_number == MAX_TOOL_ROUNDS:
                # Never run a tool whose result the customer will not see: a complaint
                # written here would be registered without its protocol being told.
                logger.warning("still calling tools after %d rounds; none run", MAX_TOOL_ROUNDS)
                return _fallback(reply, TOOL_LIMIT)

            text = (message.content or "").strip()
            if not message.tool_calls and not text:
                # Not stored: an empty assistant turn can make providers reject the
                # whole history, breaking every later message of the session.
                return _fallback(reply, EMPTY_REPLY)

            history.append(_assistant_message(message))
            if not message.tool_calls:
                reply.text = text
                return reply

            for call in message.tool_calls:
                history.append(self._run_tool(call, context, reply))

        raise AssertionError("unreachable: the last round returns")

    def _run_tool(self, call: Any, context: ToolContext, reply: AgentReply) -> dict[str, Any]:
        name = call.function.name
        reply.tools_called.append(name)
        started = time.perf_counter()
        failed = True
        try:
            arguments = json.loads(call.function.arguments or "{}")
            result = self._toolbox.run(name, arguments, context)
            content = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
            failed = False
        except json.JSONDecodeError:
            content = "ERRO: os argumentos não são um JSON válido."
        except ToolError as error:
            content = f"ERRO: {error}"
        except Exception:
            logger.exception("tool %s crashed", name)
            content = "ERRO: falha interna ao executar a ferramenta."

        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("tool=%s error=%s %.0fms", name, failed, elapsed_ms)
        return {"role": "tool", "tool_call_id": call.id, "content": content}


def _assistant_message(message: Any) -> dict[str, Any]:
    """The assistant message as the provider sent it, minus empty fields.

    Dumping the SDK object (instead of rebuilding it) keeps provider-specific extras,
    such as Gemini's thought signatures on tool calls, that must be sent back as is.
    """
    data = message.model_dump(exclude_none=True)
    return {key: value for key, value in data.items() if value not in ([], {}, "")}


def _fallback(reply: AgentReply, reason: str) -> AgentReply:
    reply.text = FALLBACK_REPLY
    reply.fallback_reason = reason
    return reply


def _log_usage(finish_reason: str | None, usage: Any) -> None:
    if usage is None:  # some providers omit it
        logger.info("llm finish=%s", finish_reason)
        return
    details = usage.prompt_tokens_details
    logger.info(
        "llm finish=%s in=%s cached=%s out=%s",
        finish_reason,
        usage.prompt_tokens,
        details.cached_tokens if details else None,
        usage.completion_tokens,
    )
