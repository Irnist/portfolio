"""Static site build.

    python _src/build.py        -> rebuilds dist/  (never edit dist/ by hand)

Page bodies: _src/pages/*.html. Shared chrome: _src/partials/. Business data,
page list and helpers: _src/site_config.py. Source images: assets/img/.

Template syntax (pages and partials):
    {{KEY}}                     BIZ value, plus derived PHONE_HREF, EMAIL_HTML, YEAR
    {{PAGE.key}}                current page's field (title, desc, file, body_class, ...)
    {{> name}}                  include _src/partials/name.html
    {{i:name}} {{i:name|cls}}   inline SVG from _src/icons/name.svg
    {{fn:name}} {{fn:name|arg}} helper output (built-ins below, or site_config.HELPERS)
"""
import html
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC, DIST = ROOT / "_src", ROOT / "dist"
sys.path.insert(0, str(SRC))
import site_config as C  # noqa: E402

try:
    from PIL import Image
except ImportError:  # dimensions are a nicety; the build still works without Pillow
    Image = None

TOKEN = re.compile(r"\{\{\s*(.+?)\s*\}\}")
warnings = []
unresolved = {}  # token -> pages


def warn(msg):
    if msg not in warnings:
        warnings.append(msg)


# ---------------------------------------------------------------- business data
def biz_values():
    v = {k: str(val) for k, val in C.BIZ.items()}
    phone = v.get("PHONE", "")
    digits = re.sub(r"[^\d+]", "", phone)
    v["PHONE_HREF"] = f"tel:{digits}" if digits else ""
    email = v.get("EMAIL", "")
    # <wbr> before @ so long addresses break cleanly on phones
    v["EMAIL_HTML"] = html.escape(email).replace("@", "<wbr>@") if email else ""
    v["EMAIL_HREF"] = f"mailto:{email}" if email else ""
    v["YEAR"] = str(date.today().year)
    v["CTA_LABEL"], v["CTA_HREF"] = C.PRIMARY_CTA
    return v


BIZ = biz_values()


# ---------------------------------------------------------------- built-in helpers
def h_nav(page, arg=None):
    items = []
    for p in C.PAGES:
        if not p.get("nav"):
            continue
        current = ' aria-current="page"' if p["file"] == page["file"] else ""
        items.append(f'<li><a href="{p["file"]}"{current}>{html.escape(p["nav"])}</a></li>')
    return "<ul>" + "".join(items) + "</ul>"


def h_cta(page, arg=None):
    cls = f"btn btn-primary {arg}" if arg else "btn btn-primary"
    label, href = C.PRIMARY_CTA
    return f'<a class="{cls}" href="{href}">{html.escape(label)}</a>'


def h_hours(page, arg=None):
    if not C.HOURS:
        warn("HOURS is empty (footer/contact show nothing)")
        return ""
    rows = "".join(f"<dt>{html.escape(d)}</dt><dd>{html.escape(t)}</dd>" for d, t in C.HOURS)
    return f'<dl class="hours">{rows}</dl>'


def h_service_options(page, arg=None):
    if not C.SERVICES:
        warn("SERVICES is empty (contact form service select has no options)")
    return "".join(f'<option value="{html.escape(s)}">{html.escape(s)}</option>' for s in C.SERVICES)


def h_form_attrs(page, arg=None):
    if not C.FORM_ENDPOINT:
        warn("FORM_ENDPOINT is empty: forms run in demo mode (list at handoff)")
        return 'method="post" data-endpoint=""'
    ep = html.escape(C.FORM_ENDPOINT)
    return f'action="{ep}" method="post" data-endpoint="{ep}"'


def h_canonical(page, arg=None):
    if not C.DOMAIN:
        return ""
    path = "" if page["file"] == "index.html" else page["file"]
    return f'<link rel="canonical" href="{C.DOMAIN.rstrip("/")}/{path}">'


GSAP_VENDOR = ROOT / "tools" / "vendor" / "gsap"


def gsap_plugins():
    """site_config.GSAP, minus names that aren't vendored (warned). [] = GSAP off."""
    plugins = []
    for name in getattr(C, "GSAP", []):
        if (GSAP_VENDOR / f"{name}.min.js").exists():
            plugins.append(name)
        else:
            warn(f"GSAP plugin '{name}' isn't in tools/vendor/gsap/ (left out); copy it from the gsap npm package's dist/")
    return plugins


def h_gsap(page, arg=None):
    """Script tags for GSAP core, the plugins in site_config.GSAP, then motion.js. Deferred scripts run in
    document order, so this goes after main.js in layout.html. Empty when GSAP is off."""
    if not getattr(C, "GSAP", []):
        return ""
    srcs = [f"assets/js/vendor/gsap/{n}.min.js" for n in ["gsap", *gsap_plugins()]] + ["assets/js/motion.js"]
    return "\n".join(f'<script src="{s}" defer></script>' for s in srcs)


HELPERS = {
    "nav": h_nav, "cta": h_cta, "hours": h_hours, "service_options": h_service_options,
    "form_attrs": h_form_attrs, "canonical": h_canonical, "gsap": h_gsap,
    **C.HELPERS,
}


# ---------------------------------------------------------------- rendering
def icon(name, cls=""):
    p = SRC / "icons" / f"{name}.svg"
    if not p.exists():
        warn(f"missing icon: _src/icons/{name}.svg")
        return ""
    attrs = f' class="icon{" " + cls if cls else ""}" aria-hidden="true" focusable="false"'
    return re.sub(r"<svg\b", "<svg" + attrs, p.read_text(encoding="utf-8").strip(), count=1)


