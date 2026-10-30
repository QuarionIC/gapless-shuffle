#!/usr/bin/env python3
"""Regenerate episodes.json for Gapless Shuffle from the two public Podbean feeds.

Output format (one row per episode, compact JSON, UTF-8):
    [series, number, suffix, title, pubdate(YYYY-MM-DD, UTC), audio path or URL, duration_seconds]
series is HoP / HPI / HAP / HPC, or "Extra" (number 0) for bonus items.
The page derives each episode's id from (series, number, suffix), so rows must stay stable.
Exit status 0 always; prints a summary. Writes the file only if the content changed.
"""
import json, re, sys, urllib.request, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FEEDS = ["https://feed.podbean.com/hopwag/feed.xml", "https://feed.podbean.com/hopwag2/feed.xml"]
PFX = "https://mcdn.podbean.com/mf/web/"
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
ORDER = {"HoP": 0, "HPI": 1, "HAP": 2, "HPC": 3, "Extra": 4}
TITLE_RE = re.compile(r"^(HoP|HAP|HPI|HPC)\s*(\d+)([a-z])?[\s.\-–:]*(.*)$", re.S)


def parse_title(t):
    t = t.replace(" ", " ")
    m = TITLE_RE.match(t)
    if m:
        return m.group(1), int(m.group(2)), m.group(3) or "", re.sub(r"^[\s\-–:.]+|[\s\-–:.]+$", "", m.group(4))
    return "Extra", 0, "", t.strip()


def parse_duration(s):
    s = (s or "").strip()
    if re.fullmatch(r"\d+", s):
        return int(s)
    acc = 0
    for part in s.split(":"):
        acc = acc * 60 + float(part or 0)
    return int(acc)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "gapless-shuffle-refresh/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main(out_path):
    rows, seen = [], set()
    for url in FEEDS:
        root = ET.fromstring(fetch(url))
        for it in root.iter("item"):
            enc = it.find("enclosure")
            u = enc.get("url") if enc is not None else None
            if not u or u in seen:
                continue
            seen.add(u)
            title = (it.findtext("title") or "").strip()
            s, n, sfx, t = parse_title(title)
            d = parsedate_to_datetime(it.findtext("pubDate")).date().isoformat()
            dur = parse_duration(it.findtext(ITUNES + "duration"))
            rows.append([s, n, sfx, t, d, u[len(PFX):] if u.startswith(PFX) else u, dur])
    rows.sort(key=lambda r: (ORDER[r[0]], r[1], r[4]))
    new = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    try:
        old = open(out_path, encoding="utf-8").read()
    except FileNotFoundError:
        old = ""
    old_rows = json.loads(old) if old else []
    old_keys = {(r[0], r[1], r[2]) for r in old_rows}
    added = [r for r in rows if (r[0], r[1], r[2]) not in old_keys]
    removed = [r for r in old_rows if (r[0], r[1], r[2]) not in {(r[0], r[1], r[2]) for r in rows}]
    print(f"{len(rows)} episodes in feeds; {len(old_rows)} previously; {len(added)} new, {len(removed)} gone")
    for r in added:
        print(f"  + {r[0]} {r[1]}{r[2]} {r[3]} ({r[4]})")
    for r in removed:
        print(f"  - {r[0]} {r[1]}{r[2]} {r[3]} ({r[4]})")
    if len(rows) < 700:
        print("Refusing to write: fewer than 700 episodes parsed, feed looks truncated.")
        return
    if new != old:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(new)
        print("episodes.json updated")
    else:
        print("episodes.json unchanged")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "episodes.json")
