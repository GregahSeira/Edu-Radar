#!/usr/bin/env python3
"""edu-radar: pantau RSS dan halaman web, kirim yang baru ke Discord.

Tanpa database. Semua status di state.json. Lihat README.md dan HANDOFF.md.
"""
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; edu-radar/1.0)"
ROBOT_AGENT = "edu-radar"
STATE_PATH = os.environ.get("STATE_PATH", "state.json")
SOURCES_PATH = os.environ.get("SOURCES_PATH", "sources.yml")
DRY = os.environ.get("DRY_RUN") == "1"
FORCE = os.environ.get("FORCE") == "1"
ONLY = os.environ.get("ONLY")
SKIP_ROBOTS = os.environ.get("SKIP_ROBOTS") == "1"  # hanya untuk tes lokal

FAIL_LIMIT = 3  # run gagal/kosong berturut-turut sebelum alert
MAX_NOTIFY = 15  # batas notif per sumber per run
MAX_GRAY = 8  # batas notif abu-abu per sumber per run
MAX_SEEN = 1500
MAX_TITLES = 4000
MAX_HASHES = 4000
GRACE = 120  # detik toleransi interval (hanya untuk sumber dengan every)
WORKERS = 8
GRAY_CHANNEL = None  # diisi dari sources.yml (gray_channel)
GRAY_ON = False  # aktif hanya jika webhook channel itu ada (atau DRY_RUN)


def log(*a):
    print(*a, flush=True)


# ---------- state ----------
def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            st = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        st = {}
    for k in ("seen", "pages", "fail", "alerted", "last_run", "appeared"):
        st.setdefault(k, {})
    st.setdefault("titles", [])
    return st


def save_state(st):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, STATE_PATH)


# ---------- discord ----------
def notify(channel, label, title, body="", link="", silent=False):
    parts = [f"[{label}] {title}".strip()]
    if body:
        parts.append(body)
    if link:
        parts.append(link)
    msg = "\n".join(parts)[:1900]
    hook = os.environ.get("DISCORD_WEBHOOK_" + channel.upper())
    if DRY or not hook:
        log(f"--> #{channel}: {msg!r}")
        return True
    for _ in range(3):
        try:
            payload = {"content": msg, "allowed_mentions": {"parse": []}}
            if silent:
                payload["flags"] = 4096 | 4  # tanpa notifikasi dan tanpa pratinjau tautan
            r = requests.post(hook, json=payload, timeout=20)
            if r.status_code == 429:
                time.sleep(float(r.json().get("retry_after", 2)) + 0.5)
                continue
            r.raise_for_status()
            time.sleep(0.4)
            return True
        except Exception as e:  # noqa: BLE001
            log(f"discord gagal ({channel}): {e}")
            time.sleep(1.5)
    return False


# ---------- fetch (robots.txt + paralel) ----------
_robots = {}


def robots_ok(url):
    if SKIP_ROBOTS:
        return True
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    rp = _robots.get(base)
    if rp is None:
        rp = robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=15)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
            else:
                rp.parse([])  # tidak ada robots.txt = boleh
        except Exception:  # noqa: BLE001
            rp.parse([])  # robots tidak terbaca = anggap boleh
        _robots[base] = rp
    return rp.can_fetch(ROBOT_AGENT, url)


def fetch(url):
    if not robots_ok(url):
        raise PermissionError("robots.txt melarang URL ini, sumber dilewati")
    last = None
    for _ in range(2):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=25)
            r.raise_for_status()
            return r.content
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2)
    raise last


def prefetch(urls):
    out = {}

    def one(u):
        try:
            return u, fetch(u), None
        except Exception as e:  # noqa: BLE001
            return u, None, e

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for u, body, err in ex.map(one, urls):
            out[u] = (body, err)
    return out


# ---------- filter ----------
def compile_filters(raw):
    out = {}
    for name, d in (raw or {}).items():
        out[name] = {
            k: (re.compile("|".join(d[k]), re.I) if d.get(k) else None)
            for k in ("core", "topic", "anchor", "weak", "exclude")
        }
    return out


def classify(f, text):
    """2 = lolos, 1 = abu-abu (topik tanpa penanda, kirim senyap), 0 = buang."""
    if f is None:
        return 2
    if f["exclude"] and f["exclude"].search(text):
        return 0
    if f["core"] and f["core"].search(text):
        return 2
    if f["topic"] and f["topic"].search(text):
        return 2 if (f["anchor"] and f["anchor"].search(text)) else 1
    if f["weak"] and f["weak"].search(text):
        return 1
    return 0