def render(text, page, depth=0):
    if depth > 8:
        warn("include/helper nesting deeper than 8: check for a loop")
        return text

    def sub(m):
        t = m.group(1)
        if t.startswith(">"):
            p = SRC / "partials" / f"{t[1:].strip()}.html"
            if not p.exists():
                warn(f"missing partial: {p.relative_to(ROOT)}")
                return m.group(0)
            return render(p.read_text(encoding="utf-8"), page, depth + 1)
        if t.startswith("i:"):
            name, _, cls = t[2:].partition("|")
            return icon(name.strip(), cls.strip())
        if t.startswith("fn:"):
            name, _, arg = t[3:].partition("|")
            if "{{" in arg:  # the token regex stops at the first }}, so a nested token truncates the call
                warn(f"token nested inside helper args (tokens don't nest; let the helper read BIZ): {{{{{t}}}}}")
                return m.group(0)
            fn = HELPERS.get(name.strip())
            if not fn:
                warn(f"unknown helper: {name.strip()}")
                return m.group(0)
            return render(fn(page, arg.strip() or None), page, depth + 1)
        if t.startswith("PAGE."):
            return str(page.get(t[5:], ""))
        if t in BIZ:
            if BIZ[t] == "":
                warn(f"BIZ value empty, left as placeholder: {{{{{t}}}}}")
                return m.group(0)
            return BIZ[t]
        return m.group(0)  # reported as unresolved below

    return TOKEN.sub(sub, text)


IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)


def add_dims(markup, page_file):
    """Add width/height to <img> tags that lack them (prevents layout shift)."""
    def fix(m):
        tag = m.group(0)
        src = re.search(r'\ssrc="([^"]+)"', tag)
        if not src or src.group(1).startswith(("http:", "https:", "data:")):
            return tag
        path = ROOT / src.group(1).split("?")[0]
        if not path.exists():
            warn(f"missing image in {page_file}: {src.group(1)}")
            return tag
        if Image is None or " width=" in tag:
            return tag
        try:
            with Image.open(path) as im:
                w, h = im.size
        except Exception:
            return tag
        return tag[:-1].rstrip("/").rstrip() + f' width="{w}" height="{h}">'

    return IMG_TAG.sub(fix, markup)


def build_page(page, layout):
    page = dict(page)
    name = C.BIZ.get("NAME") or "{{NAME}}"
    title = page.get("title") or ""
    page["full_title"] = title if page["file"] == "index.html" and title else (
        f"{title} | {name}" if title else name)
    for key in ("title", "desc"):
        if not page.get(key) and page["file"] != "404.html":
            warn(f"{page['file']}: empty meta {key}")
    src = SRC / "pages" / page["src"]
    if not src.exists():
        warn(f"missing page source: {src.relative_to(ROOT)}")
        return None
    page["body"] = render(src.read_text(encoding="utf-8"), page)
    out = add_dims(render(layout, page), page["file"])
    for t in dict.fromkeys(TOKEN.findall(out)):
        unresolved.setdefault(t, []).append(page["file"])
    return out


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    keep = shutil.ignore_patterns(".keep")
    shutil.copytree(ROOT / "assets", DIST / "assets", ignore=keep)
    public = ROOT / "public"
    if public.exists():
        shutil.copytree(public, DIST, dirs_exist_ok=True, ignore=keep)
    if (ROOT / "_headers").exists():
        shutil.copy2(ROOT / "_headers", DIST / "_headers")

    layout = (SRC / "partials" / "layout.html").read_text(encoding="utf-8")
    # GSAP (optional): ship core + the chosen plugins + motion.js only when site_config.GSAP lists plugins
    if getattr(C, "GSAP", []):
        vendor = DIST / "assets" / "js" / "vendor" / "gsap"
        vendor.mkdir(parents=True, exist_ok=True)
        for name in ["gsap", *gsap_plugins()]:
            if (GSAP_VENDOR / f"{name}.min.js").exists():
                shutil.copy2(GSAP_VENDOR / f"{name}.min.js", vendor)
            else:
                warn("tools/vendor/gsap/gsap.min.js missing: copy tools/vendor/gsap/ from the pipeline template")
        if not (ROOT / "assets" / "js" / "motion.js").exists():
            warn("GSAP is on but assets/js/motion.js is missing: copy it from the pipeline template")
        if "fn:gsap" not in layout:
            warn("GSAP is on but layout.html has no {{fn:gsap}} after main.js: no GSAP scripts load")
    else:
        (DIST / "assets" / "js" / "motion.js").unlink(missing_ok=True)
    built = []
    for page in C.PAGES:
        out = build_page(page, layout)
        if out is not None:
            (DIST / page["file"]).write_text(out, encoding="utf-8")
            built.append(page["file"])

    if C.DOMAIN:
        base = C.DOMAIN.rstrip("/")
        urls = "".join(
            f"<url><loc>{base}/{'' if f == 'index.html' else f}</loc></url>"
            for f in built if f != "404.html")
        (DIST / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
            encoding="utf-8")

    for t, pages in unresolved.items():
        if BIZ.get(t) != "":  # empty BIZ values were already reported once
            warn(f"unresolved {{{{{t}}}}} in {', '.join(pages)}")
    print(f"built {len(built)} pages -> dist/")
    for w in warnings:
        print("  !", w)


if __name__ == "__main__":
    main()
