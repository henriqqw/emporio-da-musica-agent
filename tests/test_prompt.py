from datetime import datetime

from emporio.config import STORE_TZ
from emporio.prompt import dynamic_context, static_instructions, system_prompt

WEDNESDAY_AFTERNOON = datetime(2026, 3, 25, 14, 30, tzinfo=STORE_TZ)
SATURDAY_EVENING = datetime(2026, 3, 28, 20, 0, tzinfo=STORE_TZ)


def test_static_part_comes_first_and_is_identical_across_requests():
    first = system_prompt(WEDNESDAY_AFTERNOON, "Ana")
    second = system_prompt(SATURDAY_EVENING)
    static = static_instructions()
    assert first.startswith(static)
    assert second.startswith(static)
    assert first != second


def test_static_part_contains_the_whole_manual():
    text = static_instructions()
    assert "Rua 14 de Maio, 3200" in text
    assert "## 10. Disposições finais" in text


def test_dynamic_context_when_open():
    text = dynamic_context(WEDNESDAY_AFTERNOON, "Ana")
    assert "quarta-feira, 25/03/2026 14:30" in text
    assert "aberta" in text
    assert "Ana" in text


def test_dynamic_context_lists_categories_in_stock():
    text = dynamic_context(WEDNESDAY_AFTERNOON, categories_in_stock=["Violões", "Ukuleles"])
    assert "Categorias com produtos disponíveis hoje: Violões, Ukuleles." in text


def test_dynamic_context_when_closed_says_when_team_is_back():
    text = dynamic_context(SATURDAY_EVENING)
    assert "fechada" in text
    assert "segunda-feira, 30/03 às 09:00" in text
    assert "Nome do cliente" not in text
