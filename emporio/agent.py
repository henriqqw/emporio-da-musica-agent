"""Tool-use loop over the Anthropic Messages API (spec section 7, ADR-02).

The client is injected, so tests drive the loop with a fake. Every failure mode
(API error, refusal, too many tool rounds) ends in the same polite fallback,
never in an exception reaching the customer.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic

from emporio.prompt import system_blocks
from emporio.tools import Toolbox, ToolContext, ToolError

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
MAX_TOKENS = 8000
FALLBACK_REPLY = (
    "Desculpa, tive um probleminha aqui e não consegui te responder agora. 😕 "
    "Você pode tentar de novo em instantes ou falar com a nossa equipe pelo telefone "
    "(67) 3341-4444 ou pelo e-mail contato@emporiodamusica.com.br."
)


@dataclass
class AgentReply:
    text: str
    tools_called: list[str] = field(default_factory=list)
    fallback: bool = False


class Agent:
    def __init__(
        self,
        client: anthropic.Anthropic,
        toolbox: Toolbox,
        model: str,
        effort: str,
    ) -> None:
        self._client = client
        self._toolbox = toolbox
        self._model = model
        self._effort = effort

    def respond(
        self, messages: list[dict[str, Any]], context: ToolContext, customer_name: str | None
    ) -> AgentReply:
        """Answer the last user message in `messages`, appending the assistant turns.

        `messages` is the session history and is only ever appended to.
        """
        system = system_blocks(context.now, customer_name)
        reply = AgentReply(text="")

        for _ in range(MAX_TOOL_ROUNDS + 1):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=MAX_TOKENS,
                    system=system,
                    tools=self._toolbox.definitions,
                    messages=messages,
                    output_config={"effort": self._effort},
                )
            except anthropic.APIError:
                logger.exception("LLM request failed")
                return _fallback(reply)

            _log_usage(response)
            if response.stop_reason == "refusal":
                logger.warning("model refused: %s", response.stop_details)
                return _fallback(reply)

            messages.append({"role": "assistant", "content": response.content})
            tool_uses = [block for block in response.content if block.type == "tool_use"]
            if response.stop_reason != "tool_use" or not tool_uses:
                reply.text = _text(response.content)
                return reply if reply.text else _fallback(reply)

            messages.append(
                {"role": "user", "content": [self._run_tool(b, context, reply) for b in tool_uses]}
            )

        logger.warning("stopped after %d tool rounds", MAX_TOOL_ROUNDS)
        return _fallback(reply)

    def _run_tool(self, block: Any, context: ToolContext, reply: AgentReply) -> dict[str, Any]:
        reply.tools_called.append(block.name)
        started = time.perf_counter()
        is_error = False
        try:
            content = json.dumps(
                self._toolbox.run(block.name, block.input, context),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except ToolError as error:
            content, is_error = str(error), True
        except Exception:
            logger.exception("tool %s crashed", block.name)
            content, is_error = "Erro interno ao executar a ferramenta.", True

        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("tool=%s error=%s %.0fms", block.name, is_error, elapsed_ms)
        result = {"type": "tool_result", "tool_use_id": block.id, "content": content}
        if is_error:
            result["is_error"] = True
        return result


def _fallback(reply: AgentReply) -> AgentReply:
    reply.text = FALLBACK_REPLY
    reply.fallback = True
    return reply


def _text(content: list[Any]) -> str:
    return "\n".join(block.text for block in content if block.type == "text").strip()


def _log_usage(response: Any) -> None:
    usage = response.usage
    logger.info(
        "llm stop=%s in=%s cache_read=%s out=%s",
        response.stop_reason,
        usage.input_tokens,
        usage.cache_read_input_tokens,
        usage.output_tokens,
    )
