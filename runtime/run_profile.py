# -*- coding: utf-8 -*-
"""run_profile.py - universal adapter runtime 入口
用法: python3 runtime/run_profile.py profiles/<issuer>.json [out.jsonl]
引擎按 profile["engine"] 分发: chain | rest | graphql
所有产出事件经 emit.validate_event（schema v1.2 + 不猜日期规则）。
"""
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ENGINES = {"chain": "engine_chain", "rest": "engine_rest", "graphql": "engine_graphql"}
REQUIRED_TOP = ["profile_version", "issuer", "engine", "mapping"]
ENGINE_KEYS = {"chain": "contract", "rest": "rest", "graphql": "graphql"}


def load_profile(path):
    with open(path, encoding="utf-8") as f:
        p = json.load(f)
    for k in REQUIRED_TOP:
        if k not in p:
            raise ValueError(f"profile missing '{k}'")
    if p["engine"] not in ENGINES:
        raise ValueError(f"unknown engine '{p['engine']}' (need one of {list(ENGINES)})")
    if ENGINE_KEYS[p["engine"]] not in p:
        raise ValueError(f"chain engine profile missing '{ENGINE_KEYS[p['engine']]}' block")
    if p["profile_version"] != 1:
        raise ValueError(f"unsupported profile_version {p['profile_version']}")
    return p


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    profile_path = os.path.abspath(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else None
    profile = load_profile(profile_path)
    engine = importlib.import_module(ENGINES[profile["engine"]])
    events = engine.run(profile, os.path.dirname(profile_path), out_path=out)
    if out:
        from emit import write_jsonl
        write_jsonl(events, out)
        print(f"profile {profile['issuer']} ({profile['engine']}): {len(events)} events -> {out}")
    else:
        for e in events:
            print(json.dumps(e, ensure_ascii=False))
        print(f"# {len(events)} events", file=sys.stderr)
    return events


if __name__ == "__main__":
    main()
