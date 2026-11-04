# Contributing to duewall-adapters

Thanks for considering a contribution. The goal: one issuer per profile,
every field traceable, nothing guessed.

## Preferred path: contribute a profile (data, not code)

Most issuers fit the universal runtime — check the three engines
([`docs/PROFILE_SPEC.md`](PROFILE_SPEC.md)): on-chain contract reads (`chain`),
public REST APIs (`rest`), public GraphQL/subgraphs (`graphql`). If yours fits:

1. Copy the closest pilot in [`../profiles/`](../profiles/) and edit the
   addresses/endpoints/mapping — this is the whole contribution.
2. Validate locally: `python tools/validate_profile.py profiles/<x>.json`.
3. Open a PR containing **only the profile file**. CI validates the JSON Schema,
   runs the profile against the live public source and checks every emitted
   event against schema v1.2 — green PRs merge automatically.
4. The first events land in DueWall's human-verification queue; after a human
   check they publish via the free API.

## Legacy path: adapter code (only for genuinely new semantics)

If the issuer's data model doesn't fit any engine (e.g. a protocol with no
epoch/window structure), open an issue first — that's an engine change, reviewed
by maintainers.

## Ground rules (both paths)

1. **One issuer (or fund family) per profile/adapter.**
2. **Public sources only.** Official APIs, public documentation, public IPFS
   gateways, public RPC endpoints. If a source requires login or bypassing a
   WAF, it's out of scope.
3. **Per-field provenance.** `source_url` is mandatory on every event; for
   document extraction keep the matching rule and source sentence in fixtures.
4. **Emit schema v1.2 events.** See [`SCHEMA.md`](SCHEMA.md). Unknown = null.
   Never infer a date that isn't in the source (the runtime rejects
   `date_confidence: unknown` with a non-null `date`).
5. **Verification fixtures.** Adapter-code PRs must include sample sources plus
   produced events; profile PRs are validated by running against the live
   public source in CI.
6. **Human verification stays human.** Emitters may set `status: draft`.
   `verified` is only set after a person compares the event against the source
   (in DueWall's verification UI).

## Style

- Profiles: pure JSON, validated against [`../profiles/schema.json`](../profiles/schema.json).
- Adapter code (legacy path): Python 3.10+, stdlib only where possible
  (`urllib`, `json`); `pdfplumber` allowed for PDF extraction.
- No credentials, no endpoints requiring keys, no internal hostnames.
- Requests: identify honestly (User-Agent with a contact URL), rate-limit
  yourself, cache responses.

## Process

1. Open an issue describing the issuer, the public source, and the fields you
   expect to extract.
2. Profile PR (preferred) or adapter PR + fixtures + sample output.
3. CI validates automatically; a maintainer verifies semantics, then merges.

## Reporting data errors

If you spot a wrong value on duewall.com: open an issue with the page URL, the
field, and the correct value **with its source**. We correct fast and publicly.