def passes(f, text):
    return classify(f, text) == 2


def slug_of(link):
    return re.sub(r"[-_/]+", " ", urlparse(link).path).lower()


def split_outlet(title, e):
    """Google News: judul berakhiran " - Nama Media". Pisahkan agar dedup lintas media jalan."""
    outlet = ((e.get("source") or {}).get("title") or "").strip()
    if outlet and title.endswith(" - " + outlet):
        title = title[: -len(outlet) - 3]
    elif " - " in title:
        title, _, outlet = title.rpartition(" - ")
    return title.strip(), outlet.strip()


def filter_text(item):
    # baris mode links: "judul | url". Cek judul + slug saja, host jangan ikut (host bisa memuat kata filter).
    if " | " in item:
        a, _, u = item.rpartition(" | ")
        return f"{a} {slug_of(u)}"
    return item


def clean(html, n=220):
    t = BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)
    t = re.sub(r"\s+", " ", t)
    return t[:n] + ("..." if len(t) > n else "")


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()[:70]


# ---------- rss ----------
def run_rss(src, st, filters, body):
    sid = src["id"]
    feed = feedparser.parse(body)
    entries = feed.entries
    if not entries:
        raise RuntimeError("feed kosong atau tidak terbaca")
    first = sid not in st["seen"]
    seen = list(st["seen"].get(sid, []))
    seenset = set(seen)
    new = []
    for e in entries:
        eid = e.get("id") or e.get("link") or e.get("title")
        if eid and eid not in seenset:
            new.append((eid, e))
    failed = set()
    if first:
        log(f"[{sid}] seed {len(new)} item")
    else:
        f = filters.get(src.get("filter")) if src.get("filter") else None
        hf = filters.get(src.get("host_filter")) if src.get("host_filter") else None
        hosts = src.get("host_match") or []
        hits, gray, batch = [], [], set()
        for eid, e in reversed(new):
            link = e.get("link", "")
            title = (e.get("title") or "").strip()
            if src.get("strip_outlet"):
                title, summ = split_outlet(title, e)
                slug = ""  # tautan Google berupa token acak, jangan dicek filter
            else:
                summ = clean(e.get("summary", ""))
                slug = slug_of(link)
            text = f"{title} {summ} {slug}"
            use = hf if (hosts and any(urlparse(link).netloc.endswith(h) for h in hosts)) else f
            tier = classify(use, text)
            if tier == 0 or (tier == 1 and not GRAY_ON):
                continue
            key = norm_title(title)
            if key and (key in st["titles"] or key in batch):
                continue
            batch.add(key)
            (hits if tier == 2 else gray).append((eid, title, summ, link, key))
        for eid, title, summ, link, key in hits[:MAX_NOTIFY]:
            if notify(src["channel"], src["label"], title, summ, link):
                if key:
                    st["titles"].append(key)
            else:
                failed.add(eid)  # Discord gagal: biarkan belum terlihat, coba lagi run depan
        if len(hits) > MAX_NOTIFY:
            notify(src["channel"], src["label"], f"+{len(hits) - MAX_NOTIFY} berita lain dari {src['name']}")
        for eid, title, summ, link, key in gray[:MAX_GRAY]:
            if notify(GRAY_CHANNEL, "LAIN", title, summ, link, silent=True):
                if key:
                    st["titles"].append(key)
            else:
                failed.add(eid)
        if len(gray) > MAX_GRAY:
            log(f"[{sid}] abu-abu dipotong: {len(gray) - MAX_GRAY} tidak dikirim")
        log(f"[{sid}] baru={len(new)} lolos={len(hits)} abu={len(gray)} gagal_kirim={len(failed)}")
    seen.extend(eid for eid, _ in new if eid not in failed)
    st["seen"][sid] = seen[-MAX_SEEN:]


