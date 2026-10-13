"""Deploy the portfolio itself: public and indexable (unlike tools/deploy.py, which only ships noindex previews).

    python tools/deploy_live.py

Builds, refuses if dist/ carries a noindex header or source folders, deploys dist/ to the Cloudflare Pages
project PROJECT (production branch), then checks the live URL returns 200 without X-Robots-Tag: noindex.

Classic Pages, not a Worker: a Worker would live at <name>.ebanigon-previews.workers.dev (the account's
preview subdomain); Pages gives <project>.pages.dev. The project was created once with
`wrangler pages project create ernestbanigon --production-branch main --force` (2026-10: without --force,
wrangler delegates to Workers autoconfig, which fails). Deploys need no --force.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy import DIST, ROOT, check, refuse_stale_cache, save_state, wrangler  # noqa: E402

PROJECT = "ernestbanigon"
URL = f"https://{PROJECT}.pages.dev"  # matches DOMAIN in _src/site_config.py
ACCOUNT_ID = "845cef37a389385cd395241e0970759e"  # Banigon40@gmail.com's Account


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("CLOUDFLARE_ACCOUNT_ID", ACCOUNT_ID)
    subprocess.run([sys.executable, str(ROOT / "_src" / "build.py")], check=True)
    headers = DIST / "_headers"
    if headers.exists() and "noindex" in headers.read_text(encoding="utf-8").lower():
        sys.exit("dist/_headers has noindex: this script ships the public site; fix _headers first")
    leaked = [p.name for p in DIST.iterdir() if p.name in ("_src", "tools", "client-assets", "qa", ".pipeline")]
    if leaked:
        sys.exit(f"source folders in dist/: {leaked}")
    refuse_stale_cache(URL)  # /assets/img/* is cached for a week: changed images need a new name

    who = wrangler("whoami")
    if "You are logged in" not in who.stdout + who.stderr:
        sys.exit("Wrangler is not logged in to Cloudflare. Ask the user to run:  ! npx wrangler login")

    res = wrangler("pages", "deploy", str(DIST), "--project-name", PROJECT, "--branch", "main",
                   "--commit-dirty=true", "--commit-message", "portfolio")
    out = res.stdout + res.stderr
    if res.returncode != 0:
        sys.exit(f"deploy failed:\n{out[-2500:]}")
    m = re.search(r"https://[a-z0-9]+\." + re.escape(PROJECT) + r"\.pages\.dev", out)
    save_state(ROOT / ".pipeline" / "cloudflare-live.json",
               {"project": PROJECT, "url": URL, "last_deploy": m.group(0) if m else None})
    print(f"deployed: {URL}" + (f"  (this deploy: {m.group(0)})" if m else ""))

    # A brand-new *.pages.dev name answers 522 (or not at all) for a minute or so.
    for _ in range(12):
        code, robots = check(URL)
        if code and code < 500:
            break
        time.sleep(10)
    if code != 200:
        sys.exit(f"! public check returned {code or 'no response'}")
    if "noindex" in robots.lower():
        sys.exit("! live site sends X-Robots-Tag: noindex; search engines would skip it")
    print("public access OK (200), indexable")


if __name__ == "__main__":
    main()
