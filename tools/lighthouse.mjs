// Lighthouse (mobile, simulated slow 4G) over dist/, served locally the way the host serves it: gzip, plus the
// rules in dist/_headers, except X-Robots-Tag (a preview's noindex would otherwise sink every SEO score).
//
//   node tools/lighthouse.mjs                 every page in dist/
//   node tools/lighthouse.mjs index.html ...  just these pages
//
// browser_qa.mjs runs this at the end of every run (skip with --no-lighthouse). Lighthouse comes from
// `npx lighthouse@13` (downloaded once, then cached). Scores below the floors in FLOORS are errors or warnings;
// full results go to qa/lighthouse/<page>.json (open them at https://googlechrome.github.io/lighthouse/viewer/).
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DIST = join(ROOT, 'dist');
const OUT = join(ROOT, 'qa', 'lighthouse');
const LIGHTHOUSE = 'lighthouse@13';

// [error below, warning below] per category score (0-100)
export const FLOORS = {
  performance: [80, 90],
  accessibility: [90, 95],
  'best-practices': [70, 90],
  seo: [90, 100],
};
// Core Web Vitals (lab): [warning above, error above]
const VITALS = {
  'largest-contentful-paint': { label: 'LCP', unit: 's', scale: 1000, warn: 2500, error: 4000 },
  'cumulative-layout-shift': { label: 'CLS', unit: '', scale: 1, warn: 0.1, error: 0.25 },
  'total-blocking-time': { label: 'TBT', unit: 'ms', scale: 1, warn: 200, error: 600 },
};
// audits that only fail because the test runs on localhost
const LOCAL_ONLY = new Set(['canonical', 'is-on-https', 'redirects-http', 'uses-http2']);

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json', '.webmanifest': 'application/manifest+json',
  '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.avif': 'image/avif', '.gif': 'image/gif',
  '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.woff': 'font/woff', '.mp4': 'video/mp4', '.webm': 'video/webm',
  '.pdf': 'application/pdf',
};

function headerRules() {
  const file = join(DIST, '_headers');
  if (!existsSync(file)) return [];
  const rules = [];
  let rule = null;
  for (const line of readFileSync(file, 'utf8').split(/\r?\n/)) {
    if (!line.trim() || line.trim().startsWith('#')) continue;
    if (!/^\s/.test(line)) {
      const pattern = line.trim().replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*');
      rules.push(rule = { re: new RegExp(`^${pattern}$`), headers: [] });
    } else if (rule && line.includes(':')) {
      const i = line.indexOf(':');
      rule.headers.push([line.slice(0, i).trim(), line.slice(i + 1).trim()]);
    }
  }
  return rules;
}

function serve() {
  const rules = headerRules();
  const server = createServer((req, res) => {
    const path = decodeURIComponent(new URL(req.url, 'http://local').pathname);
    let file = join(DIST, path), status = 200;
    if (!file.startsWith(DIST + sep) && file !== DIST) { res.writeHead(403).end(); return; }
    if (existsSync(file) && statSync(file).isDirectory()) file = join(file, 'index.html');
    if (!existsSync(file)) {
      status = 404;
      file = join(DIST, '404.html');
      if (!existsSync(file)) { res.writeHead(404).end('not found'); return; }
    }
    const type = TYPES[extname(file).toLowerCase()] || 'application/octet-stream';
    const headers = { 'Content-Type': type };
    for (const r of rules) {
      if (!r.re.test(path)) continue;
      for (const [k, v] of r.headers) if (k.toLowerCase() !== 'x-robots-tag') headers[k] = v;
    }
    let body = readFileSync(file);
    if (/^(text\/|application\/(json|xml|manifest)|image\/svg)/.test(type) && /gzip/.test(req.headers['accept-encoding'] || '')) {
      body = gzipSync(body);
      headers['Content-Encoding'] = 'gzip';
    }
    res.writeHead(status, headers).end(body);
  });
  return new Promise(res => server.listen(0, '127.0.0.1', () => res(server)));
}

function run(url, chrome) {
  // one command string: npx is npx.cmd on most Windows installs, which needs a shell; no argument has spaces
  const cmd = ['npx', '-y', LIGHTHOUSE, url, '--output=json', '--quiet', '--chrome-flags=--headless=new',
    '--only-categories=performance,accessibility,best-practices,seo'].join(' ');
  return new Promise(res => {
    const proc = spawn(cmd, { shell: true, env: { ...process.env, ...(chrome ? { CHROME_PATH: chrome } : {}) } });
    const out = [], err = [];
    proc.stdout.on('data', d => out.push(d));
    proc.stderr.on('data', d => err.push(d));
    const timer = setTimeout(() => proc.kill(), 300000);
    proc.on('close', () => {
      clearTimeout(timer);
      // on Windows chrome-launcher can exit non-zero after the report (EPERM on its temp profile): trust the JSON
      try { res({ lhr: JSON.parse(Buffer.concat(out).toString('utf8')) }); }
      catch { res({ error: Buffer.concat(err).toString('utf8').trim().split('\n').slice(-3).join(' ') || 'no output' }); }
    });
  });
}

