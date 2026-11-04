# -*- coding: utf-8 -*-
"""validate_profile.py - profile 合格性检查（CI 用，开源贡献只交数据文件不交代码）
检查：
  1. JSON Schema 校验（jsonschema 可用则严格校验，否则结构自检）；
  2. 无凭据痕迹（同 validate_adapter 规则）；
  3. 运行 profile 产事件，逐条过 emit.validate_event（schema v1.2 + no-guessing）。
用法: python tools/validate_profile.py profiles/*.json
"""
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORBIDDEN = re.compile(r"(bearer\s|authorization|api[_-]?key|password|passwd|secret)",
                       re.IGNORECASE)
SCHEMA = os.path.join(HERE, "profiles", "schema.json")
RUNTIME = os.path.join(HERE, "runtime")


def check(path):
    errs, warns = [], []
    text = open(path, encoding="utf-8").read()
    profile = json.loads(text)

    # 1) schema
    try:
        import jsonschema
        jsonschema.validate(profile, json.load(open(SCHEMA, encoding="utf-8")))
        warns.append("jsonschema: PASS")
    except ImportError:
        warns.append("jsonschema not installed — structural check only (run_profile.load_profile)")
    except Exception as e:
        errs.append(f"schema: {str(e)[:200]}")

    # 2) 凭据痕迹
    for m in FORBIDDEN.finditer(text):
        errs.append(f"credential-like literal '{m.group(0)}' at offset {m.start()}")

    # 3) 运行产事件
    out = os.path.join(os.environ.get("TEMP", "/tmp"), "profile_events.jsonl")
    r = subprocess.run([sys.executable, os.path.join(RUNTIME, "run_profile.py"), path, out],
                       capture_output=True, text=True, timeout=300,
                       cwd=os.path.join(HERE, "runtime"))
    if r.returncode != 0:
        errs.append(f"runtime failed: {(r.stderr or r.stdout).strip()[:200]}")
    else:
        sys.path.insert(0, RUNTIME)
        from emit import validate_event
        n = 0
        for line in open(out, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            n += 1
            try:
                validate_event(json.loads(line))
            except Exception as e:
                errs.append(f"event #{n}: {e}")
        warns.append(f"runtime check: {n} events validated ({r.stdout.strip()[:60]})")
    return errs, warns


def main(paths):
    fail = False
    for p in paths:
        print(f"== {p}")
        try:
            errs, warns = check(p)
        except Exception as e:
            errs, warns = [f"load error: {str(e)[:150]}"], []
        for w in warns:
            print(f"   WARN {w}")
        for e in errs:
            print(f"   FAIL {e}")
            fail = True
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    args = sys.argv[1:] or sorted(
        os.path.join(HERE, "profiles", f) for f in os.listdir(os.path.join(HERE, "profiles"))
        if f.endswith(".json") and f != "schema.json")
    main(args)
