import pytest

from emporio.whatsapp_format import sanitize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("O **Takamine GD20** sai por R$ 2.199,00", "O *Takamine GD20* sai por R$ 2.199,00"),
        ("__parcelado__ em 12x", "_parcelado_ em 12x"),
        ("## Opções", "*Opções*"),
        ("- Yamaha C40\n* Tagima Memphis", "• Yamaha C40\n• Tagima Memphis"),
        (
            "Veja [rastreio](https://rastreamento.correios.com.br)",
            "Veja rastreio (https://rastreamento.correios.com.br)",
        ),
        ("Linha 1\n\n\n\nLinha 2   ", "Linha 1\n\nLinha 2"),
    ],
)
def test_converts_markdown(raw, expected):
    assert sanitize(raw) == expected


def test_flattens_tables():
    raw = "| Modelo | Preço |\n|---|---|\n| Yamaha C40 | R$ 599,90 |"
    assert sanitize(raw) == "Modelo — Preço\nYamaha C40 — R$ 599,90"


def test_keeps_whatsapp_formatting_untouched():
    text = "Oi, Ana! O *Yamaha C40* está _disponível_ 🎸\n• PIX: R$ 569,91"
    assert sanitize(text) == text
