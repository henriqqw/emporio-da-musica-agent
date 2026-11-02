# Business rules and assumptions

Consolidated from `data/políticas_da_loja.pdf` (v2.1, June 2025) and `data/*.csv`.
The manual is the source of truth for rules; the CSVs are the source of truth for
live data (prices, stock, promotions, orders). Every rule has an ID so the spec,
code and tests can reference it.

Legend: **[M]** taken from the manual · **[D]** derived from the data ·
**[A]** our assumption (ambiguity or inconsistency resolved by us).

## 1. Store information

- **R-INFO-1 [M]** Name: Empório da Música. Address: Rua 14 de Maio, 3200, Centro,
  Campo Grande/MS, CEP 79202-333. Founded 2008. Sells **only musical instruments**.
- **R-INFO-2 [A]** Contacts. The manual gives two numbers: the company table lists
  "Telefone / WhatsApp (67) 3341-4444" and section 7 says "WhatsApp (67) 3321-4500".
  We use **(67) 3341-4444 as phone** and **(67) 3321-4500 as WhatsApp** (section 7
  is the specific one about the channel).
- **R-INFO-3 [A]** E-mail: the company table writes `contato@empóriodamusica.com.br`
  (with an accent, not a valid domain); the cover writes `contato@emporiodamusica.com.br`.
  We use the cover's version.
- **R-INFO-4 [M]** Hours (store and WhatsApp): Mon–Fri 09:00–18:00, Sat 09:00–13:00,
  Sundays and holidays closed. May be extended on special dates (communicated in advance).
- **R-INFO-5 [A]** The assistant answers 24/7 (it *is* the virtual assistant). When a
  request needs a human and it is outside business hours, it tells the customer when
  the team is back. No holiday calendar is available, so holidays are not detected.

## 2. Catalog, availability and scope

- **R-CAT-1 [D]** A product is *sellable* only if `status = active` **and**
  `stock_quantity > 0`.
