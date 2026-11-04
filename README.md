# duewall-adapters

Open-source extraction adapters and CC-BY data snapshots for
[DueWall](https://duewall.com) — **the maturity calendar for tokenized credit**,
built for the RWA (real-world asset) data ecosystem.

**Why this exists** — everyone publishes TVL and APY for tokenized credit; nobody publishes
*when it comes due*. Chains only record history: Maple's public API lists 266 loans, all
matured, zero forward maturities visible on-chain. The forward-looking layer lives in
documents — factsheets and loan agreements. These adapters read them, with per-field source
links and human verification, to restore the liability time-axis that TradFi investors expect.

Public on-chain APIs only show settled history. When a tokenized private-credit
loan matures, when a fund's redemption window opens, what the lockup terms are —
that lives in **documents** (loan agreements, fund factsheets), not in chain
state. Example: Maple's public API lists 266 loans, all matured; zero future
maturities are visible on-chain.

DueWall builds the forward-looking calendar by reading those documents. This
repository contains the parts we open:

```
runtime/           universal adapter runtime — one engine set (chain/rest/graphql);
                   honesty rules & verification hooks live here (MIT)
profiles/          declarative per-issuer configs (JSON Schema v1) — adding an
                   issuer = a data file, not code
adapters/          legacy per-issuer adapters (MIT) — kept for provenance;
                   new issuers go through profiles
data-snapshots/    periodic CC-BY snapshots of the structured output
tools/             snapshot builder, profile/adapter validators
docs/              event schema, profile spec, contribution guide
```

## Why open?

1. **Auditability** — every datapoint on duewall.com links back to its source.
   The adapters show exactly how each field was extracted, so you don't have to
   trust us: verify us.
2. **Coverage is communal** — one issuer adapter per module. Contributing an
   adapter for an issuer we don't cover yet extends the calendar for everyone.
3. **Citation-friendly** — data snapshots are CC-BY 4.0: use them in research,
   newsletters, dashboards. Cite and link; that's the whole price.

## One runtime, many profiles (summary)

New issuers are **declarative profiles** (JSON), not code: a profile says *where*
the data lives (contract addresses / API endpoints) and *how* fields map to
schema v1.2 events; the runtime owns transport, honesty rules (no guessed dates,
mandatory `source_url`, `status: draft` until human-checked) and the
human-verification overrides. See
[`docs/PROFILE_SPEC.md`](docs/PROFILE_SPEC.md) and the pilots:
[`profiles/pareto_credit.json`](profiles/pareto_credit.json) (on-chain),
[`profiles/maple_loans.json`](profiles/maple_loans.json) (GraphQL),
[`profiles/defillama_rwa.json`](profiles/defillama_rwa.json) (REST).

The legacy adapters in [`adapters/`](adapters/) stay runnable for provenance;
genuinely new *semantics* (a protocol that doesn't fit any profile) are engine
changes, reviewed by maintainers — never crammed into config flags.

## Quickstart

**Just want the data?** (no code required) — grab the latest CSV from
[`data-snapshots/`](data-snapshots/) (coverage rules: [duewall.com/coverage/](https://duewall.com/coverage/))
and cite per
[`data-snapshots/CITATION.md`](data-snapshots/CITATION.md). Or in Python:

```python
import pandas as pd

terms = pd.read_csv("data-snapshots/2026-10-25/terms.csv")
events = pd.read_csv("data-snapshots/2026-10-25/events.csv")

# every row links back to its source document
print(events[["token", "event_type", "date", "status", "source_url"]].head())
```

**Want to refresh the data yourself?** — run an adapter against its public
source (standard library only, no key required):

```bash
python adapters/maple_loans.py --out events_maple.jsonl
# -> 266 loans -> events_maple.jsonl | future-dated: 0
```

## Free public API (no key required)

The full dataset behind this repo is also served as static JSON at
**https://duewall.com/api/v1/** — CORS-enabled, CC-BY 4.0:

```bash
curl https://duewall.com/api/v1/events.json   # all events (schema v1.2)
curl https://duewall.com/api/v1/terms.json    # liquidity terms per fund
curl https://duewall.com/api/v1/pools.json    # pool NAV + TVL/APY snapshot
curl https://duewall.com/api/v1/meta.json     # version, counts, license
```

Docs: **https://duewall.com/api/** · Schema: [`docs/SCHEMA.md`](docs/SCHEMA.md)

## Data snapshots

See [`data-snapshots/`](data-snapshots/) — CSV/JSON, one directory per snapshot
date. License: **CC-BY 4.0** (code in this repo: MIT). Citation formats in
[`data-snapshots/CITATION.md`](data-snapshots/CITATION.md).

**Bitcoin-anchored** — every published manifest carries its own `MANIFEST.ots`
(OpenTimestamps): anyone can verify, without trusting us, that this data existed at its
stated date, unaltered. Daily internal snapshots are hash-chained (each day binds the
previous anchor) and served free via the
[public API](https://duewall.com/api/).

**Source-document hashes** — `FACTSHEETS.json` in each snapshot lists the sha256 of every
issuer factsheet PDF that `legal_doc` events were extracted from, together with the official
source URL. We do not redistribute the documents (publisher copyright); download from the
issuer gateway and verify the hash. Those hashes are covered by the same `MANIFEST.ots`
Bitcoin proof.

## Contributing

Read [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md). In short: **one issuer =
one profile** (a JSON data file — no code to review, CI validates schema + runs
it and checks every emitted event, then auto-merges when green). Public sources
only; nothing guessed; the first events land in human verification before they
publish.

## Links

- Live site & weekly digest: https://duewall.com
- Fund/issuer pages with structured terms: https://duewall.com/centrifuge.html
- Analysis: [Why on-chain data can't tell you when tokenized credit matures](https://duewall.com/onchain-maturity-blindspot.html)

## License

- Code: [MIT](LICENSE) © 2026 DueWall Labs
- Data snapshots: [CC-BY 4.0](data-snapshots/LICENSE-CC-BY-4.0.txt)
