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
    redirects = _read("_redirects")
    assert re.search(r"^/tablet/\*\s+/:splat\s+301\s*$", redirects, re.MULTILINE), \
        "docs/_redirects must 301 the old /tablet/* paths to the new root"


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


def test_the_pages_workflow_publishes_to_cloudflare_pages():
    with open(os.path.join(ROOT, ".github", "workflows", "pages.yml"), encoding="utf-8") as f:
        workflow = f.read()
    assert "pages deploy docs --project-name=lotrlcg" in workflow
    assert "cloudflare/wrangler-action@v3" in workflow
