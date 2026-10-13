"""Deploy dist/ as a noindex preview (Netlify or Cloudflare) and verify it's publicly reachable.

    python tools/deploy.py                      # host from BRIEF.md "Deploy host:" (default cloudflare)
    python tools/deploy.py --host cloudflare    # or --host netlify

Rebuilds first, refuses to deploy without the noindex _headers file or with source
folders in dist/, creates the site/Worker on the first run (kept in
.pipeline/netlify.json or .pipeline/cloudflare.json), then checks the live URL returns
200 with X-Robots-Tag: noindex. Cloudflare deploys a static-assets Worker (<name>.<account>.workers.dev),
which is what Cloudflare Pages became.
Not logged in? Run once:  npx netlify-cli login   |   npx wrangler login
Cloudflare with several accounts: set CLOUDFLARE_ACCOUNT_ID (wrangler can't pick one non-interactively).
"""
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
NPX = shutil.which("npx") or "npx"
HOSTS = ("netlify", "cloudflare")


def npx(pkg, *args):
    env = {**os.environ, "WRANGLER_SEND_METRICS": "false"}
    return subprocess.run([NPX, "-y", pkg, *args], cwd=ROOT, capture_output=True, env=env,
                          text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)


def netlify(*args):
    return npx("netlify-cli", *args)


def wrangler(*args):
    return npx("wrangler", *args)


def pick_host():
    if "--host" in sys.argv:
        i = sys.argv.index("--host")
        host = sys.argv[i + 1].lower() if i + 1 < len(sys.argv) else ""
    else:
        brief = ROOT / "BRIEF.md"
        m = re.search(r"^Deploy host:[ \t]*([A-Za-z]*)", brief.read_text(encoding="utf-8"), re.M) if brief.exists() else None
        # Default is cloudflare, but a site already previewed on Netlify stays there so its URL doesn't move.
        default = "netlify" if (ROOT / ".pipeline" / "netlify.json").exists() else "cloudflare"
        host = (m.group(1).lower() if m else "") or default
    host = {"cf": "cloudflare", "pages": "cloudflare", "cloudflare-pages": "cloudflare"}.get(host, host)
    if host not in HOSTS:
        sys.exit(f"unknown deploy host {host!r}; use one of {HOSTS}")
    return host


def preview_name():
    return re.sub(r"[^a-z0-9]+", "-", ROOT.name.lower()).strip("-")[:40] + "-preview"


def retry_name(name):
    return name.rsplit("-x", 1)[0] + "-x" + "".join(random.choices(string.ascii_lowercase + string.digits, k=4))


def archived_state(path):
    """A redesign archives the old site, .pipeline/ included, to <workspace>/_temp/<Name>-previous-<date>/. Without
    its state the next deploy made a second Worker (`…-preview-xmcon`) and the shared preview URL kept the old
    design (Macz, L-061). Reuse the newest archived state so a redesign deploys over the same preview."""
    temp = next((p / "_temp" for p in ROOT.parents if (p / "_temp").is_dir()), None)
    if temp is None:
        return {}
    stem = ROOT.name.removesuffix(" Website")
    found = sorted(temp.glob(f"{stem}*-previous-*/.pipeline/{path.name}"), key=lambda p: p.stat().st_mtime)
    if not found:
        return {}
    print(f"reusing the archived preview state {found[-1].relative_to(temp.parent)} so the URL stays the same")
    return json.loads(found[-1].read_text(encoding="utf-8"))


