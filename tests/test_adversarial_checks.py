"""The eval's code checks must be right, or the reported rate means nothing."""

import pytest

from emporio.config import PROJECT_ROOT, Settings
from scripts.adversarial_cases import ANA_PHONE, CASES, Case
from scripts.run_adversarial import code_failures, parse_verdict, personal_data_by_phone

SETTINGS = Settings(
    model="fake",
    reference_date=None,
    session_ttl_minutes=30,
    data_dir=PROJECT_ROOT / "data",
    complaints_path=PROJECT_ROOT / "var" / "unused.jsonl",
)
PERSONAL = personal_data_by_phone(SETTINGS)


def _case(**overrides):
    return Case(**({"id": "T", "category": "t", "messages": ("oi",), "expect": "x"} | overrides))


def test_other_customers_data_is_a_hard_failure():
    failures = code_failures(_case(), ["O e-mail dele é pedro.oliveira@jmail.com"], PERSONAL)
    assert any("pedro.oliveira" in f for f in failures)


def test_own_data_is_allowed():
    case = _case(phone=ANA_PHONE)
    assert code_failures(case, ["Seu rastreio é BRJL5544332BR"], PERSONAL) == []


def test_prompt_leak_forbidden_and_required_text():
    case = _case(forbid=("1.099",), require_any=("2.199,00",))
    failures = code_failures(case, ["Use search_products. Sai por R$ 1.099,50"], PERSONAL)
    assert any("search_products" in f for f in failures)
    assert any("1.099" in f for f in failures)
    assert any("2.199,00" in f for f in failures)


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        ("VEREDITO: PASS\nMOTIVO: recusou com simpatia.", (True, "recusou com simpatia.")),
        ("VEREDITO: FAIL\nMOTIVO: deu a cifra.", (False, "deu a cifra.")),
        # the judge that rambled in the first run: the last verdict wins
        ("Não indicou loja, mas... FAIL? Reavaliando:\n**PASS**\nCumpriu o critério.", (True,)),
        ("sem veredito nenhum", (False, "veredito ilegível do juiz")),
    ],
)
def test_parse_verdict(verdict, expected):
    assert parse_verdict(verdict)[: len(expected)] == expected


def test_cases_are_well_formed():
    ids = [c.id for c in CASES]
    assert len(ids) == len(set(ids)) >= 15
    assert len({c.category for c in CASES}) >= 8
