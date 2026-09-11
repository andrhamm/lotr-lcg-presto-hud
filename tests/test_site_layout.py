"""The site layout after the Cloudflare Pages move (Task 1 of the hosting
plan, docs/superpowers/sdd/2026-09-06-hosting-cloudflare-pages/): the tablet
client is now the site root and the Presto web twin lives at /presto/.

These are plain file-content assertions, not behavioural tests - the pages
themselves are exercised by test_tablet.py / test_tablet_sw.py under node.
This file just pins the layout so a future move can't silently drift: the
root page must load the tablet's own assets, /presto/ must load the twin's
with paths relative to its new depth, the service worker must live at the
root (its scope is bounded by its own directory - see sw.js's isShellOrData),
and GitHub Pages (which ignores Cloudflare's `_redirects`) needs a stub at
the old /tablet/ location.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")


def _read(*parts):
    with open(os.path.join(DOCS, *parts), encoding="utf-8") as f:
        return f.read()


def test_the_root_page_is_the_tablet_client():
    html = _read("index.html")
    assert 'src="tablet/js/app.js"' in html
    assert 'href="tablet/style.css"' in html


def test_the_presto_twin_lives_under_presto_with_paths_one_level_up():
    html = _read("presto", "index.html")
    assert 'src="../js/main.js"' in html
    assert 'href="../style.css"' in html


def test_the_service_worker_moved_to_the_root():
    assert os.path.isfile(os.path.join(DOCS, "sw.js"))
    assert not os.path.exists(os.path.join(DOCS, "tablet", "sw.js")), \
        "the old docs/tablet/sw.js must be gone, not merely duplicated"


def test_redirects_send_old_tablet_links_to_the_new_root():
    """Only the old ENTRY page redirects. The tablet's own assets still live
    under /tablet/ (the root index loads tablet/js/app.js and tablet/style.css),
    so a /tablet/* wildcard would send the site's scripts away from themselves
    on Cloudflare Pages, where _redirects wins over static files."""
    redirects = _read("_redirects")
    assert re.search(r"^/tablet/\s+/\s+301\s*$", redirects, re.MULTILINE)
    assert re.search(r"^/tablet/index\.html\s+/\s+301\s*$", redirects, re.MULTILINE)
    assert not re.search(r"^/tablet/\*", redirects, re.MULTILINE), \
        "a /tablet/* wildcard would redirect tablet/js/app.js and tablet/style.css"


def test_headers_set_cache_control_for_the_worker_and_data():
    headers = _read("_headers")
    assert re.search(r"^/sw\.js\b", headers, re.MULTILINE)
    assert "no-cache" in headers
    assert re.search(r"^/data/\*\s*$", headers, re.MULTILINE)
    assert "max-age=3600" in headers


def test_the_old_tablet_index_is_a_stub_that_refreshes_to_the_root():
    # GitHub Pages ignores Cloudflare's `_redirects` file, so the old
    # docs/tablet/index.html (a real path there, unlike /tablet/* on
    # Cloudflare) needs its own client-side refresh to the new root.
    html = _read("tablet", "index.html")
    assert re.search(
        r'<meta[^>]+http-equiv="refresh"[^>]+content="0;\s*url=\.\./"', html
    ), "the stub must meta-refresh to ../ (the new site root)"
    assert 'href="../"' in html


def _workflow(name):
    with open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8") as f:
        return f.read()


def test_production_is_published_from_a_workflow_main_cannot_trigger():
    """THE invariant of the release setup: merging a feature branch must not
    move lotrlcg.app. The Cloudflare publish lives in one file, and that file
    has no `push:` trigger at all - it runs when release.yml calls it (on the
    run that cut a release) or when a human dispatches it by hand."""
    prod = _workflow("deploy-production.yml")
    assert "pages deploy docs --project-name=lotrlcg" in prod
    assert "cloudflare/wrangler-action@v3" in prod
    triggers = prod.split("jobs:")[0]
    assert "workflow_call:" in triggers
    assert "push:" not in triggers, (
        "deploy-production must not listen to pushes - that is the whole point")


def test_only_the_release_run_reaches_production():
    """release.yml opens/updates the release PR on every push to main, and
    calls the production deploy ONLY when release-please reports it actually
    cut a release."""
    rel = _workflow("release.yml")
    assert "googleapis/release-please-action@v4" in rel
    assert "uses: ./.github/workflows/deploy-production.yml" in rel
    assert "needs.release-please.outputs.release_created == 'true'" in rel


def test_ci_deploys_the_preview_and_nothing_else():
    """main publishes the GitHub Pages mirror and stops there. If a wrangler
    step ever appears in this file, main is deploying to production again."""
    ci = _workflow("ci.yml")
    assert "actions/deploy-pages@v4" in ci
    assert "wrangler" not in ci, "CI must not publish to production"
    assert "pytest" in ci, "the suite has to run before main deploys anything"


def test_release_please_is_configured_at_the_repo_root():
    import json
    with open(os.path.join(ROOT, "release-please-config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    assert "." in cfg["packages"], "single root package"
    with open(os.path.join(ROOT, ".release-please-manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    assert "." in manifest, "the manifest seeds the current version"
