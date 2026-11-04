# -*- coding: utf-8 -*-
"""engine_chain.py - chain 引擎：链上合约读取（eth_call，无鉴权）
profile 片段（chain 引擎）:
  "chains":  {"ethereum": {"rpc": [...], "explorer": "https://etherscan.io/address/"}}
  "contract": {"calls": {"epochEndDate": "0x75d1497b", ...},
               "entities": [{"id": "fasanara", "chain": "ethereum", "cdo": "0x..",
                             "aa": "0x..", "bb": "0x..", "strategy": "0x..", ...}]}
  "mapping": {
    "token": "pareto:{chain}:{aa}", "source_url": "{explorer}{cdo}",
    "nav": {"call": "getContractValue", "decimals": 6, "fix_key": "nav_decimals",
            "assumption_template": "{nav_dp}dp underlying per docs/live-vaults{ov_note}"},
    "redemption_window": {
        "date_call": "epochEndDate", "running_call": "isEpochRunning",
        "duration_call": "epochDuration", "buffer_call": "bufferPeriod",
        "recurrence": [{"max_days": 8, "label": "weekly"}, ...],
        "window_fix_key": "next_window_date",
        "terms": {"structure": "...", "settlement": "...", "base_currency": "USDC"}},
    "apr": {"call": "lastEpochApr", "scale": 1e18, "precision": 4},
    "extra": {"vault_name": "{name}", "chain": "{chain}", ...}}
语义（诚实规则，与 SCHEMA.md 一致）:
  - epoch 运行且 endDate 在未来 -> exact 日期
  - epoch 运行但 endDate 已过期(stale) -> date=null + stale 标记；
    人工核验 UI 写入 next_window_date override 时填入(confidence=estimated)
  - 无 epoch 运行(idle) -> 不发 dated 事件（有 override 时发 estimated）
overrides 文件: <repo>/data/verification/overrides_<issuer>.json，
  结构 {"vaults": {"<entity_key>": {"nav_decimals": 6, "next_window_date": "YYYY-MM-DD"}}}
"""
import json
import os
import time
from datetime import datetime, timezone

from emit import make_event, render

NOW = lambda: int(time.time())  # noqa: E731
TODAY = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d")  # noqa: E731