def load_state(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else archived_state(path)


def save_state(path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def check_netlify_forms(site_id):
    """FORM_ENDPOINT = "netlify": confirm Netlify registered the form(s) in the deployed HTML. Form detection can be
    off on a site, and then submissions vanish without an error."""
    wanted = sorted({m for f in DIST.glob("*.html")
                     for m in re.findall(r'<form[^>]*\bname="([^"]+)"[^>]*data-netlify="true"', f.read_text(encoding="utf-8"))})
    if not wanted or not site_id:
        return
    res = netlify("api", "listSiteForms", "--data", json.dumps({"site_id": site_id}))
    try:
        found = {f.get("name") for f in json.loads(res.stdout[res.stdout.find("["):res.stdout.rfind("]") + 1])}
    except ValueError:
        print(f"! couldn't list Netlify forms to check {wanted}:\n{(res.stderr or res.stdout)[-400:]}")
        return
    missing = [n for n in wanted if n not in found]
    if missing:
        print(f"! Netlify hasn't registered form(s) {missing}: turn on form detection (Site configuration → Forms → "
              "Enable form detection), then run deploy.py again. Until then submissions are lost.")
    else:
        print(f"Netlify forms registered: {wanted}. Set the email alert: Site configuration → Forms → Form notifications.")


def deploy_netlify():
    """Returns (url, fix_401) where fix_401() tries to lift visitor protection and returns True on success."""
    state_file = ROOT / ".pipeline" / "netlify.json"
    status = netlify("status")
    # An unlinked folder also exits 1 ("not linked to a project"); only a missing user means logged out
    # (Trevor Travis Motors, 2026-10).
    if "Not logged in" in status.stdout + status.stderr or "Email:" not in status.stdout:
        sys.exit("Netlify CLI is not logged in. Ask the user to run:  ! npx netlify-cli login")

    state = load_state(state_file)
    base = ["deploy", "--dir", "dist", "--prod", "--no-build", "--json", "--message", "pipeline preview"]
    if state.get("site_id"):
        res = netlify(*base, "--site", state["site_id"])
    else:
        name = preview_name()
        for attempt in range(3):
            res = netlify(*base, "--site-name", name)
            if res.returncode == 0:
                break
            name = retry_name(name)
    if res.returncode != 0:
        sys.exit(f"deploy failed:\n{res.stdout[-1500:]}\n{res.stderr[-1500:]}")

    out = res.stdout
    data = json.loads(out[out.find("{"):out.rfind("}") + 1])
    url = data.get("url") or data.get("deploy_url")
    save_state(state_file, {"site_id": data.get("site_id"), "site_name": data.get("site_name"), "url": url})
    check_netlify_forms(data.get("site_id"))

    def fix_401():
        if not data.get("site_id"):
            return False
        # Team login (sso_login) on a preview site this tool created: the brief authorised a public
        # noindex preview, so switch it off for this site only and re-check. Seen twice (IronCity, Trevor Travis).
        res = netlify("api", "updateSite", "--data",
                      json.dumps({"site_id": data["site_id"], "body": {"sso_login": False}}))
        print("401: team login was on; switched it off for this preview site" if res.returncode == 0
              else f"401: could not switch off team login:\n{res.stderr[-600:]}")
        return res.returncode == 0

    return url, fix_401, ("Turn it off in Netlify: Site configuration → Access & security → "
                          "Visitor access (team login / password).")


def deploy_cloudflare():
    """Cloudflare Pages is now part of Workers: wrangler 4.14x delegates `pages project create` to Workers
    autoconfig, which derives an invalid name from the folder (2026-10). So deploy dist/ as a Worker with
    static assets from a config we write ourselves; that serves _headers the same way Pages did."""
    state_file = ROOT / ".pipeline" / "cloudflare.json"
    config = ROOT / ".pipeline" / "wrangler.jsonc"
    who = wrangler("whoami")
    if "You are logged in" not in who.stdout + who.stderr:
        sys.exit("Wrangler is not logged in to Cloudflare. Ask the user to run:  ! npx wrangler login")

    state = load_state(state_file)
    name = state.get("worker_name")
    if not name:
        # Worker names are per account: never deploy over a Worker this tool didn't create.
        name = preview_name()
        for attempt in range(4):
            if wrangler("deployments", "list", "--name", name, "--json").returncode != 0:
                break
            name = retry_name(name)
        else:
            sys.exit("could not find a free Worker name for the preview")

    config.parent.mkdir(exist_ok=True)
    config.write_text(json.dumps({"name": name, "compatibility_date": "2026-09-01", "workers_dev": True,
                                  "preview_urls": False, "assets": {"directory": "../dist"}}, indent=2),
                      encoding="utf-8")
    res = wrangler("deploy", "--config", str(config), "--message", "pipeline preview")
    if res.returncode != 0:
        sys.exit(f"deploy failed:\n{res.stdout[-1500:]}\n{res.stderr[-1500:]}")

    m = re.search(r"https://[a-z0-9.-]+\.workers\.dev", res.stdout + res.stderr)
    if not m:
        sys.exit(f"deployed, but no *.workers.dev URL in wrangler's output (is a workers.dev subdomain "
                 f"registered on the account?):\n{res.stdout[-1500:]}")
    url = m.group(0)
    if "register a workers.dev subdomain" in res.stdout + res.stderr:
        # First Workers deploy on the account: wrangler registered the account-wide subdomain itself, named
        # after this folder (2026-10: "revor--ravis--otors--ebsite"). Flag it so the user can rename it.
        print(f"! wrangler auto-registered this account's workers.dev subdomain ({url.split('.', 1)[1]}). "
              "Ask the user whether to rename it: Cloudflare dashboard → Workers & Pages → Settings → Subdomain.")
    save_state(state_file, {"worker_name": name, "url": url})
    return url, (lambda: False), ("Cloudflare Access is protecting the Worker. Remove it in the dashboard: "
                                  "Workers & Pages → the Worker → Settings → Domains & Routes.")


def check(url):
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0 (pipeline deploy check)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            if "cloudflareaccess.com" in r.geturl():  # Access redirects to its login page (200), not a 401
                return 401, ""
            return r.status, r.headers.get("X-Robots-Tag", "")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("X-Robots-Tag", "")
    except (urllib.error.URLError, OSError):
        return 0, ""  # DNS/TLS not ready yet (a fresh *.workers.dev name can take a minute or two)


def long_cached_prefixes():
    """URL prefixes that dist/_headers caches for longer than zero seconds (e.g. "/assets/img/")."""
    headers = DIST / "_headers"
    prefixes, current = [], None
    for line in (headers.read_text(encoding="utf-8").splitlines() if headers.exists() else []):
        if line.startswith("/"):
            current = line.strip().rstrip("*")
        elif current and (m := re.search(r"max-age=(\d+)", line)) and int(m.group(1)) > 0:
            prefixes.append(current)
    return prefixes


def stale_cached_files(live_url):
    """Long-cached files whose content changed while their URL stayed the same. A visitor who already has the
    old copy keeps seeing it until it expires (portfolio 2026-10: the user's desktop showed the old opaque
    headshot under the new cut-out's name for days). Fix by renaming the file. Returns [paths]."""
    stale = []
    for prefix in long_cached_prefixes():
        base = DIST / prefix.strip("/")
        for f in sorted(base.rglob("*") if base.is_dir() else []):
            if not f.is_file():
                continue
            path = "/" + f.relative_to(DIST).as_posix()
            try:
                req = urllib.request.Request(live_url.rstrip("/") + path, headers={"User-Agent": "deploy-check"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    if "text/html" in r.headers.get("Content-Type", ""):
                        continue  # fallback page, the file isn't live yet
                    if r.read() != f.read_bytes():
                        stale.append(path)
            except (urllib.error.URLError, OSError):
                continue  # not live yet (404) or unreachable: a new URL can't be stale
    return stale


def refuse_stale_cache(live_url):
    stale = stale_cached_files(live_url) if live_url else []
    if stale:
        sys.exit("these long-cached files changed content but kept their URL, so returning visitors would keep "
                 "the old copy; rename each (and its references), then rebuild:\n  " + "\n  ".join(stale))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp1252 consoles choke on arrows
    host = pick_host()
    subprocess.run([sys.executable, str(ROOT / "_src" / "build.py")], check=True)
    headers = DIST / "_headers"
    if not headers.exists() or "noindex" not in headers.read_text(encoding="utf-8"):
        sys.exit("dist/_headers with X-Robots-Tag: noindex is missing; refusing to deploy a preview")
    leaked = [p.name for p in DIST.iterdir() if p.name in ("_src", "tools", "client-assets", "qa", ".pipeline")]
    if leaked:
        sys.exit(f"source folders in dist/: {leaked}")
    refuse_stale_cache(load_state(ROOT / ".pipeline" / f"{host}.json").get("url"))

    url, fix_401, protection_hint = deploy_netlify() if host == "netlify" else deploy_cloudflare()
    print(f"deployed ({host}): {url}")

    # Public access + noindex check. Retry while a fresh subdomain is still propagating.
    deadline = time.time() + (180 if host == "cloudflare" else 30)
    code, robots = check(url)
    while code in (0, 404, 522, 525, 526) and time.time() < deadline:
        time.sleep(10)
        code, robots = check(url)
    if code == 401 and fix_401():
        code, robots = check(url)
    if code in (401, 403):
        print(f"! {code}: visitor protection is on. {protection_hint}")
        sys.exit(1)
    if code != 200:
        print(f"! public check returned {'no response' if code == 0 else f'HTTP {code}'}")
        sys.exit(1)
    if "noindex" not in robots.lower():
        print("! X-Robots-Tag noindex header not present on the live site")
        sys.exit(1)
    print("public access OK (200), X-Robots-Tag: noindex present")


if __name__ == "__main__":
    main()
