"""Per-project data for the build: Ernest Mar Banigon's portfolio (one page).

Any BIZ key can be used in pages and partials as {{KEY}}. Contact values are copied from the
user's message (2026-10-08), never retyped.
"""
import html

BIZ = {
    "NAME": "Ernest Mar Banigon",
    "ROLE": "Web Designer & SEO Specialist",
    "PHONE": "+63 9612148125",  # from Ernest's message, 2026-10-08
    "EMAIL": "banigon40@gmail.com",
    "FACEBOOK": "https://www.facebook.com/ernestmar14",
    "LINKEDIN": "https://www.linkedin.com/in/ernest-mar-banigon-052253248/",
    "GITHUB": "https://github.com/Irnist",
    "FIVERR": "https://www.fiverr.com/ernest_mar",  # from Ernest, 2026-10-15 (his link minus ?public_mode=true)
    # Shown above the contact links: who replies, how fast, what happens next. A promise: Ernest confirms it.
    "NEXT_STEPS": "I read every message myself and reply by email within one business day, usually with a few questions about your business and a written quote.",
}

HOURS = []
SERVICES = []

# The one primary CTA sitewide: (label, href). Every other button is ghost or a text link.
PRIMARY_CTA = ("Start a project", "index.html#contact")

FORM_ENDPOINT = ""

DOMAIN = "https://ernestbanigon.pages.dev"

# A portfolio, not a storefront: the phone sits in the contact band and footer, not a header tap-to-call.
LOCAL_BUSINESS = False

# GSAP motion (his request, 2026-10-10): self-hosted from tools/vendor/gsap/, moments in assets/js/motion.js
GSAP = ["ScrollTrigger", "SplitText"]

ALLOW_PATTERNS = {}
ALLOW_REPEAT_IMAGES = []
ALLOW_REPEAT_TEXT = []

PAGES = [
    dict(file="index.html", src="home.html", nav=None,
         title="Ernest Mar Banigon | Web Designer & SEO Specialist",
         desc="Ernest Mar Banigon designs responsive, search-ready small-business websites, "
              "backed by five years of web design and a graphic design background. See his work."),
    dict(file="404.html", src="404.html", nav=None, title="Page not found", desc="", body_class="page-404"),
]

# One-page nav: section anchors, in page order.
SECTIONS = [("Work", "index.html#work"), ("Graphic design", "index.html#design"), ("Process", "index.html#process")]


# Live sites Ernest designed (user, 2026-10-08). URLs from "Live Website URL Links.txt"; descriptions
# only say what each site's own screenshot shows about the business.
CLIENT_WORK = [
    dict(slug="aurora-plumbing", name="Aurora Plumbing & Electric Supply", url="https://www.auroraplumbing.com/",
         domain="auroraplumbing.com",
         text="A Seattle plumbing and electrical supply store, open since 1960, that also runs in-home plumbing service."),
    dict(slug="children-matter", name="Children Matter Family Life Center", url="https://childrenmattertx.org/",
         domain="childrenmattertx.org",
         text="A Texas nonprofit for children, families and caregivers, with clear ways in to sponsor, donate, volunteer or attend an event."),
    dict(slug="macon-supply", name="MaCon Supply", url="https://maconsupply.net/", domain="maconsupply.net",
         text="A construction supplier serving contractors across five states since 1976, with product lines and branch locations up front."),
    dict(slug="parker-auto", name="Parker Automotive Service Center", url="https://www.parkerautoaz.com/",
         domain="parkerautoaz.com",
         text="A Tucson auto repair shop open since 1995, built around booking an appointment or calling the shop."),
]

# Self-initiated concept sites. Preview URLs copied from each project's .pipeline state file.
CONCEPT_WORK = [
    dict(slug="trevor-travis", name="Trevor Travis Motors",
         url="https://trevor-travis-motors-website-preview.netlify.app",
         text="A motorcycle shop: bikes on the floor, the parts counter and in-house installment plans, each with its own page."),
    dict(slug="macz", img="macz-v2", name="Macz Arkitektura",  # img: new file name after the 2026-10-10 redesign (L-037)
         url="https://macz-arkitektura-website-preview.ebanigon-previews.workers.dev",
         text="A design-and-build architecture firm in Alabang, with its services, a project gallery and consultation booking."),
    dict(slug="gadget-zone", name="Gadget Zone",
         url="https://gadget-zone-website-preview.ebanigon-previews.workers.dev",
         text="A gadget store in Muntinlupa City, with a filterable shop, open-box deals and a reserve list that turns into an order request."),
    dict(slug="ironcity", name="IronCity Rods & Customs",
         url="https://iron-city-website-preview.ebanigon-previews.workers.dev",
         text="A classic car restoration shop in Punta Gorda, Florida, with a build gallery and filterable inventory."),
    dict(slug="ironwood", name="Ironwood Heating & Air",
         url="https://hvac-website-preview.ebanigon-previews.workers.dev",
         text="An aircon cleaning and repair company in Muntinlupa City, with service pricing and a quote form."),
    dict(slug="weknz", name="Weknz Patio Furniture",
         url="https://weknz-patio-furniture-preview.ebanigon-previews.workers.dev",
         text="A family patio furniture showroom in Shacklefords, Virginia, built around planning a visit."),
]

# Solasta Travel and Tours promotions, in grid order (3 x 2). The domestic series (Calaguas, Ilocos) was
# dropped after review: its flat price circles read as empty placeholders.
POSTERS = [
    ("korea-winter", "Korea winter tour, 2020"),
    ("malaysia", "Malaysia promo, 2019"),
    ("bangkok", "Bangkok promo, 2019"),
    ("holy-land", "Pilgrims’ journey to the Holy Land"),
    ("puerto-princesa", "Puerto Princesa and the Underground River"),
    ("korea-autumn", "Korea autumn group departure, 2019"),
]

