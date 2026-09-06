# Hosting on lotrlcg.app — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The tablet client is the front door at `https://lotrlcg.app/`, the Presto web twin lives at `/presto/`, `lotr.quest` redirects to `lotrlcg.app`, and every push to `main` publishes the same built `docs/` to both GitHub Pages (unchanged, `andrhamm.com/lotr-lcg-presto-hud/`) and a Cloudflare Pages project.

**Architecture:** No app code moves except two entry files and the service worker: `docs/index.html` becomes the tablet's entry (loading `tablet/js/app.js`), the twin's entry becomes `docs/presto/index.html` (loading `../js/main.js`), and `docs/tablet/sw.js` becomes `docs/sw.js` so its scope is the site root. Cloudflare Pages `_redirects` maps the old `/tablet/*` paths to `/*`. The existing `pages.yml` build job gains one wrangler step. The Cloudflare project, custom domains, DNS and the `lotr.quest` redirect rule are Task 2, done from the main session with an API token the user mints (the token in `~/.zshenv` today has DNS edit only).

**Decisions (user, 2026-09-06):** Cloudflare Pages; tablet at the root; `lotrlcg.app` canonical with `lotr.quest` redirecting; merge the tablet branch first, then deploy.

## Global Constraints

- Relative paths only in HTML and JS (`import.meta.url`-based `dataUrl`, `new URL("./", swUrl)` scope) — the same `docs/` serves under `/` on Cloudflare and under `/lotr-lcg-presto-hud/` on GitHub Pages.
- Storage keys stay prefixed (`lotr-hud-` twin, `lotr-tablet-` tablet) — both clients share one origin now on both hosts.
- `tests/test_no_stray_io.py`'s `fetch` allow-list names `docs/sw.js`; `tests/test_tablet_sw.py` loads the moved file and its fixture URLs drop the `/tablet/` segment; `python3 -m pytest tests/` green (2605 today).
- No secrets in the repo: the wrangler step reads `CLOUDFLARE_PAGES_TOKEN` from repo secrets and `CLOUDFLARE_ACCOUNT_ID` from a repo variable; the step is `continue-on-error: false` (a failed Cloudflare publish must show red) but placed AFTER the GitHub Pages artifact upload so the existing deploy is never blocked by it.
- Data policy unchanged: `docs/data/` stays gitignored and is built in CI for both targets in the one build job.

---

### Task 1: The site layout and the publish step

**Files:**
- Move: `docs/index.html` → `docs/presto/index.html` (script `../js/main.js`, stylesheet `../style.css`); `docs/tablet/index.html` → `docs/index.html` (stylesheet `tablet/style.css`, script `tablet/js/app.js`, title unchanged); `docs/tablet/sw.js` → `docs/sw.js`.
- Create: `docs/tablet/index.html` (a stub: `<meta http-equiv="refresh" content="0; url=../">` plus a link, for GitHub Pages where `_redirects` does not apply), `docs/_redirects` (`/tablet/* /:splat 301`), `docs/_headers` (`/sw.js` → `Cache-Control: no-cache`; `/data/*` → `Cache-Control: public, max-age=3600`).
- Modify: `docs/tablet/js/app.js` (registration: `new URL("../../sw.js", import.meta.url)`; the comment about the scope), `docs/sw.js` (`isShellOrData`: same-origin GET under the site directory — derive the directory from `self.location` the same way the registration does, matching `/tablet/`, `/js/`, `/data/`, `/presto/` and the root files; keep the image rule), `tests/test_tablet_sw.py` (path + fixture URLs), `tests/test_no_stray_io.py` (allow-list path), `tests/test_tablet.py` (any `/tablet/` assumption — line ~1178 asserts a data URL contains no `/tablet/`; keep), `.claude/launch.json` (`web-twin` opens the same port; add a `"url"`? no — the pane navigates; leave), `tools/devserver.py` (nothing unless it special-cases index), `.github/workflows/pages.yml` (after `upload-pages-artifact`: `- name: Publish to Cloudflare Pages` / `uses: cloudflare/wrangler-action@v3` with `apiToken: ${{ secrets.CLOUDFLARE_PAGES_TOKEN }}`, `accountId: ${{ vars.CLOUDFLARE_ACCOUNT_ID }}`, `command: pages deploy docs --project-name=lotrlcg --branch=main --commit-dirty=true`), `README.md` (the live URLs: `https://lotrlcg.app/` tablet, `https://lotrlcg.app/presto/` twin, the GitHub Pages mirror), `CLAUDE.md` (the "Web twin" bullet in the header and the "Card data" paragraph that names `docs/tablet/sw.js`).

