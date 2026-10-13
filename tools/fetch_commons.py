"""Download Wikimedia Commons files by title into assets/img/stock/ and record credits.

    python tools/fetch_commons.py "File title.jpg:name" ["Other.jpg:name2" ...] [--w 2000]

Records author and licence in assets/img/stock/CREDITS.csv (same columns as fetch_stock.py,
plus author/license), because CC BY / BY-SA photos need visible attribution.
"""
import csv
import time
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "assets" / "img" / "stock"
CREDITS = DEST / "CREDITS.csv"
UA = {"User-Agent": "site-builder/1.0 (portfolio sample build)"}
FIELDS = ["file", "source", "site", "url", "date", "author", "license"]


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    width = 2000
    if "--w" in args:
        i = args.index("--w")
        width = int(args[i + 1])
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    DEST.mkdir(parents=True, exist_ok=True)
    rows = []
    for n, arg in enumerate(args):
        if n:
            time.sleep(4)  # Commons rate-limits bursts (429)
        title, _, name = arg.rpartition(":")
        q = urllib.parse.urlencode({"action": "query", "titles": "File:" + title, "prop": "imageinfo",
                                    "iiprop": "url|extmetadata", "iiurlwidth": width, "format": "json"})
        data = json.load(urllib.request.urlopen(urllib.request.Request(
            "https://commons.wikimedia.org/w/api.php?" + q, headers=UA), timeout=30))
        page = next(iter(data["query"]["pages"].values()))
        if "imageinfo" not in page:
            print(f"  ! not found: {title}")
            continue
        ii = page["imageinfo"][0]
        md = ii.get("extmetadata", {})
        out = DEST / f"{name}.jpg"
        if out.exists():
            print(f"  skip {out.name}: exists")
            continue
        url = ii.get("thumburl") or ii["url"]
        out.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        rows.append({"file": out.relative_to(ROOT).as_posix(), "source": "commons:" + title,
                     "site": "Wikimedia Commons", "url": ii["descriptionurl"], "date": date.today().isoformat(),
                     "author": strip_tags(md.get("Artist", {}).get("value")),
                     "license": md.get("LicenseShortName", {}).get("value", "")})
        print(f"  saved {out.relative_to(ROOT).as_posix()} ({out.stat().st_size // 1024} KB) "
              f"{rows[-1]['license']} by {rows[-1]['author'][:40]}")

    if rows:
        existing = []
        if CREDITS.exists():
            with CREDITS.open(newline="", encoding="utf-8") as f:
                existing = list(csv.DictReader(f))
        with CREDITS.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows([{k: r.get(k, "") for k in FIELDS} for r in existing + rows])


if __name__ == "__main__":
    main()
