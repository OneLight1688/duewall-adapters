# -*- coding: utf-8 -*-
"""emit.py - universal adapter runtime 公共层：事件构造 + schema v1.2 校验
所有引擎产出的事件必须过这里（规则与 docs/SCHEMA.md 一致）：
  - 必填字段齐全、枚举合法
  - source_url 强制
  - 不猜日期: date_confidence=unknown 时 date 必须为 null
  - status 默认 draft（verified 只能来自人工核验）
"""
import json
import os
from datetime import datetime, timezone

REQUIRED = ["token", "issuer", "event_type", "date", "date_confidence",
            "amount_usd", "amount_pct_of_float", "seniority",
            "source_type", "source_url", "verified_by", "status", "last_updated"]
ENUMS = {
    "event_type": {"maturity", "redemption_window", "nav_report", "maturity_resolution",
                   "liquidity_window", "rate_decision"},
    "date_confidence": {"exact", "estimated", "unknown"},
    "source_type": {"legal_doc", "announcement", "chain", "press"},
    "status": {"draft", "verified"},
}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SafeDict(dict):
    """format_map 容错：缺键留空占位，不炸"""
    def __missing__(self, key):
        return "{" + key + "}"


def render(tpl, ctx):
    if not isinstance(tpl, str):
        return tpl
    return tpl.format_map(SafeDict(ctx))


def validate_event(e):
    for k in REQUIRED:
        if k not in e:
            raise ValueError(f"missing required field '{k}': {e.get('token')}")
    if e["event_type"] not in ENUMS["event_type"]:
        raise ValueError(f"bad event_type {e['event_type']}")
    if e["date_confidence"] not in ENUMS["date_confidence"]:
        raise ValueError(f"bad date_confidence {e['date_confidence']}")
    if e["source_type"] not in ENUMS["source_type"]:
        raise ValueError(f"bad source_type {e['source_type']}")
    if e["status"] not in ENUMS["status"]:
        raise ValueError(f"bad status {e['status']}")
    if not e.get("source_url"):
        raise ValueError(f"source_url mandatory: {e.get('token')}")
    if e["date_confidence"] == "unknown" and e.get("date"):
        raise ValueError(f"no-guessing: date must be null when confidence=unknown: {e['token']}")
    return e


def make_event(token, issuer, event_type, date, date_confidence, amount_usd,
               source_type, source_url, verified_by, status="draft",
               date_recurring=None, terms=None, extra=None):
    e = {
        "token": token, "issuer": issuer, "event_type": event_type,
        "date": date, "date_confidence": date_confidence,
        "date_recurring": date_recurring,
        "amount_usd": amount_usd, "amount_pct_of_float": None, "seniority": None,
        "source_type": source_type, "source_url": source_url,
        "verified_by": verified_by, "status": status,
        "last_updated": now_iso(),
    }
    if terms:
        e["terms"] = terms
    if extra:
        e["extra"] = extra
    return validate_event(e)


def write_jsonl(events, path):
    if not path:
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