- [ ] **Step 1: Failing tests** — `tests/test_site_layout.py` (new): `docs/index.html` loads `tablet/js/app.js` and `tablet/style.css`; `docs/presto/index.html` loads `../js/main.js` and `../style.css`; `docs/sw.js` exists and `docs/tablet/sw.js` does not; `docs/_redirects` has the `/tablet/*` line; `docs/tablet/index.html` refreshes to `../`; `pages.yml` contains `pages deploy docs --project-name=lotrlcg`. `tests/test_tablet_sw.py`: `isShellOrData` accepts `ORIGIN + "/js/app.js"`, `"/presto/index.html"`, `"/tablet/js/app.js"`, `"/data/index.json"` and rejects a foreign origin — under BOTH a root deployment (`location.href = ORIGIN + "/sw.js"`) and a subpath one (`ORIGIN + "/lotr-lcg-presto-hud/sw.js"`).
- [ ] **Step 2: Run, expect failures.**
- [ ] **Step 3: Implement** — `git mv` for the three moves so history follows; update every reference above; run `python3 tools/devserver.py --port 8643 --directory docs` is NOT needed (the pane's server is running) — instead verify with `curl -sI http://localhost:8643/` (200, the tablet title) and `http://localhost:8643/presto/` (200, the twin) if the server is up; otherwise say so.
- [ ] **Step 4: Run** `python3 -m pytest tests/ -q` — green. Commit — `feat(site): the tablet client is the root; the Presto twin lives at /presto/; publish to Cloudflare Pages`.

---

### Task 2: The Cloudflare project, domains and redirect (main session)

Needs a Cloudflare API token with **Account · Cloudflare Pages · Edit**, **Zone · DNS · Edit** and **Zone · Dynamic Redirect · Edit** on `lotrlcg.app` and `lotr.quest`, in `~/.zshenv` as `CF_PAGES_TOKEN`, and the same token added by the user to the GitHub repo as secret `CLOUDFLARE_PAGES_TOKEN` plus variable `CLOUDFLARE_ACCOUNT_ID` = `31d0a323fcd472daf6c82573b6010918`.

- [ ] `npx wrangler pages project create lotrlcg --production-branch main` (account id via `CLOUDFLARE_ACCOUNT_ID` env).
- [ ] Build `docs/data/` locally (`python3 tools/build_card_data.py && python3 tools/build_catalog_pack.py && python3 tools/build_icons.py --svg-out docs/data/icons/svg`) and `npx wrangler pages deploy docs --project-name=lotrlcg --branch=main`; check `https://lotrlcg.pages.dev/` and `/presto/`.
- [ ] Custom domains: `POST /accounts/{id}/pages/projects/lotrlcg/domains` for `lotrlcg.app` and `www.lotrlcg.app`; DNS on the `lotrlcg.app` zone: `CNAME lotrlcg.app → lotrlcg.pages.dev` (proxied), `CNAME www → lotrlcg.pages.dev` (proxied); wait for the domain status `active`.
- [ ] `lotr.quest`: `A lotr.quest → 192.0.2.1` (proxied placeholder) + `CNAME www → lotr.quest` (proxied); a Dynamic Redirect rule on the zone: any request → `https://lotrlcg.app${http.request.uri.path}` 301, preserve query string.
- [ ] Merge the tablet branch (with Task 1) into `main`, push; watch the workflow: GitHub Pages deploy green, the wrangler step green; `https://lotrlcg.app/` serves the tablet, `/presto/` the twin, `https://lotr.quest/tablet/x` lands on `https://lotrlcg.app/x`.
- [ ] Record the URLs in `README.md` (Task 1 wrote them) and in memory (`ipad-web-domains`).

## Done when

- `pytest` green; `https://lotrlcg.app/` is the tablet client with a controlling service worker scoped to `/`; `https://lotrlcg.app/presto/` is the twin; `https://lotr.quest/` redirects; `andrhamm.com/lotr-lcg-presto-hud/` shows the same layout (tablet at its root, twin at `/presto/`); every push to `main` updates both hosts.
