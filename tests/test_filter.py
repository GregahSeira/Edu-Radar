#!/usr/bin/env python3
"""Uji filter dan konfigurasi. Jalankan: python tests/test_filter.py (atau pytest)."""
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import main  # noqa: E402

CFG = yaml.safe_load(open(os.path.join(ROOT, "sources.yml"), encoding="utf-8"))
CASES = yaml.safe_load(open(os.path.join(ROOT, "tests", "cases.yml"), encoding="utf-8"))["cases"]
FILTERS = main.compile_filters(CFG["filters"])
TIER = {"lolos": 2, "abu": 1, "buang": 0}


def test_cases():
    f = FILTERS["edu"]
    bad = []
    for c in CASES:
        text = main.filter_text(c["t"]) if c.get("link") else c["t"]
        got = main.classify(f, text)
        if got != TIER[c["y"]]:
            bad.append(f"harap {c['y']} dapat {got}: {c['t'][:80]}")
    assert not bad, "\n".join(bad)


def test_filters_shared():
    assert FILTERS.keys() >= {"edu", "strict"}


def test_sources():
    ids = [s["id"] for s in CFG["sources"]]
    assert len(ids) == len(set(ids)), "id sumber ganda"
    for s in CFG["sources"]:
        assert s["type"] in ("rss", "page"), s["id"]
        assert s["url"].startswith(("http://", "https://")), s["id"]
        assert s["channel"] in ("resmi", "berita"), s["id"]
        for k in ("filter", "host_filter"):
            if s.get(k):
                assert s[k] in FILTERS, f"{s['id']}: filter {s[k]} tidak ada"
        if s.get("enabled") is False:
            assert s.get("todo"), f"{s['id']}: nonaktif tanpa todo"
    assert CFG.get("gray_channel") == "lain"


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except AssertionError as e:
                fails += 1
                print("FAIL", name, "\n" + str(e))
    sys.exit(1 if fails else 0)
