# Event schema v1.1 — DueWall structured events

All adapters emit a flat list of JSON objects (JSONL), one event per line.
Every field is traceable: `source_url` points at the document or API response
the value came from; `verified_by` identifies the extractor; `status` is the QA
state.

## Fields

| field | type | notes |
|---|---|---|
| `token` | string | `issuer_namespace:pool_or_loan_id:symbol`, e.g. `centrifuge:281474976710663:JAAA`, `maple:loan:0x…` |
| `issuer` | string | lowercase namespace: `maple`, `centrifuge`, `ondo-yield-assets`, … |
| `event_type` | enum | `maturity` \| `redemption_window` \| `nav_report` |
| `date` | string\|null | ISO `YYYY-MM-DD` when known; null for recurring/open-ended |
| `date_confidence` | enum | `exact` \| `estimated` \| `unknown` |
| `date_recurring` | string\|null | e.g. `daily` — set when the window recurs rather than occurring once |
| `settlement` | string\|null | e.g. `T+0`, `T+1`, `T+0 / T+1` |
| `amount_usd` | float\|null | USD amount (maturity principal, NAV/AUM) |
| `amount_pct_of_float` | float\|null | reserved; null while float data is unavailable |
| `seniority` | string\|null | `senior`/`mezz`/`junior`; chain APIs don't distinguish — usually null |
| `source_type` | enum | `legal_doc` \| `announcement` \| `chain` \| `press` |
| `source_url` | string | **mandatory** — the document/API response this event came from |
| `verified_by` | string | extractor id, e.g. `adapter_maple_v0`, `rule_extract_v0`, `human_verification_20261027` |
| `status` | enum | `draft` (machine-extracted) → `verified` (human-checked against source) |
| `last_updated` | string | ISO timestamp |
| `terms` | object\|null | `redemption_window` only — structured liquidity terms (below) |
| `extra` | object | extractor-specific extras (e.g. `aum_ccy`, `startDate`) |

## `terms` object (redemption_window events)

| field | type | example |
|---|---|---|
| `structure` | string | `Open-ended` |
| `liquidity` | string | `Daily` |
| `settlement` | string | `T+1` or `T+0 / T+1` |
| `min_investment` | number | `500000.0` |
| `min_investment_ccy` | string | `USDC` |
| `mgmt_fee_bps` | number | `50.0` |
| `inception` | string | `July 2025` |
| `domicile` | string | `British Virgin Islands` |
| `base_currency` | string | `USDC` |

Missing fields are **omitted or null — never guessed**. Downstream renders show
"–" for unknowns.

## Extraction rules (hard requirements for adapters)

1. Rule-based first; every accepted field must be traceable to a quoted source
   sentence/JSON path.
2. PDF text is extracted with pdfplumber; beware ligature loss
   (`settlement` → `seément`) — match with `se.?lement`, `di?erent`, etc.
3. `status` starts at `draft`; only a human check against the source document
   moves it to `verified`. Both states are displayed publicly.
4. Never scrape access-controlled sources. Public APIs, official docs, public
   IPFS gateways only.