def _rpc_call(urls, method, params, tries=2):
    last = None
    for u in urls:
        for i in range(tries):
            try:
                import urllib.request
                body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                                   "params": params}).encode()
                req = urllib.request.Request(
                    u, data=body,
                    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
                r = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
                if "error" in r:
                    return ("revert", r["error"].get("message", "")[:60])
                return ("ok", r["result"])
            except Exception as e:
                last = e
                time.sleep(0.6 * (i + 1))
    return ("err", str(last)[:60])


def _hexint(v):
    return int(v, 16) if v and v != "0x" else 0


def _overrides(profile_dir, issuer):
    p = os.environ.get(f"OVERRIDES_{issuer.upper()}")
    if not p:
        p = os.path.join(profile_dir, "..", "data", "verification",
                         f"overrides_{issuer}.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("vaults", {})
    except Exception:
        return {}


def _recurrence(buckets, duration_s):
    if not duration_s:
        return None
    d = duration_s / 86400.0
    for b in buckets:
        if d <= b["max_days"]:
            return b["label"]
    return f"every {d:.0f}d"


def run(profile, profile_dir, out_path=None):
    issuer = profile["issuer"]
    chains = profile["chains"]
    calls = profile["contract"]["calls"]
    mp = profile["mapping"]
    overrides = _overrides(profile_dir, issuer)
    ev_defaults = profile.get("event_defaults", {})
    verified_by = ev_defaults.get("verified_by", f"profile_{issuer}_v1")
    events = []
    errors = []

    for ent in profile["contract"]["entities"]:
        ch = ent["chain"]
        rpc = chains[ch]["rpc"]
        cdo = ent["cdo"]
        vals, ctx = {}, {}
        for name, sel in calls.items():
            st, r = _rpc_call(rpc, "eth_call", [{"to": cdo, "data": sel}, "latest"])
            vals[name] = _hexint(r) if st == "ok" else None
            if st != "ok":
                errors.append(f"{ent['id']}/{name}: {r}")
        ov = overrides.get((ent.get("entity_key") or ent.get("aa", "")).lower(), {})
        nav_cfg = mp["nav"]
        nav_dp = int(ov.get(nav_cfg.get("fix_key", "nav_decimals"),
                            nav_cfg.get("decimals", 6)))
        nav_raw = vals.get(nav_cfg["call"])
        nav_usd = round(nav_raw / (10 ** nav_dp), 2) if nav_raw is not None else None
        apr_cfg = mp.get("apr")
        apr = (round(vals.get(apr_cfg["call"], 0) / apr_cfg["scale"], apr_cfg.get("precision", 4))
               if apr_cfg and vals.get(apr_cfg["call"]) else None)
        ctx = {
            **{k: v for k, v in ent.items()},
            "chain": ch, "explorer": chains[ch]["explorer"], "today": TODAY(),
            "nav_raw": nav_raw, "nav_usd": nav_usd, "nav_dp": nav_dp,
            "ov_note": " (human-verified via verification UI)"
                       if nav_cfg.get("fix_key") in ov else "",
            "human_overrides": {k: ov[k] for k in ov if not k.startswith("set_")}
                               or None,
            "last_epoch_apr_pct": apr,
        }
        extra = {k: render(v, ctx) for k, v in (mp.get("extra") or {}).items()}
        for k, v in list(extra.items()):
            if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                name = v[1:-1]
                extra[k] = vals.get(name, ctx.get(name))
        extra.update({k: ctx[k] for k in ("nav_raw", "human_overrides", "last_epoch_apr_pct")
                      if k not in extra and ctx.get(k) is not None})
        src = render(mp["source_url"], ctx)
        token = render(mp["token"], ctx)

        events.append(make_event(
            token=token, issuer=issuer, event_type="nav_report",
            date=TODAY(), date_confidence="exact", amount_usd=nav_usd,
            source_type=ev_defaults.get("source_type", "chain"), source_url=src,
            verified_by=verified_by, extra=dict(extra)))

        rw = mp.get("redemption_window")
        if not rw:
            continue
        end = vals.get(rw["date_call"])
        running = bool(vals.get(rw["running_call"]))
        rec = _recurrence(rw.get("recurrence", []), vals.get(rw.get("duration_call")) or 0)
        terms = {k: render(v, ctx) for k, v in rw.get("terms", {}).items()}
        next_ov = ov.get(rw.get("window_fix_key", "next_window_date"))
        rw_extra = dict(extra)

        if end and end > NOW() and running:
            events.append(make_event(
                token=token, issuer=issuer, event_type="redemption_window",
                date=datetime.fromtimestamp(end, tz=timezone.utc).strftime("%Y-%m-%d"),
                date_confidence="exact", amount_usd=nav_usd,
                source_type=ev_defaults.get("source_type", "chain"), source_url=src,
                verified_by=verified_by, date_recurring=rec, terms=terms,
                extra={**rw_extra, "epoch_end_ts": end}))
        elif end and running:
            events.append(make_event(
                token=token, issuer=issuer, event_type="redemption_window",
                date=next_ov, date_confidence="estimated" if next_ov else "unknown",
                amount_usd=nav_usd, source_type=ev_defaults.get("source_type", "chain"),
                source_url=src, verified_by=verified_by, date_recurring=rec, terms=terms,
                extra={**rw_extra, "stale_onchain_end_date": end}))
        else:
            if next_ov:
                events.append(make_event(
                    token=token, issuer=issuer, event_type="redemption_window",
                    date=next_ov, date_confidence="estimated", amount_usd=nav_usd,
                    source_type=ev_defaults.get("source_type", "chain"), source_url=src,
                    verified_by=verified_by, date_recurring=rec, terms=terms,
                    extra=rw_extra))
            else:
                extra["vault_idle"] = True

    if errors:
        for e in events:
            e.setdefault("extra", {})["read_errors"] = errors
    return events
