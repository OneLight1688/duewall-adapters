# Issuer Profile Spec v1 — universal adapter runtime

**One runtime, many profiles.** A new issuer no longer means new adapter code: it
means a declarative profile (JSON) describing *where* the data lives and *how* it
maps to schema v1.2 events. The runtime (`runtime/`) owns transport, honesty
rules (no guessing, source_url mandatory, status=draft) and the verification-loop
hooks.

## Structure

```
profiles/
  schema.json          JSON Schema (draft-07) — validated in CI
  pareto_credit.json   chain engine pilot (5 credit vaults, eth_call only)
  maple_loans.json     graphql engine pilot (loan maturities + resolutions)
  defillama_rwa.json   rest engine pilot (TVL/APY cross-reference)
runtime/
  run_profile.py       entry: python3 runtime/run_profile.py profiles/<x>.json [out.jsonl]
  emit.py              event construction + schema v1.2 validation (shared)
  engine_chain.py      eth_call reads: address registry + selectors + honest stale/idle policy
  engine_rest.py       public REST: endpoint + filter + field mapping
  engine_graphql.py    public GraphQL/subgraph: query template + mapping + resolution block
```

## Engine semantics (what a profile can express)

| engine | express | not expressible in profile (needs engine change) |
|---|---|---|
| `chain` | contract addresses, function selectors, NAV decimals, recurrence buckets, stale/idle policy, per-entity extras | new contract semantics (e.g. a protocol without epochEndDate) |
| `rest` | endpoint, list path, filters, field mapping, extra templates | paginated/authenticated APIs (stay excluded per policy) |
| `graphql` | query template, date/amount transforms, maturity_resolution state map | nested multi-query joins |

**Rule of containment:** anything that doesn't fit the profile schema is an engine
change — decided by a maintainer (AI run), never crammed into config flags. This
keeps profiles boring, reviewable, and safely auto-mergeable.

## Verification loop integration

- `verified_by` in `event_defaults` is the verification-queue grouping key — keep
  it stable across profile revisions.
- Human-verification overrides live at `<repo>/data/verification/overrides_<issuer>.json`
  (written by the `/ops/verify/` UI on reject), e.g.:
  `{"vaults": {"<entity_key>": {"nav_decimals": 6, "next_window_date": "2026-11-15"}}}`
- Changing a profile changes event `content_hash` → approved items auto-reset to
  pending for re-verification.

## Adding a new issuer (contributor path)

1. Copy the closest pilot profile, adjust entity/endpoint/mapping.
2. `python tools/validate_profile.py profiles/<x>.json` must pass locally.
3. Open a PR with **only the profile file** — CI validates schema + runs it +
   checks every event against schema v1.2, then auto-merges when green.
4. The first events land in the human-verification queue (`/ops/verify/`);
   after human approval they go `verified` and publish via the API.
