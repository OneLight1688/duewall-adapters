# -*- coding: utf-8 -*-
"""engine_rest.py - rest 引擎：公开 REST API（无鉴权）
profile 片段（rest 引擎）:
  "rest": {"endpoint": "https://yields.llama.fi/pools",
           "list_path": "data",
           "filter": {"field": "project", "op": "contains_any",
                      "values": ["maple", "centrifuge"]},
           "sort_by": "tvlUsd", "sort_desc": true, "limit": 50}
  "mapping": {
    "token": "llama:{pool}", "issuer_field": "project",
    "event_type": "nav_report", "date": "$TODAY", "date_confidence": "exact",
    "amount": {"field": "tvlUsd", "round": 2},
    "source_url": "https://defillama.com/yields/pool/{pool}",
    "extra": {"apy": "{apy}", "pool_name": "{name}", "chain": "{chain}"}}
filter op: contains_any | eq | gte
"""
import json
import urllib.request
from datetime import datetime, timezone

from emit import make_event, render

TODAY = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d")  # noqa: E731


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())


def _walk(obj, path):
    for part in path.split("."):
        obj = obj[part]
    return obj


def _match(row, flt):
    v = row.get(flt["field"])
    op = flt.get("op", "eq")
    if op == "contains_any":
        s = (v or "").lower()
        return any(x.lower() in s for x in flt["values"])
    if op == "eq":
        return v == flt.get("value")
    if op == "gte":
        return (v or 0) >= flt.get("value", 0)
    raise ValueError(f"unknown filter op {op}")


def run(profile, profile_dir, out_path=None):
    issuer = profile["issuer"]
    cfg = profile["rest"]
    mp = profile["mapping"]
    ev_defaults = profile.get("event_defaults", {})
    data = _get(cfg["endpoint"])
    rows = _walk(data, cfg["list_path"]) if cfg.get("list_path") else data
    if cfg.get("filter"):
        rows = [r for r in rows if _match(r, cfg["filter"])]
    if cfg.get("sort_by"):
        rows = sorted(rows, key=lambda r: -(r.get(cfg["sort_by"]) or 0))
    if cfg.get("limit"):
        rows = rows[:cfg["limit"]]

    events = []
    for row in rows:
        ctx = {**row, "today": TODAY()}
        amount = None
        a = mp.get("amount")
        if a:
            amount = row.get(a["field"])
            if amount is not None and a.get("round") is not None:
                amount = round(amount, a["round"])
        etype = mp.get("event_type", "nav_report")
        date = TODAY() if mp.get("date") == "$TODAY" else row.get(mp.get("date"))
        events.append(make_event(
            token=render(mp["token"], ctx), issuer=issuer, event_type=etype,
            date=date, date_confidence=mp.get("date_confidence", "exact"),
            amount_usd=amount,
            source_type=ev_defaults.get("source_type", "press"),
            source_url=render(mp["source_url"], ctx),
            verified_by=ev_defaults.get("verified_by", f"profile_{issuer}_v1"),
            extra={k: render(v, ctx) for k, v in (mp.get("extra") or {}).items()}))
    return events
