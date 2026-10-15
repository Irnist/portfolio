# Ernest Mar Banigon: portfolio

My personal portfolio as a web designer and SEO specialist.

**Live site: [ernestbanigon.pages.dev](https://ernestbanigon.pages.dev)**

![Desktop view of the portfolio homepage](docs/screenshot-desktop.png)

<img src="docs/screenshot-phone.png" alt="Phone view of the portfolio homepage" width="260">

## What's on it

- **Client websites:** four live business sites I designed (Aurora Plumbing & Electric Supply, Children Matter Family Life Center, MaCon Supply and Parker Automotive Service Center).
- **Concept projects:** self-initiated sample sites for car, HVAC, architecture, furniture and gadget businesses, each shown in a desktop and phone frame that scrolls through the whole page.
- **Graphic design:** travel posters made for a travel agency.
- **Process and contact:** the four steps a project goes through, from getting to know the business to search setup and launch, and how to reach me.

## How it's built

- Plain HTML, CSS and JavaScript with no framework. Pages are written as templates in `_src/` and rendered by a small Python build script.
- Animations use [GSAP](https://gsap.com) (ScrollTrigger and SplitText) and switch off for visitors who prefer reduced motion.
- Fonts (Cormorant and Archivo) are self-hosted, and images are served as responsive WebP.
- Hosted on Cloudflare Pages.
- Lighthouse, mobile (2026-10-13): **99** performance, **100** accessibility, **100** best practices, **100** SEO.

## Build it yourself

You need Python 3 and Pillow (`pip install pillow`).

```
python _src/build.py
```

The finished site goes to `dist/`. To preview it, run `python -m http.server 8000 --directory dist` and open http://localhost:8000.

## Folders

| Folder | What's in it |
|---|---|
| `_src/` | Page templates, shared partials, icons, the site settings (`site_config.py`) and the build script |
| `assets/` | Stylesheet, scripts, fonts and images |
| `public/` | Files copied as they are: favicon, share image, robots.txt |
| `client-assets/` | Original photos and screenshots the site's images were made from |
| `tools/` | QA, screenshot and deploy scripts. Most of them are small stubs that run my website pipeline's shared tools, which live in a separate project. |
| `docs/` | Screenshots for this README |