- **R-CAT-2 [D/A]** Availability shown to the customer (never the raw stock number):
  `disponível` (stock ≥ 3), `últimas unidades` (stock 1–2), `esgotado` (active, stock 0),
  `descontinuado` (`status = discontinued`, regardless of stock), `em breve`
  (`status = coming_soon`, regardless of stock).
  - Data quirks: product 136 is discontinued with stock 13; product 130 is
    coming_soon with stock 2 and already appears in a delivered order (#3). `status`
    wins over `stock_quantity` in both cases.
- **R-CAT-3 [M]** Out of stock → say it is temporarily unavailable and suggest similar
  sellable products. Discontinued → say it left the catalog and suggest equivalents.
  Never confirm availability without querying the data.
- **R-CAT-4 [D]** Categories 6, 7 and 8 (sopros madeiras/metais, cordas orquestrais)
  exist but have no products. The manual mentions "300+ instruments"; the data has 65.
  The agent only states what is in the data: "no momento não temos opções nessa
  categoria".
- **R-CAT-5 [M]** Accessories (cordas, palhetas, cabos, cases, pedais, amplificadores)
  are not sold → polite redirect. **[A]** The manual says "suggest partner stores when
  possible", but none are listed, so the agent does not name any.
- **R-CAT-6 [A]** Anything unrelated to the store (homework, other stores, general
  chit-chat beyond a greeting) → polite refusal and offer of what it can help with.

## 3. Prices, promotions and payment

All computed by deterministic code, never by the LLM.

- **R-PRICE-1 [D]** Table price = `products.price_brl`.
- **R-PRICE-2 [M/D]** A promotion applies only if `promotions.is_active = 1`.
  Inactive rows are history. **[A]** If a product had more than one active promotion
  the highest discount would apply (promotions are not cumulative); no product has
  that today.
- **R-PRICE-3 [M]** A promotional price is always shown together with the original
  price and the discount percentage.
- **R-PRICE-4 [M]** PIX: 5% off the **table** price. Not applied on top of a
  promotional price (not cumulative).
- **R-PRICE-5 [M]** Promotion asked about but not active (e.g. Takamine GD20, promo #4
  "Oferta Especial" is inactive) → say it is no longer valid and show the current price.
  Never promise an expired discount.
- **R-PAY-1 [M]** Methods: PIX (à vista), débito (à vista, todas as bandeiras),
  crédito (até 12x sem juros), boleto (à vista, compensação em até 3 dias úteis).
- **R-PAY-2 [A]** Installments. The payment table says "parcela mínima de R$ 100,00"
  for credit, while section 3.1 gives tiers. We use the more specific section 3.1:
  - 2x–3x: minimum installment R$ 50,00 (we read "sem valor mínimo (exceto abaixo de
    R$ 50,00)" as "the installment cannot be below R$ 50,00");
  - 4x–6x: minimum R$ 80,00;
  - 7x–12x: minimum R$ 100,00.
  Max installments = largest n ≤ 12 whose installment (price / n) meets the tier
  minimum; 1x always allowed. Computed on the price actually charged (promotional if
  active, otherwise table price).
- **R-PAY-3 [M]** Mixing payment methods (e.g. PIX + card) only for purchases above
  R$ 2.000,00.
- **R-PRICE-6 [A]** Price filters ("até R$ 1000") compare against the price the customer
  pays on card (promotional if active, otherwise table price), not the PIX price.

## 4. Shipping

- **R-SHIP-1 [M]** Campo Grande metro region: free above R$ 500,00, otherwise R$ 35,00;
  1–3 business days, own motoboy, customer is called before delivery.
  **[A]** "Região metropolitana" is treated as the city of Campo Grande.
- **R-SHIP-2 [M]** Other cities: Correios PAC (5–12 d.u.), SEDEX (2–5 d.u.), Jadlog
  (3–8 d.u.), all tracked and insured. Price depends on CEP, weight and size; large
  instruments (baterias acústicas, pianos digitais, contrabaixos) may need a special
  quote. **[A]** The agent cannot quote this freight (no rate table) and says it is
  calculated at checkout / by the team with the CEP.
- **R-SHIP-3 [M]** Damaged delivery: refuse the package and contact the store.
- **R-SHIP-4 [M]** Tracking code sent by e-mail and WhatsApp when dispatched; format
  `BR` + 9 alphanumerics + `BR`; trackable on the Correios / Jadlog sites.

## 5. Orders

- **R-ORD-1 [A]** Order data is personal (LGPD). It is only disclosed after the customer
  is identified by **phone + e-mail of the same registered customer**. The phone comes
  from the channel (the WhatsApp number / the demo's phone field), never from the LLM;
  the e-mail is provided by the customer. Checked inside the tool.
  - Data quirk: customers 11 and 43 share the e-mail `bruno.martins@jmail.com` with
    different phones; the pair (phone, e-mail) still identifies one customer.
- **R-ORD-2 [A]** Status labels (pt-BR):
  `pending` → "recebido, aguardando confirmação do pagamento";
  `confirmed` → "pagamento confirmado, em separação";
  `shipped` → "enviado" (+ tracking code and estimated delivery);
  `delivered` → "entregue";
  `cancelled` → "cancelado" (+ reason from `notes`).
- **R-ORD-3 [D/A]** Totals: show `orders.total_brl` as recorded. Orders #3 and #20
  differ from current prices (prices/discounts change over time); the order total wins.
- **R-ORD-4 [A]** A `shipped` order whose estimated delivery is before the reference
  date is flagged as late; the agent apologises and points the customer to the team.
- **R-ORD-5 [A]** There is no actual delivery date in the data. For `delivered` orders,
  **receipt date = `estimated_delivery`**.

## 6. Returns, exchanges and warranty

Windows are computed by code from the reference date and returned by the order tool.

- **R-RET-1 [M] Arrependimento (online):** up to 7 calendar days after receipt, no
  reason needed; original packaging, unused, with accessories and manuals; refund in the
  original payment method within 10 business days; store pays return freight.
  **[A]** The data has no sales-channel field; all orders are treated as online.
- **R-RET-2 [M] Defeito:** exchange within 30 calendar days **after purchase**
  (`order_date`). After that, warranty with the manufacturer; the store can intermediate.
  Not covered: misuse, drops, excessive humidity, unauthorised modifications.
- **R-RET-3 [M] Preferência (cor/modelo/tamanho):** up to 7 days, subject to stock;
  perfect condition and original packaging; price differences charged or refunded.
  **[A]** Counted from receipt, like arrependimento.
- **R-RET-4 [M] Not eligible:** custom setup / adjustments, "venda final" clearance items,
  wind-instrument mouthpieces (hygiene). **[D]** The data has no flag for these; the
  agent mentions the exceptions when relevant instead of asserting them per order.
- **R-WAR-1 [M]** Legal warranty: 90 days from receipt against manufacturing defects.
  Manufacturer warranty: 6 months to 2 years (see certificate). Not covered: natural wear
  (trastes, cordas, feltros, palhetas), misuse, extreme weather, third-party repairs,
  cosmetic damage that doesn't affect function.
- **R-RET-5 [A]** The agent explains eligibility and next steps; it does not open a return
  (tools are read-only). The customer is directed to the team to proceed.
- Orders that are not `delivered` have no return window yet; `cancelled` orders have none.

## 7. Tone and conversation

- **R-TONE-1 [M]** Informal but professional, welcoming, "a friend who understands music";
  not robotic. Brazilian Portuguese.
- **R-TONE-2 [M]** Flow: greet (by name if available) → understand → look up → answer
  clearly with prices and conditions → ask if anything else is needed.
- **R-TONE-3 [A]** WhatsApp format: short plain text, only `*bold*` and `_italic_`,
  simple lists with "•" or numbers allowed, no tables, no headings, no Markdown links,
  at most one question per message.
- **R-TONE-4 [M]** Complaints: listen with empathy; the manual says register and forward
  to the person in charge, return within 24 business hours. See open question Q2.
- **R-PRIV-1 [M]** LGPD: data used only for orders, communication and (with consent)
  marketing; never shared with third parties for marketing; the customer can ask for
  deletion via WhatsApp or e-mail.

## 8. Reference date

- **R-DATE-1 [A]** The data ends in March 2026 (last order 2026-03-22), while the real
  date is later. Date-dependent logic (return windows, late deliveries, "today") uses
  `REFERENCE_DATE`; `.env.example` sets `2026-03-25` so the dataset is coherent. If unset,
  the real current date (America/Campo_Grande) is used.
