"""Maple loans adapter — enumerate Maple's public GraphQL API and emit
schema-v1.1 maturity events.

Why this adapter matters: Maple's public API exposes the *archival* loan book.
As of 2026-10-25 it lists 266 loans, every one matured or liquidated, zero
future-dated maturities. Forward-looking walls live in loan documents — that is
DueWall's document layer. The on-chain archive is the verification baseline.

Public source:
    https://api.maple.finance/v2/graphql   (no key required)
Known quirks:
    - introspection is disabled: fields must be requested explicitly
    - loan ids are hex addresses; `maturityDate` is ISO date or null

Usage:
    python maple_loans.py --out events_maple.jsonl

MIT License — Copyright (c) 2026 DueWall Labs
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request

GRAPHQL_URL = "https://api.maple.finance/v2/graphql"
USER_AGENT = "duewall-adapters/0.1 (https://duewall.com; contact: hello@duewall.com)"
PAGE_LIMIT = 100  # server-side page size
MAX_PAGES = 20    # hard safety stop

QUERY = """
query($skip: Int!, $limit: Int!) {
  loans(skip: $skip, limit: $limit) {
    id
    maturityDate
    startDate
    principalOwed
    collateralAmount
  }
}
"""


def _post(query: str, variables: dict, timeout: int = 20) -> dict:
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def fetch() -> list[dict]:
    """Return schema-v1.1 maturity events for the Maple loan book (status: draft)."""
    events: list[dict] = []
    seen: set[str] = set()
    for page in range(MAX_PAGES):
        data = _post(QUERY, {"skip": page * PAGE_LIMIT, "limit": PAGE_LIMIT})
        loans = (data.get("data") or {}).get("loans") or []
        if not loans:
            break
        for loan in loans:
            loan_id = loan.get("id")
            if not loan_id or loan_id in seen:
                continue
            seen.add(loan_id)
            maturity = loan.get("maturityDate")
            events.append(
                {
                    "token": f"maple:loan:{loan_id}",
                    "issuer": "maple",
                    "event_type": "maturity",
                    "date": maturity,  # ISO date or None — never guessed
                    "date_confidence": "exact" if maturity else "unknown",
                    "date_recurring": None,
                    "settlement": None,
                    "amount_usd": loan.get("principalOwed") or None,
                    "amount_pct_of_float": None,
                    "seniority": None,  # chain API does not distinguish
                    "source_type": "chain",
                    "source_url": f"https://app.maple.finance/loans/{loan_id}",
                    "verified_by": "adapter_maple_v0",
                    "status": "draft",
                    "extra": {"startDate": loan.get("startDate")},
                }
            )
        time.sleep(1.0)  # be polite
    return events


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="events_maple.jsonl")
    args = ap.parse_args()

    events = fetch()
    future = sum(1 for e in events if (e["date"] or "") > time.strftime("%Y-%m-%d"))
    with open(args.out, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"{len(events)} loans -> {args.out} | future-dated: {future}")


if __name__ == "__main__":
    main()
