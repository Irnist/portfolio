"""Download stock photos by known ID into assets/img/stock/ and record credits.

    python tools/fetch_stock.py SOURCE:name [SOURCE:name ...] [--w 2400]

SOURCE is one of:
    photo-1503376780353-7e6692767b70      Unsplash image ID (images.unsplash.com/<id>)
    pexels:3807277                        Pexels photo ID
    https://images.unsplash.com/...       any direct image URL

Unsplash search sits behind a bot check: never try to get around it. Find IDs some other way.
Open every downloaded file and check it before use (locale, plates, logos, text behind headlines).
"""
import csv
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "assets" / "img" / "stock"
CREDITS = DEST / "CREDITS.csv"


def resolve(source, width):
    if source.startswith("pexels:"):
        pid = source.split(":", 1)[1]
        return f"https://images.pexels.com/photos/{pid}/pexels-photo-{pid}.jpeg?auto=compress&cs=tinysrgb&w={width}", "Pexels"
    if source.startswith("photo-"):
        return f"https://images.unsplash.com/{source}?w={width}&q=72&fm=jpg&fit=max", "Unsplash"
    if source.startswith("http"):
        return source, "Unsplash" if "unsplash" in source else "web"
    sys.exit(f"don't know how to fetch {source!r}")


def main():
    args = sys.argv[1:]
    width = 1600
    if "--w" in args:
        i = args.index("--w")
        width = int(args[i + 1])
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    DEST.mkdir(parents=True, exist_ok=True)
    known = {}
    if CREDITS.exists():
        with CREDITS.open(newline="", encoding="utf-8") as f:
            known = {row["source"]: row["file"] for row in csv.DictReader(f)}

    rows = []
    for arg in args:
        # split on the LAST colon that isn't part of the URL scheme or the pexels: prefix
        m = re.match(r"^(.*):([\w.-]+)$", arg)
        source, name = (m.group(1), m.group(2)) if m and not m.group(1).endswith(("http", "https", "pexels")) else (arg, None)
        if source in known:
            print(f"  already have {source} as {known[source]}: reuse is a repeat; pick a different photo")
            continue
        url, site = resolve(source, width)
        name = re.sub(r"[^\w-]+", "-", (name or source.rsplit("/", 1)[-1].split("?")[0]).lower()).strip("-")
        out = DEST / f"{name}.jpg"
        if out.exists():
            sys.exit(f"{out.relative_to(ROOT)} exists; choose another name")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (site build; stock download)"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                if "image" not in r.headers.get("Content-Type", ""):
                    print(f"  ! {source}: not an image response (blocked or wrong ID), skipped")
                    continue
                out.write_bytes(r.read())
        except Exception as e:  # noqa: BLE001
            print(f"  ! {source}: {e}")
            continue
        rows.append({"file": out.relative_to(ROOT).as_posix(), "source": source, "site": site,
                     "url": url, "date": date.today().isoformat()})
        print(f"  saved {out.relative_to(ROOT).as_posix()} ({out.stat().st_size // 1024} KB)")

    if rows:
        new = not CREDITS.exists()
        with CREDITS.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["file", "source", "site", "url", "date"])
            if new:
                w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
