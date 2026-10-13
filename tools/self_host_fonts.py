"""Self-host Google Fonts: removes the two render-blocking round trips (fonts.googleapis.com CSS, then
fonts.gstatic.com files) that cost ~1.7s of mobile LCP on Macz.

    python tools/self_host_fonts.py "<Google Fonts css2 URL>" --preload "Jost:400" [--preload ...] [--subset latin]

Downloads the WOFF2 files for one subset (default latin) to assets/fonts/ (named by content hash, so a
changed file gets a new URL) and writes _src/partials/fonts.html: <link rel="preload"> for the --preload
faces plus an inline <style> of @font-face rules with font-display: swap. Use it in site_config.py:

    FONTS = (Path(__file__).parent / "partials" / "fonts.html").read_text(encoding="utf-8")

Preload only the body text face (one, maybe two files); preloading every weight slows the first paint.
"""
import hashlib
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
PARTIAL = ROOT / "_src" / "partials" / "fonts.html"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/140.0 Safari/537.36")  # Google serves WOFF2 only to browsers it recognises


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
        return r.read()


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    if not args or not args[0].startswith("https://fonts.googleapis.com/"):
        sys.exit(__doc__)
    url, preload, subset = args[0], set(), "latin"
    for flag, value in zip(args[1::2], args[2::2]):
        if flag == "--preload":
            preload.add(value.lower().replace(" ", ""))
        elif flag == "--subset":
            subset = value
        else:
            sys.exit(f"unknown option {flag}")
    css = fetch(url).decode("utf-8")
    # Blocks look like: /* latin */\n@font-face { font-family: 'Jost'; font-style: normal; font-weight: 400 600; ... }
    blocks = re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{[^}]*\})", css)
    if not blocks:
        sys.exit("no @font-face blocks with subset comments: is this a css2 URL?")
    FONTS.mkdir(parents=True, exist_ok=True)
    saved, faces, links = {}, [], []
    for sub, block in blocks:
        if sub != subset:
            continue
        family = re.search(r"font-family:\s*'([^']+)'", block).group(1)
        style = re.search(r"font-style:\s*(\w+)", block).group(1)
        weight = re.search(r"font-weight:\s*([\d ]+)", block).group(1).strip()
        src = re.search(r"url\((https://[^)]+\.woff2)\)", block).group(1)
        if src not in saved:  # variable fonts reuse one file across weights
            data = fetch(src)
            name = f"{re.sub(r'[^a-z0-9]+', '-', family.lower())}-{style}-{weight.replace(' ', '-')}-{hashlib.sha1(data).hexdigest()[:8]}.woff2"
            (FONTS / name).write_bytes(data)
            saved[src] = name
            print(f"  {family} {style} {weight}: assets/fonts/{name} ({len(data) // 1024} KB)")
        local = f"assets/fonts/{saved[src]}"
        block = block.replace(src, local)
        if "font-display" not in block:
            block = block.replace("{", "{\n  font-display: swap;", 1)
        faces.append(re.sub(r"\s+", " ", block))
        # Family:weight matches a static face, or any weight inside a variable face's range ("Cormorant:600"
        # for weight 500 700; it once had to be the range's first weight)
        fam, ws = family.lower().replace(" ", ""), weight.split()
        lo, hi = (int(ws[0]), int(ws[-1])) if all(w.isdigit() for w in ws) else (None, None)
        hits = {p for p in preload if p.split(":")[0] == fam and (
            p.split(":")[-1] in (ws[0], weight.replace(" ", "-"))
            or (lo is not None and p.split(":")[-1].isdigit() and lo <= int(p.split(":")[-1]) <= hi))}
        if hits and local not in "".join(links):
            links.append(f'<link rel="preload" href="{local}" as="font" type="font/woff2" crossorigin>')
        preload -= hits
    if not faces:
        sys.exit(f"no '{subset}' faces in the CSS")
    if preload:
        print(f"! --preload not matched (use Family:weight, e.g. Jost:400): {sorted(preload)}")
    PARTIAL.write_text("".join(links) + "<style>" + "".join(faces) + "</style>\n", encoding="utf-8")
    print(f"wrote {PARTIAL.relative_to(ROOT)} ({len(faces)} faces, {len(links)} preloaded). "
          "Point FONTS in site_config.py at it and drop the fonts.googleapis.com links.")


if __name__ == "__main__":
    main()
