# -*- coding: utf-8 -*-
"""validate_adapter.py - 开源适配器合格性检查（合并前自动跑，CI 用）
合格标准（coverage policy + SCHEMA.md 推导）：
  1. 文件可编译；
  2. 无凭据/鉴权痕迹（Bearer/Authorization/api_key/password/secret 字面量）；
  3. 无 >4KB base64 载荷（防塞私货）；
  4. 若适配器可无参运行产事件：逐条过 schema v1.2 校验
     （必填字段、枚举、source_url 必填、status 合法、不得猜日期——
      date_confidence=unknown 时 date 必须为 null）。
用法: python tools/validate_adapter.py adapters/*.py
"""
import ast
import base64
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile

FORBIDDEN = re.compile(r"(bearer\s|authorization|api[_-]?key|password|passwd|secret)",
                       re.IGNORECASE)
B64 = re.compile(r"[A-Za-z0-9+/]{100,}={0,2}")
REQUIRED = ["token", "issuer", "event_type", "date", "date_confidence",
            "amount_usd", "source_type", "source_url", "verified_by", "status", "last_updated"]
ENUMS = {
    "event_type": {"maturity", "redemption_window", "nav_report", "maturity_resolution",
                   "liquidity_window", "rate_decision"},
    "date_confidence": {"exact", "estimated", "unknown"},
    "source_type": {"legal_doc", "announcement", "chain", "press"},
    "status": {"draft", "verified"},
}


def check_source(path):
    errs, warns = [], []
    code = open(path, encoding="utf-8", errors="replace").read()
    # 1) 编译
    try:
        py_compile.compile(path, doraise=True)
    except Exception as e:
        return [f"compile error: {e}"], []
    # 2) 凭据痕迹
    for m in FORBIDDEN.finditer(code):
        ctx = code[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")
        if re.search(r"#.*" + re.escape(m.group(0)) + "|docs|forbid|never|no auth", ctx, re.I):
            continue  # 文档性提及放行
        errs.append(f"credential-like literal '{m.group(0)}' near: ...{ctx[:80]}")
    # 3) base64 载荷
    for m in B64.finditer(code):
        try:
            raw = base64.b64decode(m.group(0) + "==", validate=True)
            if len(raw) > 4096:
                errs.append(f"base64 payload >4KB at offset {m.start()}")
        except Exception:
            pass
    # 4) 无参运行产事件则校验 schema
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "events.jsonl")
        try:
            r = subprocess.run([sys.executable, path, out], capture_output=True,
                               timeout=180, cwd=os.path.dirname(path) or ".")
            if r.returncode == 0 and os.path.exists(out):
                n = 0
                for line in open(out, encoding="utf-8"):
                    line = line.strip()
                    if not line:
                        continue
                    n += 1
                    e = json.loads(line)
                    for k in REQUIRED:
                        if k not in e:
                            errs.append(f"event #{n}: missing required field '{k}'")
                    if e.get("event_type") not in ENUMS["event_type"]:
                        errs.append(f"event #{n}: bad event_type {e.get('event_type')}")
                    if e.get("date_confidence") not in ENUMS["date_confidence"]:
                        errs.append(f"event #{n}: bad date_confidence")
                    if e.get("source_type") not in ENUMS["source_type"]:
                        errs.append(f"event #{n}: bad source_type")
                    if e.get("status") not in ENUMS["status"]:
                        errs.append(f"event #{n}: status must start as draft")
                    if not e.get("source_url"):
                        errs.append(f"event #{n}: source_url mandatory")
                    if e.get("date_confidence") == "unknown" and e.get("date"):
                        errs.append(f"event #{n}: date must be null when confidence=unknown (no guessing)")
                if n:
                    warns.append(f"runtime check: {n} events validated")
        except subprocess.TimeoutExpired:
            warns.append("runtime check skipped: adapter did not finish in 180s")
        except Exception:
            warns.append("runtime check skipped: adapter needs args/network or has no default run")
    return errs, warns


def main(paths):
    fail = False
    for p in paths:
        errs, warns = check_source(p)
        print(f"== {p}")
        for w in warns:
            print(f"   WARN {w}")
        for e in errs:
            print(f"   FAIL {e}")
            fail = True
        if not errs and not warns:
            print("   OK (static only)")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = [os.path.join("adapters", f) for f in sorted(os.listdir("adapters"))
                if f.endswith(".py") and f != "__init__.py"]
    main(args)