# Tools Ernest works in (his list, 2026-10-08: CapCut -> Claude Code, Premiere -> Lightroom).
# (icon, name): one colour for the whole name, his call (2026-10-08).
SKILLS = [
    ("skill-duda", "Duda Builder"),
    ("skill-photoshop", "Photoshop"),
    ("skill-illustrator", "Illustrator"),
    ("skill-canva", "Canva"),
    ("skill-wordpress", "WordPress"),
    ("skill-claude-code", "Claude Code"),
    ("skill-lightroom", "Adobe Lightroom"),
    ("skill-html-css", "HTML &amp; CSS"),
]


def _icon(name):
    """Inline SVG from _src/icons (helpers' output isn't re-rendered, so {{i:...}} can't be used here)."""
    import re
    from pathlib import Path
    svg = (Path(__file__).parent / "icons" / f"{name}.svg").read_text(encoding="utf-8").strip()
    return re.sub(r"<svg\b", '<svg class="icon skill__icon" aria-hidden="true" focusable="false"', svg, count=1)


def _screen(w, label, extra=""):
    return (f'<div class="sheet work__sheet">'
            f'<div class="browser"><p class="browser__bar">{html.escape(label)}</p>'
            f'<div class="browser__screen"><img src="assets/img/work/{w.get("img", w["slug"])}.webp" '
            f'alt="{html.escape(w["name"])} website, homepage" loading="lazy" decoding="async"></div>'
            # Shown by main.js: lets touch and keyboard users run the same scroll-through as hover.
            f'<button class="browser__play" type="button" aria-pressed="false" data-play hidden>'
            f'Scroll the page<span class="sr-only"> of {html.escape(w["name"])}</span></button></div>'
            f'{extra}</div>')


def h_client_work(page, arg=None):
    out = []
    for w in CLIENT_WORK:
        out.append(
            f'<li class="work">{_screen(w, w["domain"])}'
            f'<h3 class="work__name">{html.escape(w["name"])}</h3>'
            f'<p class="work__text">{html.escape(w["text"])}</p>'
            f'<p class="work__meta">Website design</p>'
            f'<a class="work__link" href="{w["url"]}" target="_blank" rel="noopener">'
            f'Visit {html.escape(w["domain"])}<span aria-hidden="true"> ↗</span>'
            f'<span class="sr-only"> (opens in a new tab)</span></a></li>')
    return "".join(out)


def h_concept_work(page, arg=None):
    out = []
    for w in CONCEPT_WORK:
        phone = (f'<img class="work__phone" src="assets/img/work/{w.get("img", w["slug"])}-phone.webp" '
                 f'alt="" loading="lazy" decoding="async">')
        out.append(
            f'<li class="work">{_screen(w, "Concept preview", phone)}'
            f'<h3 class="work__name">{html.escape(w["name"])}</h3>'
            f'<p class="work__text">{html.escape(w["text"])}</p>'
            # No role line: the section intro already says I planned, wrote, designed and built each one,
            # and six identical labels cost ~170px of phone height (2026-10-09).
            f'<a class="work__link" href="{w["url"]}" target="_blank" rel="noopener">'
            f'Open the preview<span aria-hidden="true"> ↗</span>'
            f'<span class="sr-only"> of {html.escape(w["name"])} (opens in a new tab)</span></a></li>')
    return "".join(out)


def h_posters(page, arg=None):
    out = []
    for slug, caption in POSTERS:
        cap = html.escape(caption)
        out.append(
            f'<li class="poster"><a class="sheet poster__sheet" href="assets/img/posters/{slug}-large.webp" '
            f'data-lightbox="{cap}"><img src="assets/img/posters/{slug}.webp" alt="Poster: {cap}" '
            f'loading="lazy" decoding="async"></a><p class="poster__caption">{cap}</p></li>')
    return "".join(out)


def h_skills(page, arg=None):
    return "".join(f'<li class="skill">{_icon(icon)}<span class="skill__name">{name}</span></li>'
                   for icon, name in SKILLS)


def h_nav(page, arg=None):
    items = "".join(f'<li><a href="{href}">{html.escape(label)}</a></li>' for label, href in SECTIONS)
    return f"<ul>{items}</ul>"


def h_person_ld(page, arg=None):
    """schema.org Person on the homepage only (PAGE values aren't re-rendered, so this is a helper)."""
    import json
    if page["file"] != "index.html":
        return ""
    return '<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org",
        "@type": "Person",
        "name": BIZ["NAME"],
        "jobTitle": BIZ["ROLE"],
        "email": f"mailto:{BIZ['EMAIL']}",
        "telephone": BIZ["PHONE"].replace(" ", ""),
        "url": DOMAIN + "/",
        "image": DOMAIN + "/assets/img/me/ernest-mar-banigon-v2.webp",
        "sameAs": [BIZ["LINKEDIN"], BIZ["GITHUB"], BIZ["FIVERR"], BIZ["FACEBOOK"]],
        "knowsAbout": ["Web design", "Responsive web design", "Search engine optimization", "Graphic design",
                       "Duda", "Adobe Photoshop", "Adobe Illustrator", "Canva", "WordPress", "Claude Code",
                       "Adobe Lightroom", "HTML", "CSS"],
    }, ensure_ascii=False) + "</script>"


def h_og_image(page, arg=None):
    return f'<meta property="og:image" content="{DOMAIN}/og-image.png">'


HELPERS = {"nav": h_nav, "person_ld": h_person_ld, "og_image": h_og_image,
           "client_work": h_client_work, "concept_work": h_concept_work, "posters": h_posters,
           "skills": h_skills}
