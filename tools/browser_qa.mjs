// Browser QA in headless Chrome: screenshots + rendered-layout checks. No npm packages needed.
//
//   node tools/browser_qa.mjs                 every page in dist/
//   node tools/browser_qa.mjs index.html ...  just these pages
//   node tools/browser_qa.mjs --no-lighthouse skip the Lighthouse pass (quick re-checks while iterating)
//
// Viewports 360x780, 390x844 and 1440x900, one page at a time in ONE browser
// (parallel Chrome instances collide). Reduced motion is emulated so reveals render (and parallax holds still).
// Pages that load GSAP get a second pass at 390/1440 with motion on (motionChecks): tweened properties,
// clashes with .reveal/data-parallax, a hidden hero at load, overflow while scrolling, content left invisible.
// Contrast: CSS colours for text on plain surfaces; on-screen pixels for SVG graphics and text on photos.
// Accessibility: axe-core (tools/vendor/axe.min.js, WCAG 2.2 A/AA rules; its colour-contrast rule is off
// because the contrast checks here are calibrated for photos). Then Lighthouse mobile (tools/lighthouse.mjs),
// after this browser has closed. Writes qa/shots/<page>-<width>-fold.png and -full.png (390, 1440) and
// qa/browser-report.md. Exit code 1 when an error-level check fails.
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { lighthouse, scoreTable } from './lighthouse.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const AXE = join(dirname(fileURLToPath(import.meta.url)), 'vendor', 'axe.min.js');
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
// serious in axe, but a warning here: it fired on Trevor Travis's brand link (spans "Trevor Travis" + "Motors"
// with no space between, label "Trevor Travis Motors, home"), where speech users still hit the link
const AXE_WARN_ONLY = new Set(['label-content-name-mismatch']);
const DIST = join(ROOT, 'dist');
const OUT = join(ROOT, 'qa');
const SHOTS = join(OUT, 'shots');
const VIEWPORTS = [
  { name: '360', width: 360, height: 780, mobile: true, shots: false },
  { name: '390', width: 390, height: 844, mobile: true, shots: true },
  { name: '1440', width: 1440, height: 900, mobile: false, shots: true },
];
const CHROME = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
].find(p => p && existsSync(p));

const sleep = ms => new Promise(r => setTimeout(r, ms));

