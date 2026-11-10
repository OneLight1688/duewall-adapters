# Event schema v1.3 — DueWall structured events

All adapters emit a flat list of JSON objects (JSONL), one event per line.
Every field is traceable: `source_url` points at the document or API response
the value came from; `verified_by` identifies the extractor; `status` is the QA
state.

## Fields

| field | type | notes |
|---|---|---|
| `token` | string | `issuer_namespace:pool_or_loan_id:symbol`, e.g. `centrifuge:281474976710663:JAAA`, `maple:loan:0x…` |
| `issuer` | string | lowercase namespace: `maple`, `centrifuge`, `ondo-yield-assets`, … |
| `event_type` | enum | `maturity` \| `redemption_window` \| `nav_report` \| `maturity_resolution` \| `liquidity_window` \| `rate_decision` |
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

## `maturity_resolution` events (v1.2)

Emitted **after** a maturity date passes, recording how it resolved. This is
what turns expired dates into a backtestable corpus: a maturity wall only has
analytical value once you know whether it was paid, rolled, extended, or
defaulted.

| extra field | type | notes |
|---|---|---|
| `resolution` | enum | `paid` \| `rolled` \| `extended` \| `defaulted` \| `refinanced` \| `liquidated` |
| `chain_state` | string | raw on-chain/issuer state the resolution was derived from |
| `maturity_date` | string | the original maturity date this resolution belongs to |

Rules:
- `date` on a resolution event is the **observation date** (when the outcome
  was recorded); the original obligation date lives in
  `extra.maturity_date` — never conflate the two.
- Resolutions are never guessed while an obligation is still pending; the
  event is only emitted once a terminal state is observable.
- Chain-state mappings are explicit per adapter (e.g. Maple: `Matured` →
  `paid`, `Liquidated`/`LiquidatedAndClaimed` → `liquidated`). Document-derived
  resolutions require a quoted source sentence (human-verified).

## `liquidity_window` events (v1.3 — E1 evergreen liquidity layer)

On-chain observable liquidity events for evergreen/auto-renewing funds, where
every record carries block + txHash (currently: Centrifuge epoch redeems).
This is the **outcome** leg of the E1 ledger: the pending redemption queue is
the promise (snapshotted daily into `centrifuge_liquidity.json`), and each
approved execution below is the recorded outcome — together they form a
verifiable promise-vs-outcome corpus.

| extra field | type | notes |
|---|---|---|
| `stage` | enum | `approved` (redemption executed) — pending orders stay in the queue snapshot, never emitted as events |
| `epoch_index` | number | Centrifuge epoch sequence the execution belongs to |
| `shares` | number | approved share amount (raw on-chain units) |
| `tx_hash` | string | settlement transaction hash |
| `block` | number | block number |
| `pool_name` | string | human pool name from pool metadata |

Rules:
- `date` = `approved_at` — the date the redemption was actually executed.
- `amount_usd` is an estimate (shares × latest tokenPrice) and says so in
  `extra.amount_basis` — never presented as an exact settled value.
- Only permanent executions become events; transient queue states stay in the
  snapshot. Append-only: events are never rewritten or deleted.

## `rate_decision` events (v1.3 — R1 rate-decision layer)

Machine-detected reference-rate changes (currently: Sky Savings Rate via
sUSDS `convertToAssets` accumulator diff — DCR v1.0 series). Each event =
one detected change in the reference rate.

| extra field | type | notes |
|---|---|---|
| `series` | string | `DCR` — the published reference-rate series (rules hash on methodology page) |
| `rate_prev_pct` | number | previous annualized rate (%), null on first print |
| `rate_pct` | number | new annualized rate (%) |
| `detected_by` | string | e.g. `daily accumulator diff` |

Rules:
- `date` = first daily print at the new rate; `date_confidence` = `estimated`
  (the daily accumulator diff gives date granularity, not block granularity —
  the change took effect some time in the preceding interval).
- `amount_usd` is always null — rate events carry no principal.
- No guessing about governance mechanics: the event records the observed rate
  change, not the vote/proposal that caused it. Proposal metadata lives in the
  R1 pending-decision snapshot, never conflated with the decision event.

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
   moves it to `verified`. Both states are displayed publicly. On approval the
   verification system records `human_verified_at` (ISO timestamp) and keeps
   `verified_by` = the extractor id — never overwrite `verified_by`, downstream
   tooling groups on it.
4. Never scrape access-controlled sources. Public APIs, official docs, public
   IPFS gateways only.
