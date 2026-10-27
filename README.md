# duewall-adapters

Open-source extraction adapters and CC-BY data snapshots for
[DueWall](https://duewall.com) — **the maturity calendar for tokenized credit**.

Public on-chain APIs only show settled history. When a tokenized private-credit
loan matures, when a fund's redemption window opens, what the lockup terms are —
that lives in **documents** (loan agreements, fund factsheets), not in chain
state. Example: Maple's public API lists 266 loans, all matured; zero future
maturities are visible on-chain.

DueWall builds the forward-looking calendar by reading those documents. This
repository contains the parts we open:

```
adapters/          issuer extraction adapters (MIT) — turn public sources into
                   structured events
data-snapshots/    periodic CC-BY snapshots of the structured output
tools/             snapshot builder
docs/              event schema, contribution guide
```

## Why open?

1. **Auditability** — every datapoint on duewall.com links back to its source.
   The adapters show exactly how each field was extracted, so you don't have to
   trust us: verify us.
2. **Coverage is communal** — one issuer adapter per module. Contributing an
   adapter for an issuer we don't cover yet extends the calendar for everyone.
3. **Citation-friendly** — data snapshots are CC-BY 4.0: use them in research,
   newsletters, dashboards. Cite and link; that's the whole price.

## Adapter interface (summary)

Each adapter is a self-contained module exposing `fetch() -> list[dict]` and
emitting events that conform to [`docs/SCHEMA.md`](docs/SCHEMA.md). Every event
carries `source_url` and `verified_by`. See
[`adapters/README.md`](adapters/README.md) for the full contract and
[`adapters/maple_loans.py`](adapters/maple_loans.py) for a working example.

## Data snapshots

See [`data-snapshots/`](data-snapshots/) — CSV/JSON, one directory per snapshot
date. License: **CC-BY 4.0** (code in this repo: MIT). Citation formats in
[`data-snapshots/CITATION.md`](data-snapshots/CITATION.md).

## Contributing

Read [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md). In short: one issuer per
adapter, rule-based extraction with per-field source quotes, no scraping of
access-controlled sources, every PR must include sample source documents or
public URLs so reviewers can verify.

## Links

- Live site & weekly digest: https://duewall.com
- Fund/issuer pages with structured terms: https://duewall.com/centrifuge.html
- Analysis: [Why on-chain data can't tell you when tokenized credit matures](https://duewall.com/onchain-maturity-blindspot.html)

## License

- Code: [MIT](LICENSE) © 2026 DueWall Labs
- Data snapshots: [CC-BY 4.0](data-snapshots/LICENSE-CC-BY-4.0.txt)