// ------------------------------------------------------------------ in-page checks
// Serialised into the page with Runtime.evaluate; must be self-contained.
async function pageChecks(vp) {
  const errors = [], warnings = [];
  const vw = document.documentElement.clientWidth;
  const path = el => {
    const parts = [];
    for (let n = el; n && n !== document.body && parts.length < 3; n = n.parentElement) {
      let s = n.tagName.toLowerCase();
      if (n.id) { parts.unshift(`${s}#${n.id}`); break; }
      const cls = [...n.classList].filter(c => !c.startsWith('is-')).slice(0, 2).join('.');
      parts.unshift(cls ? `${s}.${cls}` : s);
    }
    return parts.join(' > ');
  };
  const visible = el => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0;
  };
  const snippet = el => (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40);

  // -- horizontal overflow (also when hidden by overflow-x on html/body)
  const masked = ['hidden', 'clip'].includes(getComputedStyle(document.documentElement).overflowX) ||
                 ['hidden', 'clip'].includes(getComputedStyle(document.body).overflowX);
  const offenders = [...document.querySelectorAll('body *')].filter(el => {
    if (el.closest('[aria-hidden="true"], .sr-only') || !visible(el)) return false;
    if (getComputedStyle(el).position === 'fixed') return false;  // sized to the (already widened) viewport
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return false;
    if (!(r.right > vw + 1 || r.left < -1)) return false;
    // ignore content inside an intentional horizontal scroller or clipping box
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox !== 'visible') return false;
    }
    return true;
  });
  const outer = offenders.filter(el => !offenders.includes(el.parentElement)).slice(0, 6);
  if (document.documentElement.scrollWidth > vw + 1 || (masked && outer.length)) {
    errors.push(`horizontal overflow at ${vw}px${masked ? ' (masked by overflow-x on html/body)' : ''}: ` +
      outer.map(el => `${path(el)} → ${Math.round(el.getBoundingClientRect().right)}px`).join('; '));
  }

  // -- mobile: tap-to-call visible in header; hero CTA above the fold at 390x844
  if (vp.mobile) {
    // any visible one counts: sites often hide the desktop number and show a separate call button
    const tels = [...document.querySelectorAll('header a[href^="tel:"]')];
    if (tels.length && !tels.some(visible)) errors.push('header tap-to-call link is hidden on mobile');
    // menu toggle at the right edge (portfolio 2026-10: a `.cta + .toggle { margin-left: 0 }` rule still matched
    // after the CTA was hidden on phones, so the burger sat beside the logo; the user caught it)
    const toggle = [...document.querySelectorAll('header button[aria-expanded], header button[aria-controls]')].find(visible);
    if (toggle) {
      const gap = Math.round(vw - toggle.getBoundingClientRect().right);
      if (gap > 40) errors.push(`mobile menu toggle sits ${gap}px from the right edge at ${vw}px: push it to the end of the header bar`);
    }
    if (vp.name === '390') {
      const first = document.querySelector('main > :first-child');
      const cta = first && first.querySelector('.btn-primary');
      if (cta && cta.getBoundingClientRect().bottom > vp.height) {
        errors.push(`hero CTA below the fold: bottom at ${Math.round(cta.getBoundingClientRect().bottom)}px > ${vp.height}px`);
      }
      // homepage length: IronCity was ~11,700px and Weknz ~14,000px on a phone; both critiques asked for cuts
      if (/(^|\/)(index\.html)?$/.test(location.pathname)) {
        const h = document.documentElement.scrollHeight;
        const sections = document.querySelectorAll('main > section, main > div > section').length;
        const msg = `homepage is ${h}px tall at 390 (${sections} sections): distil to ~8 sections, cut repeated benefit/gallery blocks`;
        if (h > 10000) errors.push(msg);
        else if (h > 8000 || sections > 9) warnings.push(msg);
      }
    }
  }

  // -- wrapping pills/badges/buttons, dropped icons
  const lineCount = el => {
    const range = document.createRange();
    range.selectNodeContents(el);
    const tops = [...range.getClientRects()].filter(r => r.width > 0).map(r => r.top).sort((a, b) => a - b);
    const fs = parseFloat(getComputedStyle(el).fontSize) || 16;
    let lines = tops.length ? 1 : 0;
    for (let i = 1; i < tops.length; i++) if (tops[i] - tops[i - 1] > fs * 0.8) lines++;
    return lines;
  };
  document.querySelectorAll('.badge, .pill, .chip, .tag, .btn, [class*="badge"], [class*="pill"]').forEach(el => {
    // a container of pills (e.g. .pillbar) matches [class*="pill"] but is meant to span rows (Gadget Zone 2026-10)
    if (el.querySelector('.badge, .pill, .chip, .tag, .btn')) return;
    if (visible(el) && lineCount(el) > 1) warnings.push(`wraps onto ${lineCount(el)} lines: ${path(el)} "${snippet(el)}"`);
  });
  // nav labels on two lines (Trevor Travis 2026-10: six items + phone + CTA wrapped at 1440)
  document.querySelectorAll('header nav a').forEach(el => {
    if (visible(el) && lineCount(el) > 1) errors.push(`nav link wraps onto ${lineCount(el)} lines at ${vw}px: "${snippet(el)}"`);
  });
  // sideways scrollers on phones cut text at the viewport edge (Trevor Travis 2026-10: installment table)
  if (vp.mobile) {
    document.querySelectorAll('body *').forEach(el => {
      const ox = getComputedStyle(el).overflowX;
      if (!['auto', 'scroll'].includes(ox) || !visible(el) || el.scrollWidth <= el.clientWidth + 1) return;
      if (!(el.textContent || '').trim()) return;
      // deliberate rails of whole items (pill sub-navs, scroll-snap card rails) are a pattern, not cut text
      if (el.closest('nav') || getComputedStyle(el).scrollSnapType !== 'none') return;
      warnings.push(`sideways scroller at ${vw}px (text cut at the edge; stack it instead): ${path(el)} "${snippet(el)}"`);
    });
  }
  document.querySelectorAll('svg.icon').forEach(svg => {
    const row = svg.parentElement;
    if (!row || !visible(row) || !visible(svg)) return;
    // stacked on purpose (icon above label) or a positioned decoration (select chevron): not a dropped icon
    const rs = getComputedStyle(row);
    if (/flex/.test(rs.display) && rs.flexDirection.startsWith('column')) return;
    if (/grid/.test(rs.display) || ['absolute', 'fixed'].includes(getComputedStyle(svg).position)) return;
    const text = [...row.childNodes].find(n => n !== svg && (n.nodeType === 3 ? n.textContent.trim() : n.nodeType === 1 && n.textContent.trim()));
    if (!text) return;
    // a block-level label (h3, p, div) under the icon is a layout choice; only wrapping inline text is a drop
    if (text.nodeType === 1 && !/^inline/.test(getComputedStyle(text).display)) return;
    const range = document.createRange();
    range.selectNodeContents(text);
    const t = range.getBoundingClientRect(), s = svg.getBoundingClientRect();
    if (t.height && (s.bottom <= t.top + 1 || s.top >= t.bottom - 1)) errors.push(`icon dropped onto its own line: ${path(row)} "${snippet(row)}"`);
  });

  // -- images: broken, or upscaled (blurry)
  document.querySelectorAll('img').forEach(img => {
    if (!img.getAttribute('src')) return;  // no src at all: qa.py reports it (JS-filled dialog images)
    if (img.complete && img.naturalWidth === 0) { errors.push(`broken image: ${img.getAttribute('src')}`); return; }
    const r = img.getBoundingClientRect();
    if (r.width > 200 && img.naturalWidth && r.width * devicePixelRatio > img.naturalWidth * 1.3 && getComputedStyle(img).objectFit !== 'contain') {
      warnings.push(`upscaled ${Math.round(r.width)}px from ${img.naturalWidth}px source (blurry): ${img.getAttribute('src')}`);
    }
  });

  // -- rendered contrast for every visible text node, on whatever surface it sits on
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const rgba = color => {
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = '#000';
    ctx.fillStyle = color;  // canvas normalises oklch(), color-mix(), named colours, etc.
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
    return [r, g, b, a / 255];
  };
  const over = (top, bottom) => [0, 1, 2].map(i => top[i] * top[3] + bottom[i] * (1 - top[3])).concat(1);
  const lum = c => {
    const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
  const hex = c => '#' + c.slice(0, 3).map(v => Math.round(v).toString(16).padStart(2, '0')).join('');

  const background = el => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.backgroundImage !== 'none') return null;  // gradient/photo: judged visually
      const c = rgba(cs.backgroundColor);
      if (c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
    }
    return layers.reverse().reduce((acc, c) => over(c, acc), [255, 255, 255, 1]);
  };
  const overMedia = el => {
    const r = el.getBoundingClientRect();
    const x = Math.min(Math.max(r.left + r.width / 2, 0), innerWidth - 1), y = r.top + r.height / 2;
    if (y < 0 || y >= innerHeight) return false;
    const stack = document.elementsFromPoint(x, y);
    const i = stack.indexOf(el);
    return stack.slice(i + 1).some(n => /^(IMG|VIDEO|PICTURE|CANVAS|IFRAME)$/.test(n.tagName));
  };

  const fails = new Map(), skipped = new Set();
  const textEls = [...document.querySelectorAll('body *')].filter(el =>
    [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) &&
    !el.closest('script, style, noscript, [aria-hidden="true"], .sr-only, option') && visible(el));
  const pageH = document.documentElement.scrollHeight;
  for (let y = 0; y < pageH; y += innerHeight) {
    window.scrollTo(0, y);
    // let scroll handlers run (a header that turns solid once scrolled), as a visitor would see it
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 300))));
    for (const el of textEls) {
      const r = el.getBoundingClientRect();
      if (r.top + r.height / 2 < 0 || r.top + r.height / 2 >= innerHeight) continue;
      if (el.matches(':disabled')) continue;
      const bg = background(el);
      if (!bg || overMedia(el)) { skipped.add(path(el)); continue; }
      const cs = getComputedStyle(el);
      let fg = over(rgba(cs.webkitTextFillColor || cs.color), bg);
      // outline text (IronCity's "01" step numerals): the stroke is what's visible
      if (parseFloat(cs.webkitTextStrokeWidth) > 0) {
        const stroke = over(rgba(cs.webkitTextStrokeColor), bg);
        if (ratio(stroke, bg) > ratio(fg, bg)) fg = stroke;
      }
      const size = parseFloat(cs.fontSize), weight = parseInt(cs.fontWeight, 10) || 400;
      const need = size >= 24 || (size >= 18.66 && weight >= 700) ? 3 : 4.5;
      const got = ratio(fg, bg);
      if (got < need) {
        const key = `${hex(fg)} on ${hex(bg)}`;
        if (!fails.has(key)) fails.set(key, { got, need, examples: [] });
        const f = fails.get(key);
        const ex = `${path(el)} "${snippet(el)}"`;
        if (f.examples.length < 3 && !f.examples.includes(ex)) f.examples.push(ex);
      }
    }
  }
  window.scrollTo(0, 0);
  for (const [key, f] of fails) errors.push(`contrast ${f.got.toFixed(2)}:1 < ${f.need}:1, ${key}: ${f.examples.join('; ')}`);

  // -- cover crops that throw most of the photo away (Gadget Zone 2026-10: a phone card's 8rem side column
  // cut each 4:3 product photo to a ~20% sliver). Opt out with data-crop-ok on a deliberate detail crop.
  for (const img of document.images) {
    if (!img.naturalWidth || !img.offsetWidth || !img.offsetHeight || img.hasAttribute('data-crop-ok')) continue;
    if (getComputedStyle(img).objectFit !== 'cover') continue;
    const bw = img.offsetWidth, bh = img.offsetHeight, ar = img.naturalWidth / img.naturalHeight;
    const keepW = Math.min(1, bw / (bh * ar)), keepH = Math.min(1, (bw / ar) > bh ? bh / (bw / ar) : 1);
    const keep = Math.min(keepW, keepH);
    if (keep < 0.45) {
      const src = decodeURI(img.getAttribute('src') || '').replace(/^.*?\/dist\//, '');
      warnings.push(`cover crop shows only ${Math.round(keep * 100)}% of the photo's ${keepW < keepH ? 'width' : 'height'} (subject likely cut; fix the frame's aspect ratio): ${path(img)} ${src}`);
    }
  }

  // -- srcset picks (build.py adds WebP srcsets): at 1x, Chrome takes the smallest candidate >= sizes.
  // object-fit: cover in a tall frame draws the photo wider than its box, so sizes="100vw" would pick
  // a file too small (blurry hero); a sizes far above the drawn width wastes bytes (LCP).
  for (const img of document.images) {
    if (!img.srcset || !img.naturalWidth || !img.offsetWidth || !img.currentSrc) continue;
    const cands = img.srcset.split(',').map(s => s.trim().split(/\s+/))
      .map(([u, w]) => ({ u, w: parseInt(w, 10) })).filter(c => c.w).sort((a, b) => a.w - b.w);
    const picked = cands.find(c => img.currentSrc.endsWith(c.u.replace(/^\.?\//, '')));
    if (!picked) continue;
    const boxW = img.offsetWidth, boxH = img.offsetHeight, ar = img.naturalWidth / img.naturalHeight;
    const fit = getComputedStyle(img).objectFit;
    const drawn = Math.round(fit === 'cover' ? Math.max(boxW, boxH * ar) : fit === 'contain' ? Math.min(boxW, boxH * ar) : boxW);
    const best = cands.find(c => c.w >= drawn) || cands[cands.length - 1];
    const hint = `sizes="${Math.ceil(drawn / vw * 100)}vw" at this width`;
    // the lazy-load workaround above re-sets src, which makes the attribute an absolute file:// URL
    const src = decodeURI(img.getAttribute('src') || '').replace(/^.*?\/dist\//, '');
    if (picked.w < drawn * 0.95 && picked.w < best.w) {
      warnings.push(`image drawn ${drawn}px wide but srcset picked ${picked.w}w (blurry): set sizes on it, e.g. ${hint}: ${path(img)} ${src}`);
    } else if (picked.w > drawn * 2 && best.w < picked.w) {
      warnings.push(`image drawn ${drawn}px wide but srcset picked ${picked.w}w (wasted bytes): set sizes on it, e.g. ${hint}: ${path(img)} ${src}`);
    }
  }
  return { errors, warnings, overMediaCount: skipped.size };
}

// ------------------------------------------------------------------ pixel contrast (L-031)
// The CSS-colour contrast check above can't see what sits behind an element on a photo or gradient,
// and it only checks text. This pass measures real pixels: it hides the elements, screenshots the
// viewport, and compares each element's colour with what was underneath.
//  - single-colour SVG graphics (icons, dividers, strokes) anywhere: error below 3:1 (WCAG 1.4.11).
//    Macz's brown horizon divider sat on a dark photo band at ~1.2:1 and the user caught it.
//  - text on photos/gradients (skipped above): warning when the less favourable 15% of the
//    pixels behind it give below 4.5:1 (3:1 for large text).
// Installs window.__qaPx; Node drives it step by step (pixelContrast below).
function pixelProbe() {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const dot = document.createElement('canvas'); dot.width = dot.height = 1;
  const dctx = dot.getContext('2d', { willReadFrequently: true });
  const rgba = color => {
    dctx.clearRect(0, 0, 1, 1); dctx.fillStyle = '#000'; dctx.fillStyle = color; dctx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = dctx.getImageData(0, 0, 1, 1).data; return [r, g, b, a / 255];
  };
  const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  const lum = c => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
  const ratioL = (a, b) => (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  const hex = c => '#' + c.slice(0, 3).map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
  const path = el => {
    const parts = [];
    for (let n = el; n && n !== document.body && parts.length < 3; n = n.parentElement) {
      const s = n.tagName.toLowerCase();
      if (n.id) { parts.unshift(`${s}#${n.id}`); break; }
      const cls = [...(n.classList || [])].filter(c => !c.startsWith('is-')).slice(0, 2).join('.');
      parts.unshift(cls ? `${s}.${cls}` : s);
    }
    return parts.join(' > ');
  };
  const shown = el => {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width >= 6 && r.height >= 3 && cs.visibility !== 'hidden' && cs.display !== 'none' && !el.closest('[hidden], .sr-only');
  };
  const opacity = el => { let o = 1; for (let n = el; n && n.nodeType === 1; n = n.parentElement) o *= +getComputedStyle(n).opacity; return o; };

  // colours are read at measuring time: a header's ink changes once the page scrolls
  const svgInk = svg => {
    const colours = new Set();
    for (const shape of svg.querySelectorAll('path, circle, rect, line, polyline, polygon, ellipse')) {
      const cs = getComputedStyle(shape);
      for (const paint of [cs.fill, cs.stroke]) {
        if (!paint || paint === 'none' || paint.startsWith('url(')) continue;
        const c = rgba(paint);
        if (c[3] > 0) colours.add(hex(c));
      }
    }
    if (colours.size !== 1) return null;  // multi-colour (a logo): not judged
    const fg = rgba([...colours][0]);
    fg[3] *= opacity(svg);
    return fg;
  };
  const textInk = el => {
    const cs = getComputedStyle(el), fg = rgba(cs.webkitTextFillColor || cs.color);
    fg[3] *= opacity(el);
    return fg;
  };

  const items = [];
  for (const svg of document.querySelectorAll('body svg')) {
    if (svg.parentElement.closest('svg') || !shown(svg) || !svgInk(svg)) continue;
    items.push({ el: svg, kind: 'graphic', ink: svgInk, need: 3, label: path(svg) });
  }
  // text on a photo or gradient (the CSS check skips these)
  const onMedia = el => {
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.backgroundImage !== 'none') return true;
      if (rgba(cs.backgroundColor)[3] >= 1) break;
    }
    const r = el.getBoundingClientRect();
    const stack = document.elementsFromPoint(r.left + r.width / 2, Math.min(Math.max(r.top + r.height / 2, 0), innerHeight - 1));
    return stack.slice(stack.indexOf(el) + 1).some(n => /^(IMG|VIDEO|PICTURE|CANVAS)$/.test(n.tagName));
  };
  for (const el of document.querySelectorAll('body *')) {
    if (!/\S/.test([...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(''))) continue;
    if (el.closest('script, style, noscript, svg, option, [aria-hidden="true"]') || !shown(el)) continue;
    if (rgba(getComputedStyle(el).backgroundColor)[3] > 0) continue;  // its own fill is the background
    const cs = getComputedStyle(el), size = parseFloat(cs.fontSize), weight = parseInt(cs.fontWeight, 10) || 400;
    items.push({ el, kind: 'text', ink: textInk, need: size >= 24 || (size >= 18.66 && weight >= 700) ? 3 : 4.5,
      label: `${path(el)} "${el.textContent.trim().replace(/\s+/g, ' ').slice(0, 30)}"`, candidate: true });
  }

  const results = [];
  let hidden = [], pending = [];
  window.__qaPx = {
    steps() {
      const h = document.documentElement.scrollHeight, step = Math.max(200, Math.floor(innerHeight / 2));
      const ys = []; for (let y = 0; y < h; y += step) ys.push(y); return ys;
    },
    // scroll, decide which items are measurable here, hide every item, wait two frames
    async hide(y) {
      window.scrollTo(0, y);
      const settle = () => new Promise(res => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(res, 100))));
      await settle();  // scroll handlers (a header that turns solid) run first
      pending = [];
      for (const it of items) {
        if (it.done) continue;
        const r = it.el.getBoundingClientRect();
        if (r.top < 0 || r.left < 0 || r.bottom > innerHeight || r.right > innerWidth) continue;
        const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        if (!top || !(top === it.el || it.el.contains(top) || top.contains(it.el))) continue;  // covered (sticky header…)
        if (it.candidate && !onMedia(it.el)) { it.done = true; continue; }  // plain surface: the CSS check covers it
        const fg = it.ink(it.el);
        if (!fg) continue;
        pending.push({ it, fg, r: { x: r.left, y: r.top, w: r.width, h: r.height } });
      }
      // graphics: visibility hidden; text: transparent ink only, so a child with its own fill (a pill, a button) stays put
      hidden = [];
      for (const it of items) {
        const props = it.kind === 'graphic' ? { visibility: 'hidden' } : { color: 'transparent', '-webkit-text-fill-color': 'transparent', 'text-shadow': 'none' };
        for (const [prop, value] of Object.entries(props)) {
          hidden.push([it.el, prop, it.el.style.getPropertyValue(prop), it.el.style.getPropertyPriority(prop)]);
          it.el.style.setProperty(prop, value, 'important');
        }
      }
      await settle();
      return pending.length;
    },
    restore() {
      for (const [el, prop, v, p] of hidden.reverse()) v ? el.style.setProperty(prop, v, p) : el.style.removeProperty(prop);
      hidden = [];
    },
    async measure(png) {
      this.restore();
      if (!pending.length) return true;
      const img = new Image(); img.src = 'data:image/png;base64,' + png; await img.decode();
      const scale = img.naturalWidth / innerWidth;
      canvas.width = img.naturalWidth; canvas.height = img.naturalHeight; ctx.drawImage(img, 0, 0);
      for (const { it, fg: ink, r } of pending) {
        const x = Math.round(r.x * scale), y = Math.round(r.y * scale);
        const w = Math.max(1, Math.round(r.w * scale)), h = Math.max(1, Math.round(r.h * scale));
        const d = ctx.getImageData(x, y, w, h).data, ls = [], sum = [0, 0, 0];
        for (let i = 0; i < d.length; i += 4) { ls.push(lum(d.slice(i, i + 3))); sum[0] += d[i]; sum[1] += d[i + 1]; sum[2] += d[i + 2]; }
        const n = d.length / 4, mean = sum.map(v => v / n);
        // the element's colour as painted over the average background
        const fg = [0, 1, 2].map(i => ink[i] * ink[3] + mean[i] * (1 - ink[3]));
        const lf = lum(fg);
        let lb;
        if (it.kind === 'graphic') lb = lum(mean);
        else { ls.sort((a, b) => a - b); const light = lf > ls[ls.length >> 1]; lb = ls[Math.floor((ls.length - 1) * (light ? 0.85 : 0.15))]; }
        const got = ratioL(lf, lb);
        it.done = true;
        if (got < it.need) results.push({ kind: it.kind, got: +got.toFixed(2), need: it.need, fg: hex(fg), bg: hex(mean), label: it.label });
      }
      return true;
    },
    report() { this.restore(); window.scrollTo(0, 0); return results; },
  };
  return items.length;
}

async function pixelContrast(send) {
  const errors = [], warnings = [];
  if (!(await evaluate(send, `(${pixelProbe.toString()})()`))) return { errors, warnings };
  for (const y of await evaluate(send, '__qaPx.steps()')) {
    const n = await evaluate(send, `__qaPx.hide(${y})`);
    if (!n) { await evaluate(send, '__qaPx.restore(), true'); continue; }
    const shot = await send('Page.captureScreenshot', { format: 'png' });
    await evaluate(send, `__qaPx.measure(${JSON.stringify(shot.data)})`);
  }
  const seen = new Set();
  for (const f of await evaluate(send, '__qaPx.report()')) {
    const key = `${f.kind} ${f.fg} ${f.label}`;
    if (seen.has(key)) continue;
    seen.add(key);
    if (f.kind === 'graphic') errors.push(`graphic contrast ${f.got}:1 < 3:1 (measured on screen), ${f.fg} on ~${f.bg}: ${f.label}`);
    else warnings.push(`text on photo/gradient ~${f.got}:1 < ${f.need}:1 behind its brighter/darker 15%, ${f.fg} on ~${f.bg}: ${f.label}`);
  }
  return { errors, warnings };
}

// ------------------------------------------------------------------ axe-core
// WCAG 2.2 A/AA rules the custom checks don't cover: names for links, buttons and form fields, ARIA misuse,
// landmarks, duplicate ids, target size, ... Critical/serious = error, moderate/minor = warning.
// seen (per page) keeps a violation from being repeated at every viewport.
let axeSource;
async function axeChecks(send, seen) {
  const errors = [], warnings = [];
  if (!existsSync(AXE)) return { errors, warnings: ['axe-core not found at tools/vendor/axe.min.js: WCAG rules not run'] };
  axeSource ??= readFileSync(AXE, 'utf8');
  await evaluate(send, `${axeSource};true`);
  const violations = await evaluate(send, `axe.run(document, {
    runOnly: { type: 'tag', values: ${JSON.stringify(AXE_TAGS)} },
    rules: { 'color-contrast': { enabled: false } }, resultTypes: ['violations'],
  }).then(r => r.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help,
    nodes: v.nodes.map(n => n.target.join(' ')) })))`);
  for (const v of violations) {
    const nodes = v.nodes.filter(n => !seen.has(`${v.id} ${n}`));
    if (!nodes.length) continue;
    nodes.forEach(n => seen.add(`${v.id} ${n}`));
    const msg = `axe ${v.id} (${v.impact}): ${v.help}: ${nodes.slice(0, 4).join('; ')}${nodes.length > 4 ? ` (+${nodes.length - 4} more)` : ''}`;
    (['critical', 'serious'].includes(v.impact) && !AXE_WARN_ONLY.has(v.id) ? errors : warnings).push(msg);
  }
  return { errors, warnings };
}

// ------------------------------------------------------------------ CDP plumbing
async function launch() {
  if (!CHROME) throw new Error('Chrome/Edge not found; set CHROME_PATH');
  const profile = mkdtempSync(join(tmpdir(), 'site-qa-'));
  const proc = spawn(CHROME, [
    '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', '--disable-gpu',
    '--disable-extensions', '--force-color-profile=srgb', 'about:blank',
  ], { stdio: 'ignore' });
  const portFile = join(profile, 'DevToolsActivePort');
  let port;
  for (let i = 0; i < 150 && !port; i++) {
    await sleep(100);
    // Windows: Chrome may still hold the file open (EBUSY) on the first poll; just try again next tick
    if (existsSync(portFile)) { try { port = readFileSync(portFile, 'utf8').split('\n')[0].trim(); } catch { /* retry */ } }
  }
  if (!port) { proc.kill(); throw new Error('Chrome did not open a debugging port'); }
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const target = targets.find(t => t.type === 'page');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  let id = 0;
  const pending = new Map(), listeners = new Set();
  ws.onmessage = ev => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { res, rej } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? rej(new Error(msg.error.message)) : res(msg.result);
    } else listeners.forEach(fn => fn(msg));
  };
  const send = (method, params = {}) => new Promise((res, rej) => {
    const i = ++id;
    pending.set(i, { res, rej });
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  const waitFor = (method, timeout = 20000) => new Promise(res => {
    const fn = msg => { if (msg.method === method) { listeners.delete(fn); clearTimeout(t); res(msg.params); } };
    const t = setTimeout(() => { listeners.delete(fn); res(null); }, timeout);
    listeners.add(fn);
  });
  const close = () => {
    try { ws.close(); } catch {}
    proc.kill();
    setTimeout(() => { try { rmSync(profile, { recursive: true, force: true }); } catch {} }, 500);
  };
  const on = fn => { listeners.add(fn); return () => listeners.delete(fn); };
  return { send, waitFor, on, close };
}

// ------------------------------------------------------------------ GSAP motion pass
// Only for pages that load GSAP (site_config.GSAP). The main pass emulates reduced motion, so GSAP never
// runs there; this pass reloads with motion on and checks the live tweens, then scrolls the whole page.
// Serialised into the page; must be self-contained.
async function motionChecks() {
  const errors = [], warnings = [];
  const wait = ms => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, ms))));
  const label = el => `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}${el.classList.length ? '.' + [...el.classList].slice(0, 2).join('.') : ''} "${(el.textContent || el.getAttribute('alt') || '').trim().replace(/\s+/g, ' ').slice(0, 30)}"`;
  const hidden = el => { const cs = getComputedStyle(el); return +cs.opacity < 0.05 || cs.visibility === 'hidden'; };
  await wait(150);

  // LCP: the hero headline and the hero image must be visible at load, not waiting on an animation
  const h1 = document.querySelector('h1');
  const lcpImg = document.querySelector('img[fetchpriority="high"]');
  for (const el of [h1, ...(h1 ? h1.querySelectorAll('*') : []), lcpImg].filter(Boolean)) {
    if (el.getBoundingClientRect().top < innerHeight && +getComputedStyle(el).opacity < 0.5) {
      warnings.push(`hero ${label(el)} is hidden at load (opacity ${(+getComputedStyle(el).opacity).toFixed(2)}): an entrance animation delays LCP; animate below the fold instead`);
      break;
    }
  }

  // Live tweens, read before scrolling (finished tweens leave the global timeline)
  const OK = new Set(['x', 'y', 'z', 'xPercent', 'yPercent', 'scale', 'scaleX', 'scaleY', 'rotation', 'rotate',
    'rotationX', 'rotationY', 'rotateX', 'rotateY', 'skewX', 'skewY', 'opacity', 'autoAlpha', 'transformOrigin',
    'force3D', 'drawSVG', 'motionPath', 'morphSVG', 'svgOrigin', 'smoothOrigin',
    'duration', 'delay', 'ease', 'stagger', 'repeat', 'repeatDelay', 'yoyo', 'yoyoEase', 'scrollTrigger', 'paused',
    'reversed', 'immediateRender', 'overwrite', 'lazy', 'id', 'data', 'inherit', 'keyframes', 'startAt',
    'runBackwards', 'callbackScope', 'clearProps', 'parent', 'onStart', 'onUpdate', 'onComplete', 'onRepeat',
    'onReverseComplete', 'onInterrupt', 'onStartParams', 'onUpdateParams', 'onCompleteParams']);
  const tweens = window.gsap ? gsap.globalTimeline.getChildren(true, true, false) : [];
  const targets = new Set(), clash = new Set(), props = new Map(), eased = new Set();
  // A CSS transition on a property GSAP sets every frame makes the tween lag and stutter
  const transitions = el => {
    const cs = getComputedStyle(el);
    const durs = cs.transitionDuration.split(',').map(parseFloat);
    return cs.transitionProperty.split(',').some((p, i) =>
      /^(all|transform|opacity|translate|scale|rotate)$/.test(p.trim()) && (durs[i % durs.length] || 0) > 0);
  };
  for (const tw of tweens) {
    const els = tw.targets().filter(t => t instanceof Element);
    if (!els.length) continue;
    const bad = Object.keys(tw.vars).filter(k => !k.startsWith('_') && !k.startsWith('--') && !OK.has(k));
    for (const el of els) {
      targets.add(el);
      // .reveal is main.js's unless motion.js took the reveals over (.gsap-motion on <html>)
      const mainOwnsReveal = !document.documentElement.classList.contains('gsap-motion');
      if (el.matches(mainOwnsReveal ? '.reveal, [data-parallax]' : '[data-parallax]')) clash.add(el);
      else if (transitions(el)) eased.add(el);
      if (bad.length) props.set(label(el), bad);
    }
  }
  if (clash.size) errors.push(`GSAP tweens ${clash.size} element(s) that main.js already moves (.reveal / data-parallax): ` +
    `${[...clash].slice(0, 3).map(label).join('; ')}: animate a child or wrapper instead`);
  if (eased.size) warnings.push(`GSAP tweens ${eased.size} element(s) with a CSS transition on transform/opacity: ` +
    `${[...eased].slice(0, 3).map(label).join('; ')}: remove the CSS transition (all animation runs in JavaScript)`);
  for (const [el, bad] of [...props].slice(0, 5)) warnings.push(`GSAP tweens ${bad.join(', ')} on ${el}: use transform and opacity only`);

  // Trigger starts must match the layout. ScrollTriggers refresh in creation order; one created before a pin
  // above it ignores the pin's scroll length and fires that much early (Gadget Zone: dividers below the pinned
  // bench drew 900px early, off-screen). Simple "edge edge" starts only; small gaps are transforms (L-050).
  if (window.ScrollTrigger) {
    const EDGE = /^(top|center|bottom|-?\d+(\.\d+)?(%|px)?)$/;
    const at = (tok, size) => tok === 'top' ? 0 : tok === 'center' ? size / 2 : tok === 'bottom' ? size
      : tok.endsWith('%') ? parseFloat(tok) / 100 * size : parseFloat(tok);
    const off = [];
    for (const st of ScrollTrigger.getAll()) {
      const el = st.trigger, start = st.vars.start;
      if (!el || typeof start !== 'string' || st.vars.containerAnimation || !el.getClientRects().length) continue;
      const [tp, vp] = start.trim().split(/\s+/);
      if (!EDGE.test(tp || '') || !EDGE.test(vp || '')) continue;
      const r = el.getBoundingClientRect();
      const expected = r.top + scrollY + at(tp, r.height) - at(vp, innerHeight);
      if (Math.abs(st.start - expected) > Math.max(60, innerHeight * 0.08)) off.push(`${label(el)} '${start}' at ${Math.round(st.start)}px, layout says ${Math.round(expected)}px`);
    }
    if (off.length) errors.push(`${off.length} ScrollTrigger start(s) disagree with the layout: ${off.slice(0, 3).join('; ')}: ` +
      `triggers created out of page order miss a pin's scroll length; sort them in page order before each refresh ` +
      `(ScrollTrigger.addEventListener('refreshInit', () => ScrollTrigger.sort()))`);
  }

  // Scroll the whole page: pins and horizontal tracks must never widen it
  const vw = document.documentElement.clientWidth;
  let overflowAt = null;
  for (let y = 0, i = 0; i < 300; i++) {
    window.scrollTo(0, y);
    await wait(40);
    if (overflowAt === null && document.documentElement.scrollWidth > vw + 1) overflowAt = Math.round(scrollY);
    if (y >= document.documentElement.scrollHeight - innerHeight) break;
    y += Math.round(innerHeight * 0.6);
  }
  if (overflowAt !== null) errors.push(`horizontal overflow during scroll animations at ${vw}px (scrollY ${overflowAt}): ` +
    `page is ${document.documentElement.scrollWidth}px wide; clip the pinned section (overflow: hidden)`);

  // After the whole page has scrolled past, nothing in <main> should still be invisible. Entrance moments
  // replay (reset once off-screen), so a hidden target is brought back into view and judged there.
  await wait(1500);
  let stuck = [...targets].filter(el => el.isConnected && el.closest('main') && hidden(el));
  for (const el of stuck.slice(0, 40)) {
    el.scrollIntoView({ block: 'center' });
    await wait(1200);
    if (!hidden(el)) stuck = stuck.filter(s => s !== el);
  }
  if (stuck.length) warnings.push(`${stuck.length} GSAP target(s) still invisible after scrolling the whole page: ` +
    `${stuck.slice(0, 3).map(label).join('; ')}: content must not depend on an animation finishing`);
  window.scrollTo(0, 0);
  return { errors, warnings };
}

