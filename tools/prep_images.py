"""Turn the raw portfolio material into the webp files the page uses.

    python tools/prep_images.py

Sources (read-only): client-assets/headshot-cutout.png (from client-assets/Headshot.jpg via cutout_headshot.py), ../Published Live Websites/*/SS 1.png,
../Graphic Designs (Travel Agency)/*.jpg and client-assets/shots/*.png (from capture_work.mjs).
Output: assets/img/{me,work,posters}/.
"""
import sys
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT.parent  # the workspace folder ("Claude Workspace")
IMG = ROOT / "assets" / "img"

# Live client sites: published screenshots are 2560 wide (2x of 1280).
LIVE = {
    "aurora-plumbing": "auroraplumbing",
    "children-matter": "childrenmattertx",
    "macon-supply": "maconsupply",
    "parker-auto": "parkerautoaz",
}
CONCEPT = ["gadget-zone", "ironcity", "trevor-travis", "macz", "ironwood", "weknz"]
# A redesigned site gets a new file name, since /assets/img/* is cached for a week (L-037). Keep these in step
# with the `img` key in _src/site_config.py CONCEPT_WORK.
IMG_NAME = {"macz": "macz-v2"}  # 2026-10-10: the dark redesign replaced the light "sunrise" design
# Curated: finished pieces, no third-party brand logos (airline/theme-park marks skipped, L-028).
POSTERS = {
    "korea-winter": "Korea Winter Solasta.jpg",
    "malaysia": "Malaysia.jpg",
    "bangkok": "Bangkok.jpg",
    "holy-land": "PILGRIMS JOURNEY HOLYLAND.jpg",
    "puerto-princesa": "puerto edit.jpg",
    "korea-autumn": "Autumn.jpg",
}
# Unsplash stock (downloaded by photo ID into client-assets/stock/), one slot each:
# slug -> (photo ID, crop aspect w/h, horizontal centre 0-1)
STOCK = {
    "process-sketch": ("photo-1581291518633-83b4ebd1d83e", 4 / 5, 0.52),  # wireframes on paper: How a project works
    "contact-notes": ("photo-1517842645767-c639042777db", 1, 0.5),        # notebook and pen: contact band
}
SCROLL_W, SCROLL_MAX_H = 960, 2400  # page "scroll" strips: 960 wide, at most 2.5:1


def save(im, path, w=None, q=80, alpha=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    im = im.convert("RGBA" if alpha else "RGB")
    if w and im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    im.save(path, "WEBP", quality=q, method=6)
    print(f"{path.relative_to(ROOT).as_posix()}  {im.width}x{im.height}  {path.stat().st_size // 1024} KB")


def strip(im):
    """Full-width top slice of a page screenshot, scaled to SCROLL_W."""
    h = min(im.height, round(SCROLL_MAX_H * im.width / SCROLL_W))
    return im.crop((0, 0, im.width, h))


def children_matter(original):
    """The supplied screenshot has a chat popup baked in and unrevealed sections below the hero; a fresh
    capture (capture_work.mjs live) renders those, but its hero video is blocked in headless Chrome.
    So: the supplied shot's hero (rows 0-777) + the fresh capture from its hero's end (row 1554).
    Both rows are the page's plain #f7f7f7 background, so the seam is invisible."""
    fresh = Image.open(ROOT / "client-assets" / "shots" / "children-matter-live.png").convert("RGB")
    top = original.convert("RGB").crop((0, 0, original.width, 777))
    rest = fresh.crop((0, 1554, fresh.width, fresh.height))
    out = Image.new("RGB", (original.width, top.height + rest.height))
    out.paste(top, (0, 0))
    out.paste(rest, (0, top.height))
    return out


def crop_to(im, aspect, cx):
    """Largest crop of the given aspect (w/h), centred horizontally at cx (fraction of width)."""
    w, h = im.size
    if w / h > aspect:
        cw = round(h * aspect)
        left = min(max(0, round(w * cx - cw / 2)), w - cw)
        return im.crop((left, 0, left + cw, h))
    ch = round(w / aspect)
    return im.crop((0, (h - ch) // 2, w, (h - ch) // 2 + ch))


def concept_shots(slug, shots):
    name = IMG_NAME.get(slug, slug)
    save(strip(Image.open(shots / f"{slug}-desktop.png")), IMG / "work" / f"{name}.webp", w=SCROLL_W, q=72)
    save(Image.open(shots / f"{slug}-phone.png"), IMG / "work" / f"{name}-phone.webp", w=360, q=78)


def main():
    # `python tools/prep_images.py gadget-zone ...`: only those concept slugs, so the other webp files
    # stay byte-identical (a long-cached file must not change under its URL, L-037).
    only = sys.argv[1:]
    if only:
        shots = ROOT / "client-assets" / "shots"
        for slug in only:
            if slug not in CONCEPT:
                sys.exit(f"unknown concept slug: {slug}")
            concept_shots(slug, shots)
        return

    # Transparent cut-out (tools/cutout_headshot.py) so the portrait stands on the charcoal page.
    head = Image.open(ROOT / "client-assets" / "headshot-cutout.png")
    save(head, IMG / "me" / "ernest-mar-banigon-v2.webp", w=880, q=82, alpha=True)

    for slug, folder in LIVE.items():
        im = Image.open(SRC / "Published Live Websites" / folder / "SS 1.png")
        if slug == "children-matter":
            im = children_matter(im)
        save(strip(im), IMG / "work" / f"{slug}.webp", w=SCROLL_W, q=72)
    for slug in CONCEPT:
        concept_shots(slug, ROOT / "client-assets" / "shots")

    for slug, (pid, aspect, cx) in STOCK.items():
        im = crop_to(Image.open(ROOT / "client-assets" / "stock" / f"{pid}.jpg"), aspect, cx)
        save(im, IMG / "stock" / f"{slug}.webp", w=900, q=76)

    for slug, name in POSTERS.items():
        im = Image.open(SRC / "Graphic Designs (Travel Agency)" / name)
        save(im, IMG / "posters" / f"{slug}.webp", w=560, q=78)
        save(im, IMG / "posters" / f"{slug}-large.webp", w=1400, q=80)


if __name__ == "__main__":
    main()
