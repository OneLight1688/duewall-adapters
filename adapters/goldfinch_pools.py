"""Goldfinch v2 adapter — enumerate the public Goldsky subgraph and emit
schema-v1.2 maturity events.

Why this adapter matters: Goldfinch's official subgraph (migrated to a public
Goldsky endpoint, no auth required) lists 24 tranched pools and 31 credit
lines — every one already matured as of 2026-10-28. Like Maple, the on-chain
archive is the *verification baseline*; forward-looking obligations live in
loan documents (DueWall's document layer).
Known quirks:
    - Goldsky omits keys for null fields: always use `.get()`, never `[]`
    - `termEndTime` is a unix timestamp (seconds), 0 when unset
Public source:
    https://api.goldsky.com/api/public/project_cmgz2qi2d003xxhp2eqgwfd5o/subgraphs/goldfinch-v2/incident-repair-20260918/gn
    (endpoint published in Goldfinch's official docs: dev.goldfinch.finance)

Usage:
    python goldfinch_pools.py --out events_goldfinch.jsonl

MIT License — Copyright (c) 2026 DueWall Labs
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone

GOLDSKY = ("https://api.goldsky.com/api/public/project_cmgz2qi2d003xxhp2eqgwfd5o/"
           "subgraphs/goldfinch-v2/incident-repair-20260918/gn")
USER_AGENT = "duewall-adapters/0.1 (https://duewall.com; contact: hello@duewall.com)"
ADAPTER = "adapter_goldfinch_v0"

QUERY = """
{
  tranchedPools(first: 100) {
    id createdAt termEndTime termStartTime termInSeconds nextDueTime
    principalAmount totalDeposited borrowerContract isPaused
  }
  creditLines(first: 100) { id termEndTime nextDueTime limit }
}
"""


def _gql(query: str, timeout: int = 40) -> dict:
    req = urllib.request.Request(
        GOLDSKY,
        data=json.dumps({"query": query}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _ts_to_date(ts) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def _event(token: str, etype: str, date, amount, extra: dict | None) -> dict:
    e = {
        "token": token,
        "issuer": "goldfinch",
        "event_type": etype,
        "date": date,
        "date_confidence": "exact" if date else "unknown",
        "amount_usd": amount,
        "amount_pct_of_float": None,
        "seniority": None,
        "source_type": "chain",
        "source_url": GOLDSKY,
        "verified_by": ADAPTER,
        "status": "draft",
        "last_updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if extra:
        e["extra"] = extra
    return e


def fetch() -> list[dict]:
    """Return schema-v1.2 maturity events for the Goldfinch v2 book (status: draft)."""
    data = _gql(QUERY)
    pools = data["data"]["tranchedPools"]
    lines = data["data"]["creditLines"]

    events: list[dict] = []
    for p in pools:
        te = int(p.get("termEndTime") or 0)
        if te == 0:
            continue
        events.append(_event(
            f"goldfinch:{p['id'][:10]}:GFPOOL", "maturity", _ts_to_date(te),
            int(p.get("principalAmount") or 0) / 1e6,
            {"termStartTime": _ts_to_date(p.get("termStartTime")),
             "nextDueTime": _ts_to_date(p.get("nextDueTime")),
             "totalDeposited": int(p.get("totalDeposited") or 0) / 1e6,
             "borrowerContract": p.get("borrowerContract"), "isPaused": p.get("isPaused")},
        ))
    for c in lines:
        te = int(c.get("termEndTime") or 0)
        if te == 0:
            continue
        events.append(_event(
            f"goldfinch:{c['id'][:10]}:CREDIT", "maturity", _ts_to_date(te),
            None, {"limit": int(c.get("limit") or 0) / 1e6},
        ))
    return events


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="events_goldfinch.jsonl")
    args = ap.parse_args()

    events = fetch()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    future = sum(1 for e in events if (e["date"] or "") > today)
    with open(args.out, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"{len(events)} events -> {args.out} | future-dated: {future}")


if __name__ == "__main__":
    main()
