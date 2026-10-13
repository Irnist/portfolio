"""Static QA over the built site: the CLAUDE.md website rules that can be checked from markup/CSS.

    python tools/qa.py      -> qa/report.md + qa/image-allocation.md; exit 1 if any ERROR

Run after `python _src/build.py`. Layout/contrast/overflow checks live in tools/browser_qa.mjs.
"""
import re
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST, OUT = ROOT / "dist", ROOT / "qa"
sys.path.insert(0, str(ROOT / "_src"))
import site_config as C  # noqa: E402

TOKEN = re.compile(r"\{\{\s*(.+?)\s*\}\}")
PLACEHOLDER_TEXT = re.compile(r"lorem ipsum|YOUR_[A-Z_]+|FORM_ID|example\.com|\b555-01\d\d\b|\bTODO\b|\bTBD\b", re.I)
VISIBLE_JUNK = re.compile(r"\b(null|undefined|NaN)\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# Template tells seen in both IronCity ("kicker") and Weknz ("pill"): a small label over every heading,
# and rows of cards that each open with an icon.
EYEBROW = re.compile(r"eyebrow|kicker|overline|pretitle|pill|tag|label|section-?num", re.I)
CARD = re.compile(r"card|tile|feature|benefit|step|perk|usp", re.I)
FIELDS = ("input", "select", "textarea")
BRAND_ASSET = re.compile(r"logo|favicon|icon|sprite|\.svg$", re.I)  # header + footer logo is not a repeated photo


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.imgs, self.links, self.selects, self.primary, self.forms = [], [], [], [], []
        self.anchors, self.inputs = [], []  # anchors: {href, text, cls, nav}
        self.todos, self.style_urls, self.text = [], [], []
        self.h1 = self.h2 = self.eyebrow_h2 = self.icon_cards = 0
        self.marquee = False
        self.title, self.desc, self.og_image = "", None, None
        self.header_depth, self.nav_depth, self.header_tel = 0, 0, False
        self._a = self._sel = self._opt = self._form = None
        self._stack = []    # open elements: [tag, class, text, first child (tag, class) or None]
        self._last = None   # most recently closed element, cleared by any start tag
        self._skip = 0      # inside <script>/<style>
        self._in_title = False
        self.main_depth, self.main_text = 0, []  # page body only (shared header/footer excluded)
        self.data_depth = 0  # inside a data block (hours table, address, form options): repeats there are fine

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        cls = a.get("class", "")
        if tag == "main":
            self.main_depth += 1
        if tag in DATA_TAGS:
            self.data_depth += 1
        if "style" in a:
            self.style_urls += re.findall(r"url\(['\"]?([^'\")]+)", a["style"])
        if "data-todo" in a:
            self.todos.append(a["data-todo"])
        if tag == "marquee" or "marquee" in (cls + " " + a.get("id", "")).lower():
            self.marquee = True
        if tag in ("h2", "h3") and self._last:
            ltag, lcls, ltext = self._last
            if ltag in ("p", "span", "div", "small", "strong", "em") and EYEBROW.search(lcls) and len(ltext.strip()) <= 48:
                self.eyebrow_h2 += 1
        if tag == "h2":
            self.h2 += 1
        if self._stack and self._stack[-1][3] is None:
            self._stack[-1][3] = (tag, cls)
        self._last = None
        if tag not in VOID:
            self._stack.append([tag, cls, "", None])

        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "header":
            self.header_depth += 1
        elif tag == "nav":
            self.nav_depth += 1
        elif tag == "img":
            self.imgs.append(a)
        elif tag == "a":
            href = a.get("href")
            self.links.append(href)
            if self.header_depth and href and href.startswith("tel:") and len(href) > 4:
                self.header_tel = True
            self._a = {"href": href, "text": "", "cls": cls.split(), "nav": self.nav_depth > 0}
        elif tag == "h1":
            self.h1 += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta" and a.get("name") == "description":
            self.desc = a.get("content", "")
        elif tag == "meta" and a.get("property") == "og:image":
            self.og_image = a.get("content", "")
        elif tag == "form":
            self._form = dict(a, _fields=0, _next=False, _contact=False)
            self.forms.append(self._form)
        elif tag == "select":
            # filter/sort controls in a search form may default to "All" / "Newest"
            search = self._form is not None and self._form.get("role") == "search"
            self._sel = {"name": a.get("name") or a.get("id"), "options": [], "filter": search or "data-filter" in a}
        elif tag == "option" and self._sel is not None:
            self._opt = {"value": a.get("value"), "selected": "selected" in a, "text": ""}
            self._sel["options"].append(self._opt)
        if tag == "input":
            self.inputs.append(a)
        if self._form is not None:
            if tag in FIELDS and a.get("type") not in ("hidden", "submit", "button") and a.get("name") != "_gotcha":
                self._form["_fields"] += 1
            if "data-next-steps" in a:
                self._form["_next"] = True
            if tag == "textarea" or (tag == "input" and a.get("type") in ("email", "tel")):
                self._form["_contact"] = True

    def handle_endtag(self, tag):
        if tag == "main":
            self.main_depth = max(0, self.main_depth - 1)
        if tag in DATA_TAGS:
            self.data_depth = max(0, self.data_depth - 1)
        if tag not in VOID and any(e[0] == tag for e in self._stack):
            while self._stack:
                e = self._stack.pop()
                if self._stack:
                    self._stack[-1][2] += e[2]
                if e[0] == tag:
                    break
            self._last = (e[0], e[1], e[2])
            first = e[3]
            if CARD.search(e[1]) and first and (first[0] == "svg" or "icon" in first[1]):
                self.icon_cards += 1
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag == "header":
            self.header_depth -= 1
        elif tag == "nav":
            self.nav_depth -= 1
        elif tag == "form":
            self._form = None
        elif tag == "a" and self._a is not None:
            self._a["text"] = " ".join(self._a["text"].split())
            self.anchors.append(self._a)
            if "btn-primary" in self._a["cls"]:
                self.primary.append((self._a["text"], self._a["href"]))
            self._a = None
        elif tag == "title":
            self._in_title = False
        elif tag == "select" and self._sel is not None:
            self.selects.append(self._sel)
            self._sel = None
        elif tag == "option":
            self._opt = None

    def handle_data(self, data):
        if self._skip:
            return
        if self._stack:
            self._stack[-1][2] += data
        if self._in_title:
            self.title += data
        if self._a is not None:
            self._a["text"] += data
        if self._opt is not None:
            self._opt["text"] += data
        self.text.append(data)
        if self.main_depth and not self.data_depth:
            self.main_text.append(data)


SHINGLE = 8  # words; shorter runs are mostly names, places and stock phrases
DATA_TAGS = {"select", "table", "address", "dl"}  # contact/hours/spec data may repeat; prose may not


def is_data_run(phrase):
    """Hours, addresses, phone numbers and spec lines written as plain text: a quarter or more numbers."""
    ws = phrase.split()
    return sum(w[0].isdigit() for w in ws) * 4 >= len(ws)


def words(text):
    return re.findall(r"[a-z0-9±]+(?:['’][a-z]+)?", text.lower())


def repeated_wording(page_words, allowed):
    """L-009: each idea once. Runs of SHINGLE+ identical words in the <main> of two or more pages.
    Returns [(pages, phrase)], one per maximal run, in the first page's reading order."""
    seen = defaultdict(set)
    for name, ws in page_words.items():
        for i in range(len(ws) - SHINGLE + 1):
            seen[tuple(ws[i:i + SHINGLE])].add(name)
    allowed = [" ".join(words(a)) for a in list(allowed) + ["opens in a new tab"]]  # + screen-reader link text
    out, done = [], set()
    for name, ws in page_words.items():
        i = 0
        while i <= len(ws) - SHINGLE:
            where = seen[tuple(ws[i:i + SHINGLE])]
            if len(where) < 2:
                i += 1
                continue
            j = i + 1
            while j <= len(ws) - SHINGLE and seen[tuple(ws[j:j + SHINGLE])] == where:
                j += 1
            phrase = " ".join(ws[i:j + SHINGLE - 1])
            key = (frozenset(where), phrase)
            if key not in done and not is_data_run(phrase) and not any(a and (a in phrase or phrase in a) for a in allowed):
                done.add(key)
                out.append((sorted(where), phrase))
            i = j + SHINGLE - 1
    return out


def norm(src, base=""):
    """Normalise an image reference to a dist-relative path."""
    src = src.split("?")[0].split("#")[0]
    if src.startswith(("http:", "https:", "data:")):
        return src
    parts = []
    for seg in (base + src).split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            parts and parts.pop()
        else:
            parts.append(seg)
    return "/".join(parts)


def css_motion(css):
    """CSS that animates on its own: transitions, animations, @keyframes. The user's standard (2026-10-09): all
    animation runs in JavaScript, and CSS only describes states. `none` values (switching one off) are fine."""
    found = [f"@keyframes {m.group(1)}" for m in re.finditer(r"@keyframes\s+([\w-]+)", css)]
    for m in re.finditer(r"(?<![\w-])(transition|transition-property|animation|animation-name)\s*:\s*([^;}\"]+)", css):
        value = m.group(2).replace("!important", "").strip()
        if value and value != "none":
            found.append(f"{m.group(1)}: {' '.join(value.split())[:50]}")
    return found


def gsap_checks(pages, errors, warns, allow):
    """Optional GSAP motion (site_config.GSAP): self-hosted, gated on reduced motion, transform/opacity only.
    browser_qa.mjs re-checks the running tweens (properties, .reveal/data-parallax clashes, hidden hero)."""
    for path in pages:
        raw = path.read_text(encoding="utf-8")
        for src in re.findall(r"""<script[^>]+src=["'](https?://[^"']*(?:gsap|greensock)[^"']*)""", raw, re.I):
            errors.append(f"{path.name}: GSAP from a CDN ({src}): self-host it; list the plugins in site_config.GSAP")
        # SplitText puts an aria-label on its target; ARIA forbids that on <p>, <span>, <div> (L-062, Macz)
        for tag in re.findall(r"<(\w+)\b[^>]*\bdata-gsap=[\"']split[\"']", raw):
            if not re.fullmatch(r"h[1-6]|a|button|blockquote|figure|section|li", tag.lower()):
                errors.append(f"{path.name}: data-gsap=\"split\" on a <{tag}>: SplitText adds an aria-label, which is "
                              "prohibited there (axe); split a heading instead (L-062)")
    if not getattr(C, "GSAP", []):
        return
    motion = DIST / "assets" / "js" / "motion.js"
    if not motion.exists():
        errors.append("GSAP is on but dist/assets/js/motion.js is missing")
        return
    body = re.sub(r"/\*.*?\*/|//[^\n]*", "", motion.read_text(encoding="utf-8"), flags=re.S)
    if "prefers-reduced-motion" not in body:
        errors.append("motion.js: GSAP animations without a prefers-reduced-motion gate (wrap them in gsap.matchMedia())")
    if "ScrollSmoother" in body and "scrollsmoother" not in allow:
        warns.append("motion.js uses ScrollSmoother: it takes over scrolling and breaks main.js parallax; "
                     "only if the user asked for it (ALLOW_PATTERNS['scrollsmoother'])")
    code = re.sub(r"'[^'\n]*'|\"[^\"\n]*\"|`[^`]*`", "''", body)  # media queries like '(min-width: 900px)' aren't tweens
    bad = re.findall(r"(?<![\w-])(width|height|top|left|right|bottom|margin\w*|padding\w*|backgroundPosition|clipPath|filter)\s*:", code)
    if bad:
        warns.append(f"motion.js sets {', '.join(sorted(set(bad)))}: tween only transform and opacity "
                     "(x, y, xPercent, yPercent, scale, rotation, opacity/autoAlpha)")


def pipeline_tools():
    """The pipeline template's tools/, found by walking up from this project to the workspace
    (Claude Workspace/Workflow and Pipeline/website-pipeline/template/tools). None outside the workspace."""
    for parent in Path(__file__).resolve().parents:
        tools = parent / "Workflow and Pipeline" / "website-pipeline" / "template" / "tools"
        if tools.is_dir():
            return tools
    return None


def stale_tools(warns):
    """A project keeps its own copy of tools/. When the template's copy is newer and different, the project is
    missing checks added since: this site ran without Lighthouse or the CSS-motion check for days (L-052)."""
    here = Path(__file__).resolve().parent
    pipeline = pipeline_tools()
    if pipeline is None or here == pipeline.resolve():
        return
    stale = [f for f in ("qa.py", "browser_qa.mjs", "lighthouse.mjs", "deploy.py", "self_host_fonts.py")
             if (pipeline / f).exists() and (not (here / f).exists()
                 or ((pipeline / f).stat().st_mtime > (here / f).stat().st_mtime
                     and (pipeline / f).read_bytes() != (here / f).read_bytes()))]
    if stale:
        warns.append(f"tools/ older than the pipeline template: {', '.join(stale)}. Sync them (copy, or port the new "
                     "checks into a customised copy) before trusting this report (L-052)")


def tight_leading(css):
    """Rules whose unitless line-height (or `font: size/lh`) is below 1. On this site a .98 heading put the "j" of
    "project" on top of the "?" below it once the line wrapped (L-051)."""
    found = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        for v in re.findall(r"line-height\s*:\s*([\d.]+)\s*(?=[;}!]|$)", m.group(2)) + \
                re.findall(r"(?<![\w-])font\s*:[^;]*?/\s*([\d.]+)\s+", m.group(2)):
            if float(v) < 1:
                found.append((" ".join(m.group(1).split())[-60:], v))
    return found


def buried_backdrop(css):
    """A fixed `body::before/::after` backdrop at a negative z-index is painted under body's own background once html
    has a background too, so a filled body hides it completely. On Macz the blurred city backdrop never showed and two
    regrades were tuned blind (L-060). Returns the body background value that buries it, or None."""
    if not re.search(r"(?<![\w-])body::?(?:before|after)\s*(?:,[^{]*)?\{[^}]*z-index\s*:\s*-\d", css):
        return None
    for m in re.finditer(r"(?:^|[}\s,])body\s*\{([^{}]*)\}", css):
        bg = re.search(r"background(?:-color)?\s*:\s*([^;}]+)", m.group(1))
        if bg and not re.match(r"\s*(transparent|none)\b", bg.group(1)):
            return bg.group(1).strip()
    return None


def css_vars(css):
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;}]+)", css)}


