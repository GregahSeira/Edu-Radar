#!/usr/bin/env python3
"""Probe: cek URL dari IP Actions (robots, HTTP, isi feed). Hasil ke probe.json.

Dipakai sekali untuk memverifikasi sumber baru sebelum dinyalakan.
Daftar URL: env PROBE_URLS (satu per baris), atau bawaan di bawah.
"""
import json
import os
import re
import sys
from urllib.parse import urlparse

import feedparser
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main  # noqa: E402

DEFAULT = [
    "https://news.google.com/rss/search?q=SNBT+OR+UTBK+OR+SNBP+OR+SNPMB+when:2d&hl=id&gl=ID&ceid=ID:id",
    "https://news.google.com/rss/search?q=%22jalur+mandiri%22+OR+%22KIP+Kuliah%22+OR+%22masuk+PTN%22+when:2d&hl=id&gl=ID&ceid=ID:id",
    "https://news.google.com/rss/search?q=%22TKA+SMA%22+OR+%22penjurusan+SMA%22+OR+%22tes+kemampuan+akademik%22+when:2d&hl=id&gl=ID&ceid=ID:id",
]


def robots_lines(base):
    try:
        r = requests.get(base + "/robots.txt", headers={"User-Agent": main.UA}, timeout=15)
        keep = [ln for ln in r.text.splitlines() if re.search(r"user-agent|rss|search|news", ln, re.I)]
        return {"status": r.status_code, "lines": keep[:60]}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:200]}


def probe(url):
    row = {"url": url}
    p = urlparse(url)
    row["robots_txt"] = robots_lines(f"{p.scheme}://{p.netloc}")
    row["robots_allows_edu_radar"] = main.robots_ok(url)
    try:
        r = requests.get(url, headers={"User-Agent": main.UA}, timeout=25)
        row["http"] = r.status_code
        row["content_type"] = r.headers.get("content-type")
        feed = feedparser.parse(r.content)
        row["entries"] = len(feed.entries)
        row["feed_title"] = feed.feed.get("title")
        row["sample"] = [
            {
                "title": e.get("title"),
                "link": e.get("link"),
                "id": e.get("id"),
                "published": e.get("published"),
                "source": (e.get("source") or {}).get("title"),
                "summary": (e.get("summary") or "")[:160],
            }
            for e in feed.entries[:8]
        ]
    except Exception as e:  # noqa: BLE001
        row["error"] = str(e)[:300]
    return row


if __name__ == "__main__":
    urls = [u.strip() for u in os.environ.get("PROBE_URLS", "").splitlines() if u.strip()] or DEFAULT
    out = [probe(u) for u in urls]
    json.dump(out, open("probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])
