import pytest

from emporio.catalog import SEARCH_LIMIT, Catalog, availability


@pytest.fixture(scope="module")
def catalog(store):
    return Catalog(store)


def _ids(result):
    return [offer.product.id for offer in result.offers]


def test_browse_by_category_and_price_shows_only_sellable(catalog):
    # A1: "Quais violões até R$ 1000?"
    result = catalog.search(category="Violões", max_price=1000)
    assert result.total_found == 12
    assert len(result.offers) == SEARCH_LIMIT
    assert all(o.sellable and o.price.card_price <= 1000 for o in result.offers)
    prices = [o.price.card_price for o in result.offers]
    assert prices == sorted(prices)
    assert 96 not in _ids(result)  # Giannini GF-3D, out of stock
    assert 113 not in _ids(result)  # Shelby SN-7C, discontinued


def test_specific_product_by_name(catalog):
    # A2: accent/case-insensitive, model code split by the customer
    result = catalog.search(query="takamine GD 20")
    assert _ids(result)[0] == 95
    assert result.offers[0].expired_promotions == ("Oferta Especial (12%)",)


def test_out_of_stock_product_comes_with_similar_alternatives(catalog):
    # A5: Giannini GF-3D Dreadnought (R$ 799,90) is out of stock
    result = catalog.search(query="Giannini GF-3D")
    assert _ids(result)[0] == 96
    assert result.offers[0].availability == "esgotado"

    alternatives = result.alternatives
    assert len(alternatives) == 3
    assert all(o.sellable and o.category == "Violões" for o in alternatives)
    assert all("Dreadnought" in o.product.name for o in alternatives)


def test_discontinued_product_comes_with_similar_alternatives(catalog):
    # A6: Shelby SN-7C 7 Cordas is discontinued
    result = catalog.search(query="Shelby SN-7C")
    assert _ids(result)[0] == 113
    assert result.offers[0].availability == "descontinuado"
    assert all("7 Cordas" in o.product.name for o in result.alternatives)


def test_no_alternatives_when_something_found_is_sellable(catalog):
    assert catalog.search(query="takamine gd20").alternatives == ()


def test_alternatives_by_type(catalog):
    result = catalog.search(query="7 cordas")
    sellable = [o.product.id for o in result.offers if o.sellable]
    assert set(sellable) == {109, 110, 111, 112}


def test_query_of_stopwords_only_finds_nothing(catalog):
    # "quero" alone must not become "browse the whole catalog"
    assert catalog.search(query="quero").total_found == 0
    assert catalog.search(query="quero", category="Ukuleles").total_found > 0


def test_numbers_match_whole_words_only(catalog):
    # "7" must not match the "700" in "Kalani KAL-700T"
    assert 127 not in _ids(catalog.search(query="7", include_unavailable=True))


def test_empty_category_returns_nothing(catalog):
    # A13: wind instruments exist as a category but have no products
    assert catalog.search(category="Instrumentos de Sopro (Madeiras)").total_found == 0
    assert catalog.search(query="saxofone").total_found == 0


def test_categories_in_stock_reflect_the_data_not_the_manual(catalog):
    categories = catalog.categories_in_stock()
    assert "Violões" in categories and "Ukuleles" in categories
    assert not any("Sopro" in c or c == "Cordas Orquestrais" for c in categories)


def test_price_filter_uses_promotional_price(catalog):
    # Crafter HT-100: R$ 2.399 -> R$ 1.967,18 with 18% off
    assert 90 in _ids(catalog.search(query="crafter", max_price=2000))


@pytest.mark.parametrize(
    ("product_id", "expected"),
    [
        (81, "disponível"),
        (93, "últimas unidades"),  # stock 2
        (96, "esgotado"),
        (136, "descontinuado"),  # discontinued even with stock 13
        (130, "em breve"),  # coming soon even with stock 2
    ],
)
def test_availability_labels(store, product_id, expected):
    assert availability(store.products[product_id]) == expected