def to_rgba(color):
    """'#ff4a4c' / 'rgb(…)' / 'rgba(…)' -> (r, g, b, a) in 0-1, or None."""
    color = color.strip().lower()
    if color.startswith("#"):
        h = color[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            return None
        vals = [int(h[i:i + 2], 16) / 255 for i in range(0, len(h), 2)]
        return (*vals[:3], vals[3] if len(vals) == 4 else 1.0)
    m = re.match(r"rgba?\(([^)]*)\)", color)
    if m:
        nums = re.findall(r"[\d.]+%?", m.group(1))
        if len(nums) < 3:
            return None
        rgb = [float(n[:-1]) / 100 if n.endswith("%") else float(n) / 255 for n in nums[:3]]
        a = nums[3] if len(nums) > 3 else "1"
        return (*rgb, float(a[:-1]) / 100 if a.endswith("%") else float(a))
    return None


def is_glow(shadow):
    """A large-blur shadow in a saturated mid-tone colour (a halo, not an elevation shadow)."""
    for one in re.split(r",(?![^(]*\))", shadow):
        if "inset" in one:
            continue
        colour = re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", one)
        rgba = to_rgba(colour.group(0)) if colour else None
        lengths = re.findall(r"(-?[\d.]+)(px|rem|em)?(?=\s|$)", re.sub(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", " ", one))
        if not rgba or len(lengths) < 3:
            continue
        blur = float(lengths[2][0]) * (16 if lengths[2][1] in ("rem", "em") else 1)
        r, g, b, a = rgba
        mx, mn = max(r, g, b), min(r, g, b)
        light = (mx + mn) / 2
        sat = 0 if mx == mn else (mx - mn) / (1 - abs(2 * light - 1))
        if blur >= 16 and a >= 0.15 and sat >= 0.4 and 0.2 <= light <= 0.85:
            return True
    return False


def light_fringe(path):
    """Share of a cut-out's edge pixels that are much lighter than the subject just inside them: the white
    halo left by removing a white background (portfolio 2026-10-08: white lines round hair and arms; the user
    caught it). Calibrated: that halo scored 34%, clean cut-outs 0%, logos 0-5%. None = no transparency/PIL."""
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except ImportError:
        return None
    im = Image.open(path)
    if im.mode not in ("RGBA", "LA", "PA") and "transparency" not in im.info:
        return None
    im = im.convert("RGBA")
    if im.getchannel("A").getextrema()[0] >= 250:
        return None
    if im.width > 880:
        im = im.resize((880, round(im.height * 880 / im.width)), Image.LANCZOS)

    def box(a, r):
        for axis in (0, 1):
            p = np.pad(a, [((r + 1, r) if ax == axis else (0, 0)) for ax in (0, 1)], mode="edge")
            c = np.cumsum(p, axis=axis)
            a = (np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
                 - np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)) / (2 * r + 1)
        return a

    def erode(m, r):
        return np.asarray(Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(2 * r + 1))) > 127

    a = np.asarray(im.getchannel("A")).astype(np.float32) / 255
    lum = np.asarray(im.convert("RGB")).astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32)
    solid = np.pad(a > 0.5, 6, mode="edge")  # padded: a subject cut by the frame has no edge there
    edge = (solid & ~erode(solid, 2))[6:-6, 6:-6] & (a > 0.15)
    inner = (erode(solid, 3) & ~erode(solid, 9))[6:-6, 6:-6].astype(np.float32)
    weight = box(inner, 6)
    local = box(lum * inner, 6) / np.maximum(weight, 1e-6)
    e = edge & (weight > 0.05)
    return float((lum[e] - local[e] > 30).mean()) if e.any() else None


