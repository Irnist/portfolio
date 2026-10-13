"""Make a transparent cut-out of client-assets/Headshot.jpg (a cut-out on white) for the dark theme.

    python tools/cutout_headshot.py

Background = near-white pixels connected to the image border (flood fill), so white inside the subject
(collar stripes, eye highlights) stays. The source's own edge is 2-12px of light, white-mixed pixels (it was
cut out once already), which reads as a white outline on charcoal (Ernest flagged it, 2026-10-08). So:
  1. the edge is pulled in by ERODE px, which drops the contaminated rim and stray light wisps of hair;
  2. any edge pixel lighter than the clean interior around it is recoloured from the nearest interior
     colours (normalised blur of the interior), so no light value survives along the edge, while darker
     texture (hair strands, folds) is kept;
  3. the alpha edge is feathered by FEATHER px so it stays soft rather than cut.
Output: client-assets/headshot-cutout.png (full size).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "client-assets" / "Headshot.jpg"
OUT = ROOT / "client-assets" / "headshot-cutout.png"
ERODE = 6      # px pulled in from the flood-fill edge (the measured rim is 2-6px, up to ~12px where blurry)
CORE = 12      # px in from the edge where colours count as clean
FEATHER = 1.6  # px of soft alpha edge
TOL = 8        # an edge pixel this much lighter (0-255 mean) than the interior around it counts as white-mixed
PAD = 40       # edge-replicated padding, so the subject cut by the bottom of the photo isn't eroded there


def blur(a, r):
    """Approximate Gaussian blur (three box passes) of a float 2-D array, edges replicated."""
    r = max(1, int(round(r)))
    for axis in (0, 1):
        for _ in range(3):
            p = np.pad(a, [((r + 1, r) if ax == axis else (0, 0)) for ax in (0, 1)], mode="edge")
            c = np.cumsum(p, axis=axis)
            hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
            lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)
            a = (hi - lo) / (2 * r + 1)
    return a


def erode(mask, r):
    """Binary erosion by r px (PIL MinFilter takes an odd window size)."""
    img = Image.fromarray(mask.astype(np.uint8) * 255, "L").filter(ImageFilter.MinFilter(2 * r + 1))
    return np.asarray(img) > 127


def main():
    src = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)
    rgb = np.pad(src, ((PAD, PAD), (PAD, PAD), (0, 0)), mode="edge")
    whiteness = rgb.min(axis=2)  # 255 = pure white
    # Flood-fill the near-white region from every near-white border pixel.
    # .copy(): an image made by fromarray shares the read-only buffer, and floodfill silently does nothing.
    mask = Image.fromarray(((whiteness > 232) * 255).astype(np.uint8), "L").copy()
    h, w = whiteness.shape
    seeds = [(x, 0) for x in range(0, w, 8)] + [(x, h - 1) for x in range(0, w, 8)] + \
            [(0, y) for y in range(0, h, 8)] + [(w - 1, y) for y in range(0, h, 8)]
    for s in seeds:
        if mask.getpixel(s) == 255:
            ImageDraw.floodfill(mask, s, 128)
    fg = np.asarray(mask) != 128

    # 1-3: pulled-in, feathered alpha; colours outside the clean core rebuilt from the core.
    alpha = np.clip(blur(erode(fg, ERODE).astype(np.float32), FEATHER), 0, 1)
    core = erode(fg, CORE).astype(np.float32)
    col = rgb.copy()
    todo = core < 1
    for r in (4, 10, 24, 60):  # widen until every edge pixel has interior colour to borrow
        wgt = blur(core, r)
        fill = np.dstack([blur(rgb[..., i] * core, r) for i in range(3)]) / np.maximum(wgt, 1e-6)[..., None]
        ok = todo & (wgt > 0.02)
        # Keep the real texture (hair strands, shirt folds) where it isn't lighter than its surroundings;
        # only light, white-mixed pixels take the borrowed colour.
        lighter = rgb.mean(axis=2) > fill.mean(axis=2) + TOL
        col[ok & lighter] = fill[ok & lighter]
        todo &= ~ok
        if not todo[alpha > 0].any():
            break

    out = np.dstack([np.clip(col, 0, 255), alpha * 255]).astype(np.uint8)[PAD:-PAD, PAD:-PAD]
    img = Image.fromarray(out, "RGBA")
    bbox = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    img = img.crop(bbox)
    OUT.parent.mkdir(exist_ok=True)
    img.save(OUT)
    print(f"{OUT.relative_to(ROOT).as_posix()}  {img.width}x{img.height}  bbox {bbox}")


if __name__ == "__main__":
    main()