export function judge(lhr) {
  const errors = [], warnings = [];
  const scores = {};
  for (const [id, [errBelow, warnBelow]] of Object.entries(FLOORS)) {
    const cat = lhr.categories[id];
    if (!cat || cat.score === null) continue;
    const score = scores[id] = Math.round(cat.score * 100);
    const failed = cat.auditRefs
      .map(ref => ({ ref, a: lhr.audits[ref.id] }))
      .filter(({ ref, a }) => a && !LOCAL_ONLY.has(ref.id) && ref.group !== 'metrics' && a.score !== null && a.score < 0.9
        && ['binary', 'numeric', 'metricSavings'].includes(a.scoreDisplayMode))
      .sort((x, y) => (y.ref.weight || 0) - (x.ref.weight || 0) || x.a.score - y.a.score)
      .slice(0, 5)
      .map(({ a }) => a.title + (a.displayValue ? ` (${a.displayValue})` : ''));
    const msg = `Lighthouse ${cat.title} ${score} < ${score < errBelow ? errBelow : warnBelow}` + (failed.length ? `: ${failed.join('; ')}` : '');
    if (score < errBelow) errors.push(msg);
    else if (score < warnBelow) warnings.push(msg);
  }
  // Any colour-contrast failure is a defect, even when the accessibility score stays above its floor.
  // Lighthouse loads pages with motion ON (browser_qa's own contrast pass emulates reduced motion), so this is
  // what catches text held dim by an animation, e.g. GSAP steps waiting at opacity 0.3 (Gadget Zone, 2026-10-09).
  const contrast = lhr.audits['color-contrast'];
  if (contrast && contrast.score === 0) {
    const items = contrast.details?.items || [];
    const where = [...new Set(items.map(i => i.node?.selector).filter(Boolean))].slice(0, 3);
    const ratio = (items[0]?.node?.explanation || '').match(/contrast of ([\d.]+)/)?.[1];
    errors.push(`Lighthouse color-contrast fails on ${items.length} element(s)${ratio ? ` (e.g. ${ratio}:1)` : ''}: ${where.join('; ')}` +
      ' (Lighthouse runs with motion on: check animation start states such as dimmed text)');
  }
  const vitals = {};
  for (const [id, v] of Object.entries(VITALS)) {
    const value = lhr.audits[id]?.numericValue;
    if (value === undefined) continue;
    const shown = v.unit === 's' ? (value / 1000).toFixed(1) : v.unit === 'ms' ? Math.round(value) : value.toFixed(2);
    vitals[v.label] = `${shown}${v.unit}`;
    if (value > v.error) errors.push(`${v.label} ${vitals[v.label]} (mobile lab) > ${v.error / (v.unit === 's' ? 1000 : 1)}${v.unit}`);
    else if (value > v.warn) warnings.push(`${v.label} ${vitals[v.label]} (mobile lab) > ${v.warn / (v.unit === 's' ? 1000 : 1)}${v.unit}`);
  }
  return { scores, vitals, errors, warnings };
}

// -> [{ page, vp: 'lighthouse', scores, vitals, errors, warnings }]
export async function lighthouse(pages, chrome) {
  mkdirSync(OUT, { recursive: true });
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}/`;
  const results = [];
  try {
    for (const page of pages) {
      process.stdout.write(`lighthouse: ${page} ... `);
      const { lhr, error } = await run(base + encodeURI(page), chrome);
      if (!lhr) {
        console.log('failed');
        results.push({ page, vp: 'lighthouse', scores: {}, vitals: {}, errors: [], warnings: [`Lighthouse didn't run: ${error.slice(0, 300)}`] });
        continue;
      }
      writeFileSync(join(OUT, page.replace(/\.html$/, '') + '.json'), JSON.stringify(lhr));
      const r = judge(lhr);
      console.log(Object.entries(r.scores).map(([k, v]) => `${k} ${v}`).join(', '));
      results.push({ page, vp: 'lighthouse', ...r });
    }
  } finally {
    server.close();
  }
  return results;
}

export function scoreTable(results) {
  const cats = Object.keys(FLOORS);
  const rows = results.filter(r => r.vp === 'lighthouse' && Object.keys(r.scores).length);
  if (!rows.length) return [];
  return ['## Lighthouse (mobile, simulated slow 4G)', '',
    `| Page | ${cats.join(' | ')} | LCP | CLS | TBT |`, `|---|${cats.map(() => '---').join('|')}|---|---|---|`,
    ...rows.map(r => `| ${r.page} | ${cats.map(c => r.scores[c] ?? '–').join(' | ')} | ${r.vitals.LCP ?? '–'} | ${r.vitals.CLS ?? '–'} | ${r.vitals.TBT ?? '–'} |`),
    '', `Floors (error/warning below): ${cats.map(c => `${c} ${FLOORS[c].join('/')}`).join(', ')}. Scores vary a few points between runs.`, ''];
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (!existsSync(DIST)) { console.error('dist/ not found: run `python _src/build.py` first'); process.exit(2); }
  const requested = process.argv.slice(2).filter(a => !a.startsWith('--')).map(p => p.replace(/^dist[\\/]/, ''));
  const pages = requested.length ? requested : readdirSync(DIST).filter(f => f.endsWith('.html') && f !== '404.html');
  const results = await lighthouse(pages);
  const lines = ['# Lighthouse', '', ...scoreTable(results)];
  for (const r of results) {
    if (!r.errors.length && !r.warnings.length) continue;
    lines.push(`## ${r.page}`, '', ...r.errors.map(e => `- ERROR ${e}`), ...r.warnings.map(w => `- warn ${w}`), '');
  }
  writeFileSync(join(ROOT, 'qa', 'lighthouse-report.md'), lines.join('\n') + '\n');
  const nErr = results.reduce((n, r) => n + r.errors.length, 0);
  console.log(`lighthouse: ${nErr} errors -> qa/lighthouse-report.md`);
  process.exit(nErr ? 1 : 0);
}
