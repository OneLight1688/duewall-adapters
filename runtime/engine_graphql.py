# -*- coding: utf-8 -*-
"""engine_graphql.py - graphql 引擎：公开 GraphQL API / subgraph（无鉴权）
profile 片段（graphql 引擎）:
  "graphql": {"endpoint": "https://api.maple.finance/v2/graphql",
              "query": "{ loans(first:1000) { id state maturityDate startDate principalOwed } }",
              "list_path": "data.loans"}
  "mapping": {
    "token": "maple:loan:{id}", "issuer_field": null,   # issuer 用 profile.issuer
    "event_type": "maturity",
    "date": {"field": "maturityDate", "type": "unix_ts", "null_if_zero": true},
    "amount": {"field": "principalOwed", "type": "raw"},
    "source_url": "https://app.maple.finance/loans/{id}",
    "extra": {"startDate": {"field": "startDate", "type": "unix_ts"}},
    "resolution": {"event_type": "maturity_resolution", "state_field": "state",
                   "date": "$TODAY",
                   "map": {"Matured": "paid",
                           "Liquidated": "liquidated",
                           "LiquidatedAndClaimed": "liquidated"}}}
date/amount type: unix_ts(秒->ISO日期) | raw | float
"""
import json
import time
import urllib.request
from datetime import datetime, timezone

from emit import make_event, render

TODAY = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d")  # noqa: E731


def _gql(url, query, timeout=40):
    req = urllib.request.Request(
        url, data=json.dumps({"query": query}).encode(),
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())


def _walk(obj, path):
    for part in path.split("."):
        obj = obj[part]
    return obj


def _conv(row, spec):
    if isinstance(spec, str):
        return render(spec, {**row, "today": TODAY()})
    v = row.get(spec["field"])
    t = spec.get("type", "raw")
    if t == "unix_ts":
        v = int(v or 0)
        if v == 0 and spec.get("null_if_zero"):
            return None
        return datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%d")
    if t == "float":
        return float(v) if v is not None else None
    return v


def run(profile, profile_dir, out_path=None):
    issuer = profile["issuer"]
    cfg = profile["graphql"]
    mp = profile["mapping"]
    ev_defaults = profile.get("event_defaults", {})
    data = _gql(cfg["endpoint"], cfg["query"])
    rows = _walk(data, cfg["list_path"])

    events = []
    for row in rows:
        ctx = {**row, "today": TODAY()}
        date = _conv(row, mp["date"]) if isinstance(mp["date"], dict) else render(mp["date"], ctx)
        if date is None:
            continue
        amount = _conv(row, mp["amount"]) if isinstance(mp["amount"], dict) else None
        token = render(mp["token"], ctx)
        events.append(make_event(
            token=token, issuer=issuer, event_type=mp.get("event_type", "maturity"),
            date=date, date_confidence="exact", amount_usd=amount,
            source_type=ev_defaults.get("source_type", "chain"),
            source_url=render(mp["source_url"], ctx),
            verified_by=ev_defaults.get("verified_by", f"profile_{issuer}_v1"),
            extra={k: _conv(row, v) for k, v in (mp.get("extra") or {}).items()}))
        res = mp.get("resolution")
        if res:
            mapped = res["map"].get(row.get(res["state_field"]))
            if mapped:
                events.append(make_event(
                    token=token, issuer=issuer, event_type=res["event_type"],
                    date=TODAY() if res.get("date") == "$TODAY" else date,
                    date_confidence="exact", amount_usd=amount,
                    source_type=ev_defaults.get("source_type", "chain"),
                    source_url=render(mp["source_url"], ctx),
                    verified_by=ev_defaults.get("verified_by", f"profile_{issuer}_v1"),
                    extra={"resolution": mapped, "chain_state": row.get(res["state_field"]),
                           "maturity_date": date}))
    return events