# ---------- page ----------
def page_items(src, html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    ign = re.compile("|".join(src["ignore_regex"]), re.I) if src.get("ignore_regex") else None
    if src.get("mode", "text") == "links":
        items = []
        for a in soup.find_all("a", href=True):
            txt = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if txt:
                items.append(f"{txt} | {urljoin(src['url'], a['href'])}")
    else:
        items = [re.sub(r"\s+", " ", ln).strip() for ln in soup.get_text("\n").splitlines()]
        items = [i for i in items if i]
    if ign:
        items = [i for i in items if not ign.search(i)]
    return list(dict.fromkeys(items))


def h(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def run_page(src, st, filters, body, err):
    sid = src["id"]
    if err is not None:
        if src.get("watch_appear"):
            log(f"[{sid}] belum muncul")
            return
        raise err
    if src.get("watch_appear") and not st["appeared"].get(sid):
        if notify(src["channel"], src["label"], f"Halaman baru muncul: {src['name']}", "", src["url"]):
            st["appeared"][sid] = True
    items = page_items(src, body)
    if not items:
        raise RuntimeError("halaman kosong")
    cur = {h(i): i for i in items}
    first = sid not in st["pages"]
    old = set(st["pages"].get(sid, []))
    if first:
        log(f"[{sid}] seed {len(cur)} baris")
    else:
        f = filters.get(src.get("filter")) if src.get("filter") else None
        added = [t for k, t in cur.items() if k not in old and passes(f, filter_text(t))]
        if added:
            shown = [a[:200] for a in added[:8]]
            msg = "\n".join("- " + s for s in shown)
            if len(added) > 8:
                msg += f"\n(+{len(added) - 8} baris lain)"
            if not notify(src["channel"], src["label"], f"Berubah: {src['name']}", msg, src["url"]):
                log(f"[{sid}] kirim gagal, state tidak diubah (coba lagi run depan)")
                return
        log(f"[{sid}] baris baru={len(added)}")
    keep = list(cur) + [k for k in old if k not in cur]
    st["pages"][sid] = keep[:MAX_HASHES]


# ---------- orkestrasi ----------
def due(src, st, now):
    if FORCE or not src.get("every"):
        return True
    return now - st["last_run"].get(src["id"], 0) >= int(src["every"]) * 60 - GRACE


def health_ok(src, st):
    sid = src["id"]
    if st["alerted"].get(sid):
        notify("sistem", "SISTEM", f"Sumber pulih: {src['name']}")
    st["fail"][sid] = 0
    st["alerted"].pop(sid, None)


def health_bad(src, st, err):
    sid = src["id"]
    n = min(st["fail"].get(sid, 0) + 1, 10)  # batas atas: sumber rusak lama tidak mengubah state terus
    st["fail"][sid] = n
    log(f"[{sid}] gagal ({n}): {err}")
    if n >= FAIL_LIMIT and not st["alerted"].get(sid):
        if notify("sistem", "SISTEM", f"Sumber rusak: {src['name']}", f"{n}x gagal berturut-turut. {err}", src["url"]):
            st["alerted"][sid] = True


def main():
    with open(SOURCES_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    filters = compile_filters(cfg.get("filters"))
    global GRAY_CHANNEL, GRAY_ON
    GRAY_CHANNEL = cfg.get("gray_channel")
    GRAY_ON = bool(GRAY_CHANNEL) and (DRY or bool(os.environ.get("DISCORD_WEBHOOK_" + GRAY_CHANNEL.upper())))
    st = load_state()
    now = int(time.time())
    todo = [
        s
        for s in cfg["sources"]
        if s.get("enabled", True) is not False and (not ONLY or s["id"] == ONLY) and due(s, st, now)
    ]
    fetched = prefetch(sorted({s["url"] for s in todo}))
    try:
        for src in todo:
            if src.get("every"):
                st["last_run"][src["id"]] = now
            body, err = fetched[src["url"]]
            try:
                if src["type"] == "rss":
                    if err is not None:
                        raise err
                    run_rss(src, st, filters, body)
                elif src["type"] == "page":
                    run_page(src, st, filters, body, err)
                else:
                    raise ValueError("type tidak dikenal: " + src["type"])
                health_ok(src, st)
            except Exception as e:  # noqa: BLE001
                health_bad(src, st, str(e)[:200])
    finally:
        st["titles"] = st["titles"][-MAX_TITLES:]
        save_state(st)
    hc = os.environ.get("HC_URL")
    if hc and not DRY:
        try:
            requests.get(hc, timeout=15)
        except Exception as e:  # noqa: BLE001
            log(f"heartbeat gagal: {e}")


if __name__ == "__main__":
    sys.exit(main())
