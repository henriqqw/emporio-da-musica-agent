import pytest

from emporio.phone import is_valid_phone, normalize_phone


@pytest.mark.parametrize(
    "raw",
    ["(67) 99812-3456", "67998123456", "+55 67 99812-3456", "5567998123456"],
)
def test_normalizes_common_formats(raw):
    assert normalize_phone(raw) == "67998123456"


def test_landline_with_country_code():
    assert normalize_phone("+55 (67) 3341-4444") == "6733414444"


@pytest.mark.parametrize(("raw", "valid"), [("67998123456", True), ("998123456", False)])
def test_validation(raw, valid):
    assert is_valid_phone(raw) is valid
