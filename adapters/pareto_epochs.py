"""pareto_epochs.py - Pareto Credit (IdleCDOEpochVariant) on-chain redemption-wall adapter
Pareto Credit (formerly Idle Finance) runs credit vaults as epoch-based contracts:
  IdleCDOEpochVariant (CDO) behind a TransparentUpgradeableProxy, with an
  IdleCDOEpochQueue for deposit/withdraw requests and IdleCDOTranche AA/BB tokens.

Public, no auth: all state is read via eth_call to verified contracts.
Registry below was discovered on-chain on 2026-11-04 (tranche transfers -> queue
proxy -> idleCDOEpoch() -> CDO) and cross-checked against docs.pareto.credit
/developers + /product/credit-vaults/live-vaults.

Emits DueWall schema v1.2 events (see docs/SCHEMA.md):
  - redemption_window: one per vault per observation (epoch end date + recurrence)
  - nav_report:        vault NAV (getContractValue) as of today

Honesty rules honoured (never guess):
  - epoch end date in the past while isEpochRunning=1  -> date=None, flag stale_onchain_end_date
  - epoch not running / endDate=0 (between epochs)      -> no dated event, flag vault_idle
  - NAV decimals are assumed 6dp (USDC) per live-vaults docs -> flag nav_assumption for
    human verification (all covered vaults are USDC-denominated per docs)

stdlib only. Usage: python3 pareto_epochs.py [out.jsonl]
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

NOW = int(time.time())
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
STAMP = datetime.now(timezone.utc).isoformat(timespec="seconds")
ADAPTER = "adapter_pareto_v0"

RPC = {
    "ethereum": ["https://eth.drpc.org", "https://cloudflare-eth.com", "https://1rpc.io/eth",
                 "https://rpc.flashbots.net", "https://gateway.tenderly.co/public/mainnet",
                 "https://eth-mainnet.public.blastapi.io"],
    "optimism": ["https://optimism-rpc.publicnode.com", "https://1rpc.io/op",
                 "https://optimism.drpc.org", "https://mainnet.optimism.io"],
}
EXPLORER = {"ethereum": "https://etherscan.io/address/",
            "optimism": "https://optimistic.etherscan.io/address/"}

# keccak4 selectors (precomputed; see repo probe history)
SEL = {
    "epochEndDate()": "0x75d1497b",
    "epochDuration()": "0x4ff0876a",
    "bufferPeriod()": "0x0553c2e7",
    "isEpochRunning()": "0xc5c75098",
    "defaulted()": "0x69e25ec1",
    "getContractValue()": "0xdc82697c",
    "AATranche()": "0x44966ba0",
    "BBTranche()": "0xe3e39368",
    "strategy()": "0xa8c62e76",
    "lastEpochApr()": "0x2544e841",
    "idleCDOEpoch()": "0x9343d94e",
}

# Vault registry — discovered on-chain 2026-11-04, cross-checked vs docs.
# docs anchors (app.pareto.credit/vault#0x...) are the AA tranche contracts.
# Bastion Trading (polygon) deferred: blockscout polygon rate-limited during discovery.
REGISTRY = [
    {"name": "Fasanara Digital", "chain": "ethereum",
     "cdo": "0xf6223c567f21e33e859ed7a045773526e9e3c2d5",
     "queue": "0x0b4F695B05902efc14344d19ED1d0B0E061C8A3E",
     "aa": "0x45054c6753b4Bce40C5d54418DabC20b070F85bE",
     "bb": "0xed9cd82076160bbc5f734d596a039baf616d44c4",
     "strategy": "0xc35d078092872ec1f2ae82bcd6f0b6b89f0850de",
     "borrower_type": "basis trading (delta neutral), floating rate"},
    {"name": "Adaptive Frontier", "chain": "ethereum",
     "cdo": "0x14b8e918848349d1e71e806a52c13d4e0d3246e0",
     "queue": "0x5eCF8bF9eae51c2FF47FAc8808252FaCd8e36797",
     "aa": "0xae7913c672c7F1f76C2a1a0Ac4de97d082681234",
     "bb": "0xff80e0de1cc54b110632da8a3296e52590cb2374",
     "strategy": "0xa30be796fb2babf9228359e86a041c14e29f86fc",
     "borrower_type": "high-frequency trading, fixed rate"},
    {"name": "RockawayX Credit", "chain": "ethereum",
     "cdo": "0x9cf358aff79dea96070a85f00c0ac79569970ec3",
     "escrow": "0xB08aFCF83ed084DD7E4df0D83F4f4a2be9109944",
     "aa": "0xEC6a70F62a83418c7fb238182eD2865F80491a8B",
     "bb": "0x53026b3adb9956dd4d4c381e1544c998c38d140d",
     "strategy": "0x3fc0265e92eeafed0ccd9f8621764ce0981882ce",
     "borrower_type": "private credit & DeFi liquidity, fixed rate"},
    {"name": "Abraxas Capital (Heka Elysium Alpha Bitcoin)", "chain": "ethereum",
     "cdo": "0x0ad21c3ac4ffe7c1ed2b1b717cd051ded365fa32",
     "queue": "0xeBa43518e4fddA8D82Ad711DA3b27717779DBdF7",
     "aa": "0x6dbDEeF7a188bEaFFC2c57006e5D8edAf0C0e9e6",
     "bb": "0xaec53e87b91bccb5350244a3b932d89b28de1ea3",
     "strategy": "0xe7e13f902ea13e6eaaa4ed9a2de5898436d12cbf",
     "borrower_type": "cross-market arbitrage, fixed rate"},
    {"name": "FalconX (curated by M11 Credit)", "chain": "optimism",
     "cdo": "0xd2c0d848aa5ad1a4c12be89e713e70b73211989b",
     "queue": "0x463465c334742D72907CA5fB97db44688B4EC3dC",
     "aa": "0x24e16F9Fad32891f8bA69cE8fEdd273A2649331A",
     "bb": "0xb967000b6bb3fcb17018030761da9ea2b7e79c3b",
     "strategy": "0x2bcf124aa4f7f32f0fe54f498d924b934c942b31",
     "borrower_type": "prime brokerage, fixed rate"},
]


def _load_overrides():
    """人工核验 UI 驳回时写入的机器可执行修复（NAV 小数位/官方公布的下一窗口日期）。
    位置: <repo>/data/verification/overrides_pareto.json 或环境变量 PARETO_OVERRIDES"""
    p = os.environ.get("PARETO_OVERRIDES")
    if not p:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "data", "verification", "overrides_pareto.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("vaults", {})
    except Exception:
        return {}


OVERRIDES = _load_overrides()


def rpc_call(chain, method, params, tries=2):
    last = None
    for u in RPC[chain]:
        for i in range(tries):
            try:
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


def call(chain, to, sel):
    return rpc_call(chain, "eth_call", [{"to": to, "data": sel}, "latest"])


def hexint(v):
    return int(v, 16) if v and v != "0x" else 0


def addr(v):
    return "0x" + v[-40:] if v and v != "0x" else None


def recurrence(duration_s):
    d = duration_s / 86400.0
    if duration_s == 0:
        return None
    if d <= 8:
        return "weekly"
    if d <= 15:
        return "bi-weekly"
    if d <= 35:
        return "monthly"
    return f"every {d:.0f}d"


def event(token, etype, date, conf, amount, src_url, recurring=None, terms=None, extra=None):
    e = {
        "token": token, "issuer": "pareto", "event_type": etype,
        "date": date, "date_confidence": conf, "date_recurring": recurring,
        "amount_usd": amount, "amount_pct_of_float": None, "seniority": None,
        "source_type": "chain", "source_url": src_url,
        "verified_by": ADAPTER, "status": "draft", "last_updated": STAMP,
    }
    if terms:
        e["terms"] = terms
    if extra:
        e["extra"] = extra
    return e


def read_vault(v):
    ch = v["chain"]
    cdo = v["cdo"]
    st = {"errors": []}
    for sig in ("epochEndDate()", "epochDuration()", "bufferPeriod()", "isEpochRunning()",
                "defaulted()", "getContractValue()", "lastEpochApr()"):
        s, r = call(ch, cdo, SEL[sig])
        st[sig] = hexint(r) if s == "ok" else None
        if s != "ok":
            st["errors"].append(f"{sig}: {r}")
    return st


def build_events():
    events = []
    for v in REGISTRY:
        ch, cdo = v["chain"], v["cdo"]
        st = read_vault(v)
        nav_raw = st["getContractValue()"]
        ov = OVERRIDES.get(v["aa"].lower(), {})
        nav_dp = int(ov.get("nav_decimals", 6))
        nav_usd = round(nav_raw / (10 ** nav_dp), 2) if nav_raw is not None else None
        base_extra = {
            "human_overrides": {k: ov[k] for k in ("nav_decimals", "next_window_date")
                                if k in ov} or None,
            "cdo": cdo, "queue": v.get("queue"), "escrow": v.get("escrow"),
            "aa_tranche": v["aa"], "bb_tranche": v["bb"], "strategy": v["strategy"],
            "vault_name": v["name"], "chain": ch, "borrower_type": v["borrower_type"],
            "nav_raw": nav_raw,
            "nav_assumption": f"{nav_dp}dp underlying per docs/live-vaults"
                              + (" (human-verified via verification UI)" if "nav_decimals" in ov else ""),
            "epoch_duration_s": st["epochDuration()"],
            "buffer_period_s": st["bufferPeriod()"],
            "is_epoch_running": st["isEpochRunning()"],
            "defaulted": st["defaulted()"],
            "last_epoch_apr_pct": round(st["lastEpochApr()"] / 1e18, 4)
            if st["lastEpochApr()"] else None,
        }
        if st["errors"]:
            base_extra["read_errors"] = st["errors"]
        src = EXPLORER[ch] + cdo

        # nav_report
        events.append(event(
            token=f"pareto:{ch}:{v['aa']}", etype="nav_report",
            date=TODAY, conf="exact", amount=nav_usd, src_url=src,
            extra=dict(base_extra)))

        # redemption_window — only with an honest forward date
        end = st["epochEndDate()"]
        running = bool(st["isEpochRunning()"])
        rec = recurrence(st["epochDuration()"] or 0)
        terms = {
            "structure": "Epoch-based credit vault (AA/BB tranches, IdleCDOEpochVariant)",
            "liquidity": rec, "settlement": "claim after epoch close",
            "base_currency": "USDC",
        }
        if end and end > NOW and running:
            events.append(event(
                token=f"pareto:{ch}:{v['aa']}", etype="redemption_window",
                date=datetime.fromtimestamp(end, tz=timezone.utc).strftime("%Y-%m-%d"),
                conf="exact", amount=nav_usd, src_url=src, recurring=rec,
                terms=terms, extra={**base_extra,
                                    "epoch_end_ts": end,
                                    "window_note": "current running epoch ends; requests queue "
                                                   "for the following epoch (IdleCDOEpochQueue)"}))
        elif end and running:
            # on-chain end date is stale while running (e.g. FalconX) — never guess forward;
            # a human-provided next_window_date override (via verification UI) may fill it in
            next_ov = ov.get("next_window_date")
            events.append(event(
                token=f"pareto:{ch}:{v['aa']}", etype="redemption_window",
                date=next_ov, conf="estimated" if next_ov else "unknown",
                amount=nav_usd, src_url=src, recurring=rec,
                terms=terms, extra={**base_extra, "stale_onchain_end_date": end,
                                    "window_note": ("next window per human-provided override "
                                                    "(official page)" if next_ov else
                                                    "on-chain epochEndDate is in the past while "
                                                    "epoch runs — next end not published on-chain; "
                                                    "human verification required")}))
        else:
            base_extra["vault_idle"] = True
            next_ov = ov.get("next_window_date")
            if next_ov:
                events.append(event(
                    token=f"pareto:{ch}:{v['aa']}", etype="redemption_window",
                    date=next_ov, conf="estimated", amount=nav_usd, src_url=src,
                    recurring=rec, terms=terms,
                    extra={**base_extra, "window_note": "vault idle on-chain; next window per "
                                                        "human-provided override (official page)"}))
            else:
                base_extra["window_note"] = "no epoch running (between epochs) — no dated obligation"
    return events


if __name__ == "__main__":
    evs = build_events()
    out = sys.argv[1] if len(sys.argv) > 1 else None
    lines = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evs)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(lines)
        print(f"wrote {len(evs)} events -> {out}")
    else:
        print(lines, end="")
    n_rw = sum(1 for e in evs if e["event_type"] == "redemption_window")
    navs = {e["extra"]["vault_name"]: e["amount_usd"] for e in evs
            if e["event_type"] == "nav_report"}
    print(f"redemption_windows: {n_rw}, NAV sum: ${sum(v for v in navs.values() if v):,.0f}")