async function evaluate(send, expression) {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result.value;
}

// ------------------------------------------------------------------ main
async function main() {
  if (!existsSync(DIST)) { console.error('dist/ not found: run `python _src/build.py` first'); process.exit(2); }
  const flags = process.argv.slice(2).filter(a => a.startsWith('--'));
  const requested = process.argv.slice(2).filter(a => !a.startsWith('--')).map(p => p.replace(/^dist[\\/]/, ''));
  const pages = (requested.length ? requested : readdirSync(DIST).filter(f => f.endsWith('.html')))
    .sort((a, b) => (a !== 'index.html') - (b !== 'index.html') || a.localeCompare(b));
  mkdirSync(SHOTS, { recursive: true });

  const { send, waitFor, on, close } = await launch();
  const results = [];
  // Uncaught page errors: one throw in motion.js silently stopped every GSAP moment on the page (2026-10,
  // an onUpdate arrow read its tween before the const was assigned). Collected per load, reported as errors.
  let jsErrors = [];
  on(msg => {
    // A navigation clears the old page's contexts: anything it threw late belongs to the page before
    if (msg.method === 'Runtime.executionContextsCleared') jsErrors = [];
    if (msg.method !== 'Runtime.exceptionThrown') return;
    const d = msg.params.exceptionDetails;
    const where = d.url ? ` (${d.url.split('/').pop()}:${d.lineNumber + 1})` : '';
    jsErrors.push(`uncaught JavaScript error${where}: ${(d.exception?.description || d.text).split('\n')[0]}`);
  });
  const takeJsErrors = () => { const e = [...new Set(jsErrors)]; jsErrors = []; return e; };
  try {
    await send('Page.enable');
    await send('Runtime.enable');
    await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    for (const page of pages) {
      const file = join(DIST, page);
      if (!existsSync(file)) { results.push({ page, vp: '-', errors: [`not found: dist/${page}`], warnings: [] }); continue; }
      const slug = page.replace(/\.html$/, '');
      const axeSeen = new Set();
      for (const vp of VIEWPORTS) {
        await send('Emulation.setDeviceMetricsOverride', { width: vp.width, height: vp.height, deviceScaleFactor: 1, mobile: vp.mobile });
        const loaded = waitFor('Page.loadEventFired');
        takeJsErrors();
        await send('Page.navigate', { url: pathToFileURL(file).href });
        await loaded;
        await evaluate(send, 'document.fonts.ready.then(() => true)');
        // loading="lazy" images never load in a synchronous scroll or a beyond-viewport capture:
        // load them all first, or -full.png shows empty frames (Trevor Travis Motors, 2026-10)
        await evaluate(send, `Promise.all([...document.images].map(i => {
          if (i.loading === 'lazy') { i.removeAttribute('loading'); const s = i.src; i.src = ''; i.src = s; }
          return i.decode().catch(() => 0); })).then(() => true)`);
        await sleep(250);
        const ax = await axeChecks(send, axeSeen);  // before the layout checks, which scroll and restyle
        const r = await evaluate(send, `(${pageChecks.toString()})(${JSON.stringify(vp)})`);
        const px = await pixelContrast(send);
        r.errors.push(...px.errors, ...ax.errors, ...takeJsErrors());
        r.warnings.push(...px.warnings, ...ax.warnings);
        results.push({ page, vp: vp.name, ...r });
        if (vp.shots) {
          await evaluate(send, 'window.scrollTo(0, 0), true');
          await sleep(100);
          const fold = await send('Page.captureScreenshot', { format: 'png' });
          writeFileSync(join(SHOTS, `${slug}-${vp.name}-fold.png`), Buffer.from(fold.data, 'base64'));
          const { cssContentSize } = await send('Page.getLayoutMetrics');
          const height = Math.min(Math.ceil(cssContentSize.height), 16000);
          const full = await send('Page.captureScreenshot', {
            format: 'png', captureBeyondViewport: true,
            clip: { x: 0, y: 0, width: vp.width, height, scale: 1 },
          });
          writeFileSync(join(SHOTS, `${slug}-${vp.name}-full.png`), Buffer.from(full.data, 'base64'));
        }
        // GSAP pages: reload with motion on and check the live animations (screenshots stay reduced-motion)
        if (vp.shots && await evaluate(send, '!!window.gsap')) {
          await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
          try {
            const again = waitFor('Page.loadEventFired');
            takeJsErrors();
            await send('Page.navigate', { url: pathToFileURL(file).href });
            await again;
            await evaluate(send, 'document.fonts.ready.then(() => true)');
            const m = await evaluate(send, `(${motionChecks.toString()})()`);
            m.errors.push(...takeJsErrors());
            results.push({ page, vp: `${vp.name} motion on`, ...m });
          } finally {
            await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
          }
        }
      }
    }
  } finally {
    close();
  }
  // after close(): Lighthouse launches its own Chrome, and two at once collide
  if (!flags.includes('--no-lighthouse')) {
    results.push(...await lighthouse(pages.filter(p => p !== '404.html' && existsSync(join(DIST, p))), CHROME));
  }

  const nErr = results.reduce((n, r) => n + r.errors.length, 0);
  const nWarn = results.reduce((n, r) => n + r.warnings.length, 0);
  const lines = [`# Browser QA: ${pages.length} pages × ${VIEWPORTS.map(v => v.name).join('/')}`, '',
    `**${nErr} errors · ${nWarn} warnings**. Screenshots: qa/shots/. Text over photos/gradients and every single-colour SVG are measured against on-screen pixels (estimates); still judge busy photos in the screenshots.`, '',
    ...scoreTable(results)];
  for (const r of results) {
    if (!r.errors.length && !r.warnings.length) continue;
    lines.push(`## ${r.page} @ ${r.vp}`, '');
    r.errors.forEach(e => lines.push(`- ERROR ${e}`));
    r.warnings.forEach(w => lines.push(`- warn ${w}`));
    lines.push('');
  }
  if (!nErr && !nWarn) lines.push('All checks passed.');
  writeFileSync(join(OUT, 'browser-report.md'), lines.join('\n') + '\n');
  console.log(`browser qa: ${nErr} errors, ${nWarn} warnings -> qa/browser-report.md`);
  process.exit(nErr ? 1 : 0);
}

main().catch(err => { console.error(err); process.exit(2); });
