"""Optimise client photos for the web.

    python tools/optimize_images.py            client-assets/ -> assets/img/client/
    python tools/optimize_images.py DIR ...    optimise other folders in place (e.g. assets/img/stock)

EXIF-rotates, caps the long edge at 2000px, strips metadata, saves JPEG q80
(PNG kept when it has transparency, e.g. cut-outs and logos). Existing outputs are skipped.
"""
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff", ".bmp"}
MAX = 2000


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "image"


def optimise(src, dest_dir, in_place=False):
    try:
        im = ImageOps.exif_transpose(Image.open(src))
    except Exception as e:  # noqa: BLE001  (e.g. HEIC without a plugin)
        print(f"  ! {src.name}: {e}")
        return
    alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    ext = ".png" if alpha else ".jpg"
    out = src.with_suffix(ext) if in_place else dest_dir / f"{slug(src.stem)}{ext}"
    if out.exists() and not in_place:
        return
    im.thumbnail((MAX, MAX), Image.LANCZOS)
    if alpha:
        im.save(out, optimize=True)
    else:
        im.convert("RGB").save(out, quality=80, optimize=True, progressive=True)
    if in_place and out != src:
        src.unlink()
    print(f"  {src.name} -> {out.relative_to(ROOT).as_posix()} {im.size[0]}x{im.size[1]} ({out.stat().st_size // 1024} KB)")


def main():
    if len(sys.argv) > 1:
        for d in sys.argv[1:]:
            for f in sorted(Path(d).resolve().glob("*")):
                if f.suffix.lower() in EXTS and f.stat().st_size > 350_000:
                    optimise(f, f.parent, in_place=True)
        return
    src_dir, dest = ROOT / "client-assets", ROOT / "assets" / "img" / "client"
    dest.mkdir(parents=True, exist_ok=True)
    files = [f for f in sorted(src_dir.rglob("*")) if f.suffix.lower() in EXTS]
    if not files:
        print("no images in client-assets/")
    for f in files:
        optimise(f, dest)


if __name__ == "__main__":
    main()
