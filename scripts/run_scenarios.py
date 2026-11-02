"""Run the acceptance conversations against the live model and save transcripts.

Usage:  python -m scripts.run_scenarios            (needs LLM_API_KEY in .env)
        python -m scripts.run_scenarios devolucao  (only the named scenario)

Each scenario goes through ChatService exactly like a real channel would. The clock
is fixed to Wednesday 25/03/2026 14:30 (store open) so runs are reproducible, and
complaints go to a throwaway file. Output: docs/examples/<name>.md. The transcripts
are then reviewed by hand against the spec's acceptance table (section 10).
"""

import sys
import tempfile
import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from emporio.config import PROJECT_ROOT, STORE_TZ, load_settings
from emporio.service import IncomingMessage, build_chat_service

FIXED_NOW = datetime(2026, 3, 25, 14, 30, tzinfo=STORE_TZ)
EXAMPLES_DIR = PROJECT_ROOT / "docs" / "examples"


@dataclass(frozen=True)
class Scenario:
    name: str
    title: str
    shows: str  # what the conversation demonstrates
    acceptance: str  # spec section 10 rows covered
    phone: str
    customer_name: str | None
    messages: tuple[str, ...]


SCENARIOS = (
    Scenario(
        name="catalogo_e_precos",
        title="Catálogo, preço e promoção expirada",
        shows=(
            "Busca no catálogo com filtro de categoria e preço, preço com PIX e parcelamento "
            "calculados pelo código, e transparência sobre uma promoção que já acabou."
        ),
        acceptance="A1, A2, A3",
        phone="(67) 99111-2222",
        customer_name="Rodrigo",
        messages=(
            "Oi! Quais violões vocês têm até R$ 1000?",
            "Quanto custa o Takamine GD20?",
            "Ele ainda tá naquela promoção de oferta especial?",
        ),
    ),
    Scenario(
        name="estoque_e_promocao_ativa",
        title="Produto esgotado, alternativas e promoção ativa",
        shows=(
            "Produto sem estoque com sugestão de alternativas disponíveis, e promoção ativa "
            "sem acumular o desconto do PIX."
        ),
        acceptance="A5, A4",
        phone="(67) 99222-3333",
        customer_name=None,
        messages=(
            "Vocês têm o Giannini GF-3D?",
            "E o Crafter HT-100, quanto tá? Dá pra ter o desconto do PIX também?",
        ),
    ),
    Scenario(
        name="informacoes_e_fora_de_escopo",
        title="Informações da loja, acessórios e pedido fora do escopo",
        shows="Respostas do manual de políticas e recusa educada de pedidos fora do escopo.",
        acceptance="A7, A11, A12",
        phone="(67) 99333-4444",
        customer_name="Felipe",
        messages=(
            "Qual o endereço e o horário de vocês?",
            "Vocês vendem cordas de violão?",
            "Beleza. Me passa uma receita de bolo de cenoura?",
        ),
    ),
    Scenario(
        name="pedido_atrasado_e_reclamacao",
        title="Pedido atrasado e registro de reclamação",
        shows=(
            "Identificação por telefone + e-mail antes de mostrar o pedido, atraso detectado "
            "pelo código, e reclamação registrada só após confirmação, com protocolo e prazo."
        ),
        acceptance="A8, A16",
        phone="(67) 99654-7821",
        customer_name="Ana Carolina",
        messages=(
            "Oi, cadê meu pedido?",
            "anacarol.ferreira@coldmail.com",
            "Que absurdo, era pra ter chegado em fevereiro! Quero fazer uma reclamação.",
            "Sim, pode registrar.",
        ),
    ),
    Scenario(
        name="devolucao_por_arrependimento",
        title="Pedido de devolução fora do prazo",
        shows=(
            "Aplicação da política de trocas com prazos calculados pelo código: arrependimento "
            "e troca por defeito já vencidos, garantia legal ainda vigente."
        ),
        acceptance="A10, A9",
        phone="(67) 99789-0123",
        customer_name="Letícia",
        messages=(
            "Me arrependi da minha compra, posso devolver meu pedido?",
            "leticia@gmail.com",
            "Ah, errei. É leticia.rocha@jmail.com",
            "E se o ukulele apresentar defeito?",
        ),
    ),
)


def main(selected: list[str]) -> None:
    settings = load_settings()
    scenarios = [s for s in SCENARIOS if not selected or s.name in selected]
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        run_settings = replace(settings, complaints_path=Path(tmp) / "complaints.jsonl")
        for scenario in scenarios:
            service = build_chat_service(run_settings, clock=lambda: FIXED_NOW)
            turns = []
            for text in scenario.messages:
                reply = service.handle(
                    IncomingMessage(
                        channel="web",
                        phone=scenario.phone,
                        text=text,
                        message_id=str(uuid.uuid4()),
                        customer_name=scenario.customer_name,
                    )
                )
                turns.append((text, reply.text, reply.tools_used))
            path = EXAMPLES_DIR / f"{scenario.name}.md"
            path.write_text(_markdown(scenario, settings.model, turns), encoding="utf-8")
            print(f"wrote {path.relative_to(PROJECT_ROOT)}")


def _markdown(scenario: Scenario, model: str, turns: list) -> str:
    lines = [
        f"# {scenario.title}",
        "",
        f"**O que mostra:** {scenario.shows}",
        "",
        f"**Cenários de aceite (spec §10):** {scenario.acceptance}  ",
        f"**Cliente simulado:** {scenario.phone}"
        + (f" ({scenario.customer_name})" if scenario.customer_name else ""),
        "  ",
        f"**Modelo:** `{model}` · **Data de referência:** quarta-feira, 25/03/2026 14:30",
        "",
        "> Transcrição gerada por `scripts/run_scenarios.py` a partir de uma execução real.",
        "> As respostas usam a formatação do WhatsApp (*negrito*, _itálico_).",
        "",
        "---",
        "",
    ]
    for customer_text, reply, tools in turns:
        lines += [f"**Cliente:** {customer_text}", ""]
        if tools:
            lines += [f"> 🔧 ferramentas: {', '.join(f'`{t}`' for t in tools)}", ""]
        lines += ["**Assistente:**", "", *[f"> {line}" for line in reply.splitlines()], ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main(sys.argv[1:])
