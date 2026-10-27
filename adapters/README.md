# Adapters

One module per issuer. Each adapter turns a **public** source into
schema-v1.1 events (see [`../docs/SCHEMA.md`](../docs/SCHEMA.md)).

## Contract

```python
def fetch(source: SourceConfig) -> list[dict]:
    """Return a list of events (dicts) conforming to docs/SCHEMA.md.

    - every event carries source_url, verified_by, status="draft"
    - unknown fields are None, never guessed
    - no credentials, no WAF bypass, honest User-Agent, self rate-limited
    """
```

`SourceConfig` is a small dataclass with the issuer namespace, base URLs, and
an output directory for raw response caches (so runs are reproducible).

## Reference implementation

[`maple_loans.py`](maple_loans.py) — enumerates Maple's public GraphQL API
(266 loans, all matured/liquidated) and emits `maturity` events. This adapter
produced the "266 loans, zero future maturities on-chain" finding; it exists
because the chain's archive is the *verification baseline* for the
forward-looking calendar built from documents.

## Roadmap (as we clean them for publication)

- `centrifuge_pools.py` — pool/token metadata + on-chain NAV (public GraphQL)
- `centrifuge_factsheets.py` — IPFS factsheet download + rule-based term
  extraction (the pipeline behind JAAA/JTRSY/SPXA/NYHB terms)
- `defillama_rwa.py` — RWA pool TVL/APY cross-reference
- `ondo_gm.py` — pending first-party API access

If you want to contribute one of these (or an issuer we don't list), read
[`../docs/CONTRIBUTING.md`](../docs/CONTRIBUTING.md) first.
