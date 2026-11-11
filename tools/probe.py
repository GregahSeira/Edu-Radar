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
    "https://www.bing.com/news/search?q=SNBT+OR+UTBK+OR+SNBP&format=rss&setmkt=id-ID",
    "https://www.antaranews.com/rss/humaniora.xml",
    "https://www.antaranews.com/rss/pendidikan.xml",
    "https://www.jpnn.com/index.php?mib=rss",
    "https://www.suara.com/rss/edukasi",
    "https://www.medcom.id/rss/terkini.xml",
    "https://lapi.kumparan.com/v2.0/rss/",
    "https://www.kemdiktisaintek.go.id/feed",
    "https://www.kemdiktisaintek.go.id/rss",
    "https://snpmb.id/feed",
    "https://www.beritasatu.com/rss",
    "https://www.merdeka.com/feed/",
]


def robots_lines(base):
    try:
        r = requests.get(base + "/robots.txt", headers={"User-Agent": main.UA}, timeout=15)
        return {"status": r.status_code, "full": r.text[:3000]}
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
