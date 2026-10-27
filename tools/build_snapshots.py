"""Build CC-BY data snapshots from a DueWall pipeline data directory.

Usage:
    python tools/build_snapshots.py --src <duewall>/backtest/server/data --date 2026-10-25

Outputs into data-snapshots/<date>/:
    events.csv          all structured events (flat CSV)
    terms.csv           structured liquidity terms per fund
    pools_snapshot.json Centrifuge pool tokens + DefiLlama RWA pools (copy)
    maturity_wall_sample.json  monthly on-chain maturity distribution (copy)
    MANIFEST.json       snapshot metadata + sha256 of each file

MIT License — Copyright (c) 2026 DueWall Labs
(the *output* snapshots are CC-BY 4.0 — see data-snapshots/LICENSE-CC-BY-4.0.txt)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os

EVENT_FIELDS = [
    "token", "issuer", "event_type", "date", "date_confidence", "date_recurring",
    "settlement", "amount_usd", "amount_pct_of_float", "seniority",
    "source_type", "source_url", "verified_by", "status", "last_updated",
]

TERM_FIELDS = [
    "token", "issuer", "structure", "liquidity", "settlement",
    "min_investment", "min_investment_ccy", "mgmt_fee_bps",
    "inception", "domicile", "base_currency", "aum_usd", "aum_date",
    "status", "source_url",
]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, help="DueWall pipeline data dir")
    ap.add_argument("--date", required=True, help="snapshot date, e.g. 2026-10-25")
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--out", default=os.path.join(here, "data-snapshots"))
    args = ap.parse_args()

    out = os.path.join(args.out, args.date)
    os.makedirs(out, exist_ok=True)

    events = [json.loads(l) for l in open(os.path.join(args.src, "events.jsonl"), encoding="utf-8") if l.strip()]
    legal = [json.loads(l) for l in open(os.path.join(args.src, "legal_doc_events.jsonl"), encoding="utf-8") if l.strip()]

    # 1) events.csv — chain/press events + legal events, one flat table
    with open(os.path.join(out, "events.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EVENT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for e in events + legal:
            w.writerow({k: e.get(k) for k in EVENT_FIELDS})

    # 2) terms.csv — one row per fund with structured terms (latest AUM joined)
    nav = {}
    for e in legal:
        if e["event_type"] == "nav_report" and e.get("amount_usd"):
            prev = nav.get(e["token"])
            if prev is None or (e.get("last_updated") or "") >= (prev.get("last_updated") or ""):
                nav[e["token"]] = e
    with open(os.path.join(out, "terms.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TERM_FIELDS, extrasaction="ignore")
        w.writeheader()
        for e in legal:
            if e["event_type"] != "redemption_window":
                continue
            t = e.get("terms") or {}
            nv = nav.get(e["token"], {})
            w.writerow({
                "token": e["token"], "issuer": e.get("issuer"),
                "structure": t.get("structure"), "liquidity": t.get("liquidity"),
                "settlement": t.get("settlement"),
                "min_investment": t.get("min_investment"),
                "min_investment_ccy": t.get("min_investment_ccy"),
                "mgmt_fee_bps": t.get("mgmt_fee_bps"),
                "inception": t.get("inception"), "domicile": t.get("domicile"),
                "base_currency": t.get("base_currency"),
                "aum_usd": nv.get("amount_usd"), "aum_date": nv.get("date"),
                "status": e.get("status"), "source_url": e.get("source_url"),
            })

    # 3) verbatim JSON copies
    for name in ("pools_snapshot.json", "maturity_wall_sample.json"):
        src = os.path.join(args.src, name)
        if os.path.exists(src):
            with open(src, "rb") as r, open(os.path.join(out, name), "wb") as w:
                w.write(r.read())

    # 4) manifest
    manifest = {"snapshot_date": args.date, "license": "CC-BY-4.0",
                "provenance": "https://duewall.com", "files": {}}
    for name in sorted(os.listdir(out)):
        p = os.path.join(out, name)
        if os.path.isfile(p):
            manifest["files"][name] = {"sha256": sha256(p), "bytes": os.path.getsize(p)}
    with open(os.path.join(out, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)

    print(f"snapshot {args.date} -> {out} ({len(manifest['files'])} files)")


if __name__ == "__main__":
    main()
