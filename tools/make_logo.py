"""Build Ernest's logo mark: a browser window (web design) framing his EB monogram (Cormorant, outlined to paths).

    python tools/make_logo.py

Writes
  _src/icons/logo-mark.svg  header mark, inlined by the build; frame = currentColor, letters = .logo__ink
  public/favicon.svg        the same mark on a charcoal plate, colours fixed
Letters are outlined from client-assets/fonts/Cormorant-var.ttf (Google Fonts, OFL) at weight 700, so neither
file depends on a web font. Option B ("browser window") from `client-assets/Logo options.png`, picked by
Ernest 2026-10-08, replacing the first pick (lens around EMB).
"""
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "client-assets" / "fonts" / "Cormorant-var.ttf"
AMBER, CREAM, PLATE = "#F2963A", "#EFE7DA", "#1C1C1D"
TEXT, WEIGHT, TRACK = "EB", 700, -0.02       # boldest weight: lighter strokes vanish next to the frame at 48px
# Window in a 64-unit box: frame, title bar rule, three dots; the letters sit in the pane below the bar.
X, Y, W, H, RX, STROKE = 5, 7, 54, 50, 7, 3.5
BAR_Y = 19
DOTS_X, DOT_Y, DOT_R = (12, 17, 22), 13, 1.9
CX, CY = X + W / 2, (BAR_Y + Y + H) / 2 + .5  # pane centre (optically a touch low)
MAX_W, MAX_CAP = 34, 20


def monogram():
    font = instantiateVariableFont(TTFont(FONT), {"wght": WEIGHT})
    gs, cmap = font.getGlyphSet(), font.getBestCmap()
    cap = font["OS/2"].sCapHeight
    names = [cmap[ord(c)] for c in TEXT]
    units = sum(gs[n].width for n in names) + TRACK * cap * (len(names) - 1)
    s = min(MAX_CAP / cap, MAX_W / units)
    x = CX - units * s / 2
    d = []
    for n in names:
        pen = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        gs[n].draw(TransformPen(pen, (s, 0, 0, -s, x, CY + cap * s / 2)))
        d.append(pen.getCommands())
        x += (gs[n].width + TRACK * cap) * s
    return " ".join(d), cap * s


def window(colour):
    dots = "".join(f'<circle cx="{x}" cy="{DOT_Y}" r="{DOT_R}"/>' for x in DOTS_X)
    return (f'<rect x="{X}" y="{Y}" width="{W}" height="{H}" rx="{RX}" fill="none" stroke="{colour}" stroke-width="{STROKE}"/>'
            f'<path d="M{X} {BAR_Y}H{X + W}" stroke="{colour}" stroke-width="{STROKE}"/>'
            f'<g fill="{colour}">{dots}</g>')


def main():
    d, cap_px = monogram()
    pad = STROKE / 2
    box = f"{X - pad} {Y - pad} {W + STROKE} {H + STROKE}"
    mark = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}">{window("currentColor")}'
            f'<path class="logo__ink" fill="{CREAM}" d="{d}"/></svg>\n')
    fav = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="{PLATE}"/>'
           f'{window(AMBER)}<path fill="{CREAM}" d="{d}"/></svg>\n')
    (ROOT / "_src" / "icons" / "logo-mark.svg").write_text(mark, encoding="utf-8")
    (ROOT / "public" / "favicon.svg").write_text(fav, encoding="utf-8")
    print(f"logo-mark.svg {len(mark)} B, favicon.svg {len(fav)} B, letter cap height {cap_px:.1f}/64")


if __name__ == "__main__":
    main()