def main():
    if not DIST.exists():
        sys.exit("dist/ not found: run `python _src/build.py` first")
    errors, warns, placeholders = [], [], []
    usage = defaultdict(list)          # image -> ["page › context"]
    cta_labels = defaultdict(set)      # label -> pages
    empty_tokens = defaultdict(list)   # {{TOKEN}} left in output -> pages
    allow = getattr(C, "ALLOW_PATTERNS", {})  # {"marquee": "why"} for a pattern the client asked for
    cta_label, cta_href = C.PRIMARY_CTA[0], norm(C.PRIMARY_CTA[1])
    h2_total = eyebrow_total = icon_total = 0
    pages = sorted(DIST.glob("*.html"), key=lambda p: (p.name != "index.html", p.name))
    page_words = {}                    # page -> words of its <main>, for the repeated-wording check

    for path in pages:
        name = path.name
        raw = path.read_text(encoding="utf-8")
        p = Page()
        p.feed(raw)
        text = " ".join(" ".join(p.text).split())
        page_words[name] = words(" ".join(p.main_text))

        for t in sorted(set(TOKEN.findall(raw))):
            empty_tokens[t].append(name)
        for img in p.imgs:
            src = img.get("src", "")
            if not src:
                errors.append(f"{name}: <img> without src")
                continue
            ref = norm(src)
            usage[ref].append(name)
            if "alt" not in img:
                errors.append(f"{name}: image without alt attribute: {src}")
            if not ref.startswith(("http", "data:")) and not (DIST / ref).exists():
                errors.append(f"{name}: missing image file {src}")
            if ref.startswith("http"):
                warns.append(f"{name}: hotlinked image {src}: download it into assets/img/")
        for u in p.style_urls:
            usage[norm(u)].append(f"{name} (inline style)")

        for href in p.links:
            if href in ("#", "", None):
                placeholders.append(f"{name}: link with href=\"{href or ''}\" (dead/placeholder link)")
        for s in p.selects:
            opts = s["options"]
            if not opts or s["filter"]:
                continue
            first = opts[0]
            first_val = first["value"] if first["value"] is not None else first["text"].strip()
            if first_val != "":
                errors.append(f"{name}: select '{s['name']}' must start on an empty \"Choose…\" option")
            for o in opts:
                val = o["value"] if o["value"] is not None else o["text"].strip()
                if o["selected"] and val != "":
                    errors.append(f"{name}: select '{s['name']}' preselects '{val}'; never default a choice the visitor didn't make")
        for f in p.forms:
            if "data-endpoint" in f and not f.get("data-endpoint"):
                placeholders.append(f"{name}: form in demo mode (FORM_ENDPOINT empty)")
            if f.get("action", "").lower().startswith("mailto:"):
                errors.append(f"{name}: form posts to mailto: (fails silently, ejects the visitor to a mail app); use FORM_ENDPOINT or demo mode")
            if f["_contact"] and f["_fields"] >= 3 and not f["_next"]:
                errors.append(f"{name}: form has no 'what happens next' line ([data-next-steps]): say who replies, how fast, and what happens after")
        for inp in p.inputs:
            key = " ".join(inp.get(k, "") for k in ("name", "id", "autocomplete")).lower()
            if re.search(r"phone|\btel\b", key) and inp.get("type") != "tel":
                errors.append(f"{name}: phone field '{inp.get('name')}' is type=\"{inp.get('type', 'text')}\"; use type=\"tel\"")
            elif inp.get("type") == "tel" and "pattern" not in inp:
                warns.append(f"{name}: phone field '{inp.get('name')}' accepts letters; add a pattern (see template contact.html)")
        if p.og_image is not None and not p.og_image.startswith(("http://", "https://")):
            errors.append(f"{name}: og:image `{p.og_image}` is relative; social previews need an absolute URL (set DOMAIN)")
        for a in p.anchors:
            if any(c.startswith("btn") for c in a["cls"]) and a["text"] and norm(a["href"] or "") == cta_href \
                    and a["text"].lower() != cta_label.lower():
                errors.append(f"{name}: button '{a['text']}' goes to the primary CTA ({cta_href}) under a different label; "
                              f"use '{cta_label}' or make it a text link")
        nav_labels = defaultdict(set)
        for a in p.anchors:
            href = a["href"] or ""
            if any(c.startswith("btn") or "cta" in c for c in a["cls"]):
                continue  # the CTA button may share a page with a plain "Contact" nav item
            if a["nav"] and a["text"] and href and not href.startswith("#") and not re.match(r"[a-z]+:", href):
                nav_labels[href].add(a["text"])
        for href, labels in nav_labels.items():
            if len({x.lower() for x in labels}) > 1:
                warns.append(f"{name}: nav links to {href} under different names: {', '.join(sorted(labels))}")
        if p.marquee and "marquee" not in allow:
            errors.append(f"{name}: marquee/ticker element: a template tell, and auto-motion needs a pause control. "
                          "Replace it with proof from this business, or add ALLOW_PATTERNS['marquee'] with the reason")
        if p.icon_cards >= 3:
            warns.append(f"{name}: {p.icon_cards} cards that open with an icon (icon-tile rows read as a template)")
        h2_total, eyebrow_total, icon_total = h2_total + p.h2, eyebrow_total + p.eyebrow_h2, icon_total + p.icon_cards
        for label, href in p.primary:
            cta_labels[label].add(name)
        for todo in p.todos:
            placeholders.append(f"{name}: data-todo: {todo}")
        for m in sorted(set(PLACEHOLDER_TEXT.findall(text + " " + raw))):
            placeholders.append(f"{name}: placeholder text `{m}`")
        junk = sorted(set(VISIBLE_JUNK.findall(text)))
        if junk:
            errors.append(f"{name}: visible text contains {', '.join(junk)} (unguarded data?)")
        for m in EMAIL.finditer(text):
            # build's EMAIL_HTML adds <wbr>; a raw address in markup means it was typed by hand
            if m.group(0) in raw and "wrap-anywhere" not in raw[max(0, raw.find(m.group(0)) - 300):raw.find(m.group(0))]:
                warns.append(f"{name}: email `{m.group(0)}` without <wbr>/overflow-wrap; may overflow on phones")
                break

        if C.LOCAL_BUSINESS and not p.header_tel:
            errors.append(f"{name}: no tap-to-call (tel:) link in the header")
        if p.h1 != 1:
            errors.append(f"{name}: {p.h1} <h1> elements (want exactly 1)")
        if not p.title.strip():
            errors.append(f"{name}: empty <title>")
        if name != "404.html" and not (p.desc or "").strip():
            errors.append(f"{name}: empty meta description")
        if 'name="viewport"' not in raw:
            errors.append(f"{name}: missing viewport meta")

    # CSS: images used as backgrounds, motion rules, glows
    for css in sorted((DIST / "assets").rglob("*.css")):
        rel = css.relative_to(DIST).as_posix()
        base = rel.rsplit("/", 1)[0] + "/"
        src = css.read_text(encoding="utf-8")
        for u in re.findall(r"url\(['\"]?([^'\")]+)", src):
            if not u.startswith("data:"):
                usage[norm(u, base)].append(f"{rel} (css)")
        body = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        for found in css_motion(body):
            errors.append(f"{rel}: CSS motion `{found}`: all animation runs in JavaScript (GSAP in motion.js); "
                          "CSS describes the states only")
        for m in re.finditer(r"transition(?:-property)?\s*:([^;}]+)", body):
            bad = re.findall(r"\b(height|width|max-height|max-width|inset|top|left|right|bottom|margin[\w-]*|padding[\w-]*|all)\b", m.group(1))
            if bad:
                warns.append(f"{rel}: transition on {', '.join(sorted(set(bad)))}: animate only transform/opacity")
        for kf in re.finditer(r"@keyframes\s+([\w-]+)\s*\{(.*?)\}\s*\}", body, re.S):
            bad = re.findall(r"\b(height|width|inset|top|left|right|bottom|margin|padding)\s*:", kf.group(2))
            if bad:
                warns.append(f"{rel}: @keyframes {kf.group(1)} animates {', '.join(sorted(set(bad)))}: use transform/opacity")
        if re.search(r"@keyframes|animation\s*:", body) and "prefers-reduced-motion" not in body:
            errors.append(f"{rel}: animations without a prefers-reduced-motion rule")
        if re.search(r"radial-gradient\(", body):
            warns.append(f"{rel}: radial-gradient found: no decorative glows unless the client asked for them")
        cvars = css_vars(body)
        resolve = lambda v: re.sub(r"var\((--[\w-]+)[^)]*\)", lambda m: cvars.get(m.group(1), ""), v)  # noqa: E731
        for m in re.finditer(r"([^{}]+)\{[^{}]*?box-shadow\s*:\s*([^;}]+)", body):
            if is_glow(resolve(resolve(m.group(2)))) and "glow" not in allow:
                errors.append(f"{rel}: coloured glow on `{' '.join(m.group(1).split())[-60:]}` (box-shadow {m.group(2).strip()[:50]}); "
                              "use a neutral elevation shadow")
        for sel, lh in ([] if "tight-leading" in allow else tight_leading(body)):
            errors.append(f"{rel}: line-height {lh} on `{sel}`: below 1 the descenders of one line touch the next "
                          "line's ascenders when the text wraps (L-051); use 1.05+ on display type, or for an "
                          "all-caps face with no descenders set ALLOW_PATTERNS['tight-leading'] in site_config.py")
        if (bg := buried_backdrop(body)):
            errors.append(f"{rel}: `body {{ background: {bg[:40]} }}` paints over the negative-z body::before/::after "
                          "backdrop, so it never shows (L-060); move the page colour to html and make body transparent")
        slide ={k.group(1) for k in re.finditer(r"@keyframes\s+([\w-]+)\s*\{(.*?)\}\s*\}", body, re.S)
                 if re.search(r"translate(X|3d)?\(\s*-?[1-9]", k.group(2))}
        for m in re.finditer(r"animation(?:-name)?\s*:([^;}]+)", body):
            if "infinite" in m.group(1) and any(re.search(rf"\b{re.escape(n)}\b", m.group(1)) for n in slide) \
                    and "marquee" not in allow:
                errors.append(f"{rel}: endless sliding animation ({' '.join(m.group(1).split())}): marquee/ticker; "
                              "auto-motion needs a pause control and reads as a template")

    for path in pages:
        raw = path.read_text(encoding="utf-8")
        inline = re.findall(r"""<style[^>]*>(.*?)</style>|style=["']([^"']*)["']""", raw, re.S)
        for found in css_motion("\n".join(a or b for a, b in inline)):
            errors.append(f"{path.name}: inline CSS motion `{found}`: all animation runs in JavaScript")
        if re.search(r"""<link[^>]+href=["']https://fonts\.googleapis\.com/css""", raw):
            errors.append(f"{path.name}: Google Fonts CSS linked: two render-blocking round trips (L-039). Self-host: "
                          "python tools/self_host_fonts.py \"<css2 URL>\" --preload \"Family:400\"")
    gsap_checks(pages, errors, warns, allow)
    stale_tools(warns)

    for t, where in empty_tokens.items():
        placeholders.insert(0, f"`{{{{{t}}}}}` has no value in site_config.py ({', '.join(where)})")

    allowed = {norm(a) for a in C.ALLOW_REPEAT_IMAGES}
    for ref, where in sorted(usage.items()):
        if len(where) > 1 and ref not in allowed and not BRAND_ASSET.search(ref):
            errors.append(f"image used {len(where)}x: {ref} → {', '.join(where)}")
    if eyebrow_total >= 3 and eyebrow_total >= 0.4 * max(h2_total, 1):
        errors.append(f"{eyebrow_total} of {h2_total} section headings sit under a small label (eyebrow/kicker/pill): "
                      "a template tell; keep it for one or two headings at most")
    if icon_total >= 6:
        errors.append(f"{icon_total} icon-led cards sitewide: replace icon tiles with this business's real work, "
                      "photos or specifics")
    for where, phrase in repeated_wording(page_words, getattr(C, "ALLOW_REPEAT_TEXT", [])):
        short = phrase if len(phrase) <= 90 else phrase[:87] + "…"
        warns.append(f"same wording on {', '.join(where)}: \"{short}\" (each idea once: give it one home, "
                     "mark contact data up as <address>/<table>/<dl>, or list it in ALLOW_REPEAT_TEXT with a reason)")
    if len(cta_labels) > 1:
        warns.append("more than one primary CTA label: " + "; ".join(
            f"'{label}' ({', '.join(sorted(pg))})" for label, pg in cta_labels.items()))

    for img in sorted((DIST / "assets").rglob("*")):
        if img.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".avif") and img.stat().st_size > 450_000:
            warns.append(f"heavy image {img.relative_to(DIST).as_posix()} ({img.stat().st_size // 1024} KB): run tools/optimize_images.py or re-export")
        if img.suffix.lower() in (".png", ".webp") and (share := light_fringe(img)) is not None and share > 0.15:
            errors.append(f"light fringe on cut-out {img.relative_to(DIST).as_posix()}: {share:.0%} of its edge is "
                          "much lighter than the subject (a white-background halo); pull the edge in and recolour it "
                          "from the interior (see the portfolio's tools/cutout_headshot.py, L-038)")

    # Control characters in source: the trace of an escape mangled by a shell heredoc or a scripted edit
    # (L-027 repeat, 2026-10-08: r"<svg\b" became r"<svg<backspace>", so a regex silently stopped matching).
    ctrl = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    # Hard-coded user paths break when the workspace moves (L-055: the pipeline moved into Website Portfolio and
    # qa.py's own template path went dead). Derive paths from Path(__file__) instead.
    abs_path = re.compile(r"[A-Za-z]:(?:/|\\)+Users(?:/|\\)+", re.I)
    for f in sorted([*(ROOT / "_src").rglob("*"), *(ROOT / "assets").rglob("*"), *(ROOT / "tools").glob("*")]):
        if f.is_file() and f.suffix.lower() in (".py", ".html", ".css", ".js", ".mjs", ".svg", ".json", ".md", ".txt"):
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if ctrl.search(line):
                    errors.append(f"{f.relative_to(ROOT).as_posix()}:{n}: control character "
                                  f"{repr(ctrl.search(line).group())} in source (a mangled escape?)")
                if f.suffix.lower() in (".py", ".js", ".mjs", ".html") and abs_path.search(line):
                    warns.append(f"{f.relative_to(ROOT).as_posix()}:{n}: hard-coded user path "
                                 f"({abs_path.search(line).group()}...): derive it from the script's location (L-055)")

    OUT.mkdir(exist_ok=True)
    alloc = ["# Image allocation", "", "| Image | Used on |", "|---|---|"]
    alloc += [f"| {ref} | {', '.join(where)} |" for ref, where in sorted(usage.items())]
    (OUT / "image-allocation.md").write_text("\n".join(alloc) + "\n", encoding="utf-8")

    dedupe = lambda xs: list(dict.fromkeys(xs))  # noqa: E731
    errors, warns, placeholders = dedupe(errors), dedupe(warns), dedupe(placeholders)
    lines = [f"# QA report: {len(pages)} pages", "",
             f"**{len(errors)} errors · {len(warns)} warnings · {len(placeholders)} placeholders**", ""]
    for title, items in (("Errors (must fix)", errors), ("Warnings (fix or justify in PROJECT.md › Decisions)", warns),
                         ("Placeholders (list at handoff, never present as working)", placeholders)):
        lines += [f"## {title}", ""] + ([f"- {i}" for i in items] or ["- none"]) + [""]
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"qa: {len(errors)} errors, {len(warns)} warnings, {len(placeholders)} placeholders -> qa/report.md")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
