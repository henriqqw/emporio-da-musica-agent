"""Product search with availability and prices (spec 5.1, rules R-CAT-*)."""

import re
import unicodedata
from dataclasses import dataclass
from typing import NamedTuple

from emporio.data import Product, Promotion, StoreData
from emporio.pricing import PriceQuote, quote

SEARCH_LIMIT = 8
ALTERNATIVES_LIMIT = 3
LOW_STOCK_THRESHOLD = 2  # 1-2 units left -> "últimas unidades"
_STOPWORDS = {
    *("a", "o", "as", "os", "e", "de", "da", "do", "das", "dos", "em", "um", "uma"),
    *("com", "sem", "para", "pra", "por", "que", "tem", "voces", "quero"),
}


@dataclass(frozen=True)
class Offer:
    product: Product
    category: str
    availability: str
    price: PriceQuote
    expired_promotions: tuple[str, ...]

    @property
    def sellable(self) -> bool:
        return self.availability in ("disponível", "últimas unidades")


class _Match(NamedTuple):
    score: int  # how many query tokens matched
    full: bool  # every token matched
    offer: Offer


@dataclass(frozen=True)
class SearchResult:
    offers: tuple[Offer, ...]
    total_found: int
    # Filled only when nothing found is sellable: similar products the store can sell now.
    alternatives: tuple[Offer, ...] = ()


def availability(product: Product) -> str:
    """Status wins over stock: discontinued/coming_soon are never sellable (R-CAT-2)."""
    if product.status == "discontinued":
        return "descontinuado"
    if product.status == "coming_soon":
        return "em breve"
    if product.stock <= 0:
        return "esgotado"
    if product.stock <= LOW_STOCK_THRESHOLD:
        return "últimas unidades"
    return "disponível"


class Catalog:
    def __init__(self, store: StoreData) -> None:
        self._store = store
        self._promotions: dict[int, list[Promotion]] = {}
        for promo in store.promotions:
            self._promotions.setdefault(promo.product_id, []).append(promo)
        self._category_ids = {_normalize(c.name): c.id for c in store.categories.values()}
        self._search_words = {p.id: set(_words(self._haystack(p))) for p in store.products.values()}

    @property
    def category_names(self) -> list[str]:
        return [c.name for c in self._store.categories.values()]

    def offer(self, product: Product) -> Offer:
        promos = self._promotions.get(product.id, [])
        return Offer(
            product=product,
            category=self._store.categories[product.category_id].name,
            availability=availability(product),
            price=quote(product.price, promos),
            expired_promotions=tuple(
                f"{p.name} ({p.discount_percent:g}%)" for p in promos if not p.is_active
            ),
        )

    def search(
        self,
        query: str | None = None,
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        include_unavailable: bool = False,
    ) -> SearchResult:
        """Best match first, then sellable first, then cheapest.

        Products matching every query token are returned even when unavailable, so the
        agent can say "esgotado"/"descontinuado" and suggest alternatives (R-CAT-3).
        Browsing by category or price shows only sellable products unless asked.
        """
        tokens = _tokens(query or "")
        filtered = bool(category) or min_price is not None or max_price is not None
        if query and not tokens and not filtered:
            return SearchResult(offers=(), total_found=0)  # e.g. "quero": nothing to search
        candidates = self._in_category(category)

        matches: list[_Match] = []
        for product in candidates:
            score = self._score(product, tokens)
            if tokens and score == 0:
                continue
            full_match = not tokens or score == len(tokens)
            offer = self.offer(product)
            if not self._in_price_range(offer, min_price, max_price):
                continue
            if not (offer.sellable or include_unavailable or (tokens and full_match)):
                continue
            matches.append(_Match(score, full_match, offer))

        # Prefer products that match every token; fall back to partial matches.
        if any(m.full for m in matches):
            matches = [m for m in matches if m.full]

        matches.sort(key=lambda m: (-m.score, not m.offer.sellable, m.offer.price.card_price))
        offers = tuple(m.offer for m in matches)
        alternatives: tuple[Offer, ...] = ()
        if offers and not any(offer.sellable for offer in offers):
            alternatives = tuple(self.alternatives(offers[0].product))
        return SearchResult(
            offers=offers[:SEARCH_LIMIT], total_found=len(offers), alternatives=alternatives
        )

    def categories_in_stock(self) -> list[str]:
        """Categories with at least one sellable product (R-CAT-4).

        The manual lists wind and orchestral instruments, but the data has none; this is
        what the agent may claim the store sells.
        """
        in_stock = {p.category_id for p in self._store.products.values() if self.offer(p).sellable}
        return [c.name for c in self._store.categories.values() if c.id in in_stock]

    def alternatives(self, product: Product, limit: int = ALTERNATIVES_LIMIT) -> list[Offer]:
        """Sellable products of the same category, most similar first (R-CAT-3).

        Similarity = type words shared with the product's name ("dreadnought", "7",
        "cordas", "nylon"...), then the closest price.
        """
        wanted = _type_words(product)
        reference_price = self.offer(product).price.card_price
        candidates = [
            offer
            for other in self._store.products.values()
            if other.category_id == product.category_id and other.id != product.id
            if (offer := self.offer(other)).sellable
        ]
        candidates.sort(
            key=lambda o: (
                -len(wanted & _type_words(o.product)),
                abs(o.price.card_price - reference_price),
            )
        )
        return candidates[:limit]

    def _in_category(self, category: str | None) -> list[Product]:
        products = list(self._store.products.values())
        if not category:
            return products
        category_id = self._category_ids.get(_normalize(category))
        return [p for p in products if p.category_id == category_id]

    def _score(self, product: Product, tokens: list[str]) -> int:
        words = self._search_words[product.id]
        return sum(1 for token in tokens if any(_matches(token, w) for w in words))

    def _haystack(self, product: Product) -> str:
        category = self._store.categories[product.category_id].name
        return " ".join([product.name, category, product.description, *product.specs.values()])

    @staticmethod
    def _in_price_range(offer: Offer, min_price: float | None, max_price: float | None) -> bool:
        price = offer.price.card_price
        if min_price is not None and price < min_price:
            return False
        return max_price is None or price <= max_price


def _normalize(text: str) -> str:
    """Lowercase without accents: "Violões" -> "violoes"."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _words(text: str) -> list[str]:
    """Letters and digits split apart, so "GD20", "gd-20" and "gd 20" all match."""
    return re.findall(r"[a-z]+|[0-9]+", _normalize(text))


def _type_words(product: Product) -> set[str]:
    """Words of the name that describe the kind of instrument.

    Drops the brand (first word), model codes ("GF-3D", "KA-15S") and the color, which
    say nothing about what makes two instruments interchangeable.
    "Giannini GF-3D Dreadnought Sunburst" -> {"dreadnought"}.
    """
    _brand, *rest = product.name.split()
    color = _normalize(product.specs.get("color", ""))
    words = set()
    for token in rest:
        is_model_code = "-" in token or (re.search(r"\d", token) and re.search(r"\D", token))
        word = _normalize(token)
        if not is_model_code and word != color:
            words.add(word)
    return words


def _tokens(query: str) -> list[str]:
    return [w for w in _words(query) if w not in _STOPWORDS]


def _matches(token: str, word: str) -> bool:
    """Numbers and short tokens match whole words ("7" must not match "700");
    longer words match by prefix, so singular finds plural ("guitarra" -> "guitarras")."""
    if token.isdigit() or len(token) <= 2:
        return token == word
    return word.startswith(token)
