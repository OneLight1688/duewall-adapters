# Contributing to duewall-adapters

Thanks for considering an adapter contribution. The goal: one issuer per
module, every field traceable, nothing guessed.

## Ground rules

1. **One issuer (or fund family) per adapter.** `maple_loans.py`,
   `centrifuge_pools.py`, `ondo_gm.py`, …
2. **Public sources only.** Official APIs, public documentation, public IPFS
   gateways. If a source requires login or bypassing a WAF, it's out of scope.
3. **Per-field provenance.** For rule-based extraction, keep the matching rule
   and (where practical) the matched source sentence in the code or test
   fixtures.
4. **Emit schema v1.1 events.** See [`SCHEMA.md`](SCHEMA.md). Unknown = null.
   Never infer a date that isn't in the source.
5. **Include verification fixtures.** A PR adding/updating an adapter must
   include either sample source documents (PDF/JSON) or public URLs, plus the
   events your adapter produces from them, so a reviewer can check every field.
6. **Human verification stays human.** Adapters may set `status: draft`.
   `verified` is only set after a person compares the event against the source
   document.

## Style

- Python 3.10+, stdlib only where possible (`urllib`, `json`); `pdfplumber`
  allowed for PDF extraction.
- No credentials, no endpoints requiring keys, no internal hostnames in code.
- Requests: identify honestly (User-Agent with a contact URL), rate-limit
  yourself, cache responses.

## Process

1. Open an issue describing the issuer, the public source, and the fields you
   expect to extract.
2. PR with adapter + fixtures + sample output.
3. Reviewer verifies fields against the fixtures, then merges.

## Reporting data errors

If you spot a wrong value on duewall.com: open an issue with the page URL, the
field, and the correct value **with its source**. We correct fast and publicly.
