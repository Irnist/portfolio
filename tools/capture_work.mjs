// Screenshots of the concept sites for the portfolio cards. Headless Chrome over CDP, no npm packages.
//
//   node tools/capture_work.mjs              all concept sites
//   node tools/capture_work.mjs gadget-zone  just these slugs
//
// For each site: <slug>-desktop.png (1440 wide, top 3600px of the page) and <slug>-phone.png
// (390x844 fold at 2x). Raw PNGs land in client-assets/shots/; tools/prep_images.py turns them
// into the webp files the page uses. One browser, one page at a time (parallel Chrome instances collide).
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'client-assets', 'shots');
const CONCEPTS = join(ROOT, '..', 'Concept Websites'); // sibling folder holding the sample sites
const SITES = [
  { slug: 'gadget-zone', file: `${CONCEPTS}/Gadget Zone Website/dist/index.html` },
  { slug: 'ironcity', file: `${CONCEPTS}/Iron City Website/index.html` },
  { slug: 'trevor-travis', file: `${CONCEPTS}/Trevor Travis Motors Website/dist/index.html` },
  { slug: 'macz', file: `${CONCEPTS}/Macz Arkitektura Website/dist/index.html` },
  { slug: 'ironwood', file: `${CONCEPTS}/HVAC Website/index.html` },
  { slug: 'weknz', file: `${CONCEPTS}/Weknz Patio Furniture/index.html` },
];
const MAX_H = 3600;
const CHROME = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(p => p && existsSync(p));
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function launch() {
  const profile = mkdtempSync(join(tmpdir(), 'site-shots-'));
  const proc = spawn(CHROME, [
    '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', '--disable-gpu',
    '--disable-extensions', '--force-color-profile=srgb', 'about:blank',
  ], { stdio: 'ignore' });
  const portFile = join(profile, 'DevToolsActivePort');
  let port;
  for (let i = 0; i < 150 && !port; i++) {
    await sleep(100);
    // Windows: Chrome may still hold the file open (EBUSY) on the first poll; try again next tick (L-045)
    if (existsSync(portFile)) { try { port = readFileSync(portFile, 'utf8').split('\n')[0].trim(); } catch { /* retry */ } }
  }
  if (!port) { proc.kill(); throw new Error('Chrome did not open a debugging port'); }
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
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
  return { send, waitFor, close };
}

const evaluate = async (send, expression) =>
  (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result?.value;

// Load every image eagerly and wait for fonts, so beyond-the-fold shots aren't empty plates (L-020).
const SETTLE = `(async () => {
  for (const i of document.images) if (i.loading === 'lazy') { i.removeAttribute('loading'); const s = i.src; i.src = ''; i.src = s; }
  await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
  await document.fonts.ready;
  return document.documentElement.scrollHeight;
})()`;

// `node tools/capture_work.mjs og` renders client-assets/og.html to public/og-image.png instead.
async function og() {
  const { send, waitFor, close } = await launch();
  try {
    await send('Page.enable');
    await send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 630, deviceScaleFactor: 1, mobile: false });
    const loaded = waitFor('Page.loadEventFired');
    await send('Page.navigate', { url: pathToFileURL(join(ROOT, 'client-assets', 'og.html')).href });
    await loaded;
    await evaluate(send, SETTLE);
    await sleep(500);
    const shot = await send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(join(ROOT, 'public', 'og-image.png'), Buffer.from(shot.data, 'base64'));
    console.log('public/og-image.png  1200x630');
  } finally { close(); }
}

// `node tools/capture_work.mjs live <url> <out.png>`: recapture a live client site at 1280 wide, 2x,
// top 3200 CSS px. Scrolls the whole page first so scroll-reveal sections and lazy images finish,
// forces common reveal classes visible, and hides floating widgets (chat popups, cookie bars) so
// they aren't baked into the shot (Children Matter, 2026-10-08).
const REVEAL = `(async () => {
  const step = innerHeight * 0.6;
  for (let y = 0; y < document.documentElement.scrollHeight; y += step) { scrollTo(0, y); await new Promise(r => setTimeout(r, 250)); }
  await new Promise(r => setTimeout(r, 1500));
  const s = document.createElement('style');
  s.textContent = '.elementor-invisible{visibility:visible!important}[data-aos]{opacity:1!important;transform:none!important}' +
    '.animated,.elementor-element{animation:none!important}';
  document.head.append(s);
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if ((cs.position === 'fixed' || cs.position === 'sticky') && el.getBoundingClientRect().top > 120) el.style.setProperty('display', 'none', 'important');
  }
  scrollTo(0, 0);
  await new Promise(r => setTimeout(r, 800));
  return document.documentElement.scrollHeight;
})()`;

async function live(url, out) {
  const { send, waitFor, close } = await launch();
  try {
    await send('Page.enable');
    await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 800, deviceScaleFactor: 2, mobile: false });
    const loaded = waitFor('Page.loadEventFired', 45000);
    await send('Page.navigate', { url });
    await loaded;
    await sleep(2500);
    await evaluate(send, REVEAL);
    const full = await evaluate(send, SETTLE);
    const h = Math.min(full, 3200);
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: 1280, height: h, scale: 1 } });
    writeFileSync(out, Buffer.from(shot.data, 'base64'));
    console.log(`${out}  1280x${h} @2x`);
  } finally { close(); }
}

async function main() {
  if (process.argv[2] === 'og') return og();
  if (process.argv[2] === 'live') return live(process.argv[3], process.argv[4]);
  mkdirSync(OUT, { recursive: true });
  const { send, waitFor, close } = await launch();
  try {
    await send('Page.enable');
    await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    // `node tools/capture_work.mjs <slug> ...` recaptures only those sites. Re-shooting the others would
    // change their long-cached webp files under the same URL, which deploy refuses (L-037).
    const only = process.argv.slice(2);
    for (const site of only.length ? SITES.filter(s => only.includes(s.slug)) : SITES) {
      if (!existsSync(site.file)) { console.log(`! missing ${site.file}`); continue; }
      for (const vp of [{ w: 1440, h: 900, dpr: 1, mobile: false, tag: 'desktop' },
                        { w: 390, h: 844, dpr: 2, mobile: true, tag: 'phone' }]) {
        await send('Emulation.setDeviceMetricsOverride', { width: vp.w, height: vp.h, deviceScaleFactor: vp.dpr, mobile: vp.mobile });
        const loaded = waitFor('Page.loadEventFired');
        await send('Page.navigate', { url: pathToFileURL(site.file).href });
        await loaded;
        const full = await evaluate(send, SETTLE);
        await sleep(600);
        const h = vp.tag === 'desktop' ? Math.min(full, MAX_H) : vp.h;
        const shot = await send('Page.captureScreenshot', {
          format: 'png', captureBeyondViewport: vp.tag === 'desktop',
          clip: { x: 0, y: 0, width: vp.w, height: h, scale: 1 },
        });
        writeFileSync(join(OUT, `${site.slug}-${vp.tag}.png`), Buffer.from(shot.data, 'base64'));
        console.log(`${site.slug}-${vp.tag}.png  ${vp.w}x${h}`);
      }
    }
  } finally { close(); }
}
main();
