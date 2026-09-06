"""docs/tablet/sw.js, driven under node against a stub platform.

A service worker cannot be imported: it has no exports, it runs in its own
global scope, and the browser is the only thing that ever fires its events.
So this loads the REAL file - not a copy of its logic - into a `vm` sandbox
whose `self`, `caches` and `fetch` are stubs, then fires the same events the
browser would. That is why every helper in sw.js hangs off `self`.

The five behaviours here are the whole contract:
  (a) card art is served from cache after the first request - one network
      call for two requests, one cache entry;
  (b) the image cache is trimmed to IMAGE_CACHE_MAX, oldest-first;
  (c) shell/data are stale-while-revalidate - the cached copy answers, the
      network refresh lands behind it;
  (d) a `prefetch` message warms the image cache and skips what it already
      has;
  (e) anything unclaimed is left entirely alone (no respondWith at all), so
      the page behaves exactly as it would with no worker installed.
"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SW = os.path.join(ROOT, "docs", "tablet", "sw.js")

PREFIX = "https://dragncards-lotrlcg.s3.amazonaws.com/cards/English/"
ORIGIN = "https://andrhamm.github.io"


# tests/test_tablet.py's runner, copied rather than imported (test modules do
# not import each other in this repo) and simplified: sw.js has no imports at
# all, so there is nothing to stage - the probe is handed the real file's
# path as argv[2] and reads it itself.
def node(probe):
    """Run `probe` (an ES module body) and return its JSON."""
    exe = shutil.which("node")
    if exe is None:
        pytest.skip("node not installed")
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "package.json"), "w") as f:
            f.write('{"type":"module"}')
        path = os.path.join(tmp, "probe.mjs")
        with open(path, "w") as f:
            f.write(HARNESS + probe)
        r = subprocess.run([exe, path, SW], cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 0, "sw.js probe failed:\n%s" % r.stderr
        return json.loads(r.stdout)


# The stub platform, prepended to every probe below.
#
# `Response.body` is the one thing the real API does not expose synchronously;
# it stands in for "which version of this file is this", which is how test (c)
# tells a stale cache hit from a fresh network answer. Everything else is the
# real shape: Cache.keys() is insertion-ordered and returns Requests, put()
# accepts a string url or a Request, and an opaque (no-cors) response reports
# ok === false with type === "opaque".
HARNESS = """\
import fs from "node:fs";
import vm from "node:vm";

const SW = process.argv[2];
const ORIGIN = "%s";
const PREFIX = "%s";

class Res {
  constructor(url, { ok = true, type = "basic", body = "" } = {}) {
    this.url = url; this.ok = ok; this.type = type; this.body = body;
  }
  clone() { return new Res(this.url, this); }
}
class Req {
  constructor(url, init = {}) { this.url = String(url); this.method = init.method || "GET"; }
  clone() { return new Req(this.url, this); }
}
const keyOf = r => (typeof r === "string" ? r : r.url);

function harness({ routes = {} } = {}) {
  const calls = [];
  const store = new Map();                 // cache name -> Map(url -> Response)
  const cacheFor = name => {
    if (!store.has(name)) store.set(name, new Map());
    const m = store.get(name);
    return {
      async match(r) { return m.get(keyOf(r)); },
      // delete-then-set so a rewrite moves the entry to the END of the
      // insertion order, which is what makes trimCache's slice() drop the
      // least-recently-WRITTEN rather than the first-ever-seen.
      async put(r, res) { m.delete(keyOf(r)); m.set(keyOf(r), res); },
      async delete(r) { return m.delete(keyOf(r)); },
      async keys() { return [...m.keys()].map(u => new Req(u)); },
    };
  };
  const caches = { async open(name) { return cacheFor(name); } };
  const fetch = async (req) => {
    const url = keyOf(req);
    calls.push(url);
    const spec = routes[url];
    if (spec === "error") throw new Error("network down");
    return new Res(url, spec || {});
  };
  const handlers = {};
  const self = {
    location: { origin: ORIGIN, href: ORIGIN + "/lotr-lcg-presto-hud/tablet/sw.js" },
    addEventListener: (type, fn) => { (handlers[type] = handlers[type] || []).push(fn); },
    skipWaiting: () => { self._skipWaiting = true; },
    clients: { claim: async () => { self._claimed = true; } },
  };
  const sandbox = { self, caches, fetch, URL, Request: Req, Response: Res,
                    console, setTimeout, clearTimeout };
  sandbox.globalThis = sandbox;
  vm.runInNewContext(fs.readFileSync(SW, "utf8"), sandbox, { filename: "sw.js" });
  return { self, caches, store, calls, handlers, routes,
           cached: name => [...(store.get(name) || new Map()).keys()],
           // Fire a fetch event the way the browser does; returns whatever
           // the worker passed to respondWith, or null if it never called it.
           request: (url, init) => {
             let responded = null;
             handlers.fetch[0]({ request: new Req(url, init),
                                 respondWith: p => { responded = p; },
                                 waitUntil: p => p });
             return responded;
           },
           // Fire a message event and hand back the promise it registered
           // with waitUntil, so a test can await the whole prefetch.
           message: data => {
             let waited = Promise.resolve();
             handlers.message[0]({ data, waitUntil: p => { waited = p; } });
             return waited;
           } };
}

// Let every floating promise sw.js started (staleWhileRevalidate's
// background refresh) settle before asserting on the cache.
const settle = () => new Promise(r => setTimeout(r, 0));
""" % (ORIGIN, PREFIX)


IMG = PREFIX + "51223bd0-ffd1-11df-a976-0801200c9099.jpg"


def test_the_worker_registers_its_handlers_and_takes_over_at_once():
    """install/activate: skipWaiting then clients.claim. A tablet client left
    open on the table would otherwise not see a deploy until every tab
    closed."""
    js = node("""
const h = harness();
h.handlers.install[0]({ waitUntil: p => p });
await h.handlers.activate[0]({ waitUntil: p => p });
console.log(JSON.stringify({
  events: Object.keys(h.handlers).sort(),
  skipWaiting: h.self._skipWaiting === true,
  claimed: h.self._claimed === true,
  shell: h.self.SHELL_CACHE, images: h.self.IMAGE_CACHE, max: h.self.IMAGE_CACHE_MAX,
}));
""")
    assert js["events"] == ["activate", "fetch", "install", "message"]
    assert js["skipWaiting"] and js["claimed"]
    assert js["shell"] == "lotr-tablet-shell-v1"
    assert js["images"] == "lotr-tablet-images-v1"
    assert js["max"] == 400


def test_card_art_is_fetched_once_and_served_from_cache_after_that():
    """(a) THE gate for the feature: the second look at a card costs no
    network at all, which is what makes an offline reload still show the
    picker's thumbnails. Card art is immutable (the URL carries the card's
    uuid), so there is nothing to revalidate."""
    js = node("""
const h = harness();
const first = await h.request("%s");
const second = await h.request("%s");
console.log(JSON.stringify({
  calls: h.calls.length,
  entries: h.cached(h.self.IMAGE_CACHE),
  firstUrl: first.url, secondUrl: second.url,
  isImage: h.self.isImage("%s"),
  // A card-art url is NOT claimed by the shell rule as well - it is a
  // foreign origin, so only the image branch can ever see it.
  shellClaimed: h.self.isShellOrData("%s"),
}));
""" % (IMG, IMG, IMG, IMG))
    assert js["calls"] == 1, "the second request must not touch the network"
    assert js["entries"] == [IMG]
    assert js["firstUrl"] == js["secondUrl"] == IMG
    assert js["isImage"] and not js["shellClaimed"]


BACK_FACE_IMG = PREFIX + "02ba32c6-9442-4a69-b89b-b2ec4ee24be2.B.jpg"


def test_a_back_face_location_is_served_cache_first_too():
    """Regression (Task 6b finding 1): 18-24 catalog locations print on the
    BACK of a two-sided card and carry "<id>.B.jpg" (cardimage.js's cardUrl/
    locationsFor carry the recorded `image` filename rather than rebuilding
    "<id>.jpg" from the id). The old isImage() regex required a bare hex uuid
    right before ".jpg" and never matched that shape, so every back-face
    location silently fell through to `fetch` on every single reload."""
    js = node("""
const first = await (async () => {
  const h = harness();
  const r1 = await h.request("%s");
  const r2 = await h.request("%s");
  return { calls: h.calls.length, entries: h.cached(h.self.IMAGE_CACHE),
           isImage: h.self.isImage("%s") };
})();
console.log(JSON.stringify(first));
""" % (BACK_FACE_IMG, BACK_FACE_IMG, BACK_FACE_IMG))
    assert js["isImage"], "a <id>.B.jpg back-face url must match isImage()"
    assert js["calls"] == 1, "the second look must be served from cache, not refetched"
    assert js["entries"] == [BACK_FACE_IMG]


def test_an_opaque_no_cors_response_is_cached_as_a_success():
    """The art host sends no CORS headers, so every card image comes back
    opaque: ok === false, type === "opaque". Treating that as a failure would
    mean the image cache never held a single entry in a real browser."""
    js = node("""
const url = PREFIX + "aaaaaaaa-0000-0000-0000-000000000001.jpg";
const h = harness({ routes: { [url]: { ok: false, type: "opaque" } } });
await h.request(url);
await h.request(url);
console.log(JSON.stringify({ calls: h.calls.length, entries: h.cached(h.self.IMAGE_CACHE) }));
""")
    assert js["calls"] == 1
    assert len(js["entries"]) == 1


def test_the_image_cache_is_trimmed_to_400_keeping_the_newest():
    """(b) 401 entries in, 400 out - and it is the OLDEST that goes. The cap
    is a count, not a byte budget, because a no-cors opaque response reports
    no size at all (see sw.js's own note; the real quota is milestone 7's
    first soak item)."""
    js = node("""
const h = harness();
const c = await h.caches.open(h.self.IMAGE_CACHE);
const url = i => PREFIX + "card-" + String(i).padStart(4, "0") + ".jpg";
for (let i = 0; i < 401; i++) await c.put(url(i), new Res(url(i)));
const before = h.cached(h.self.IMAGE_CACHE).length;
await h.self.trimCache(c, h.self.IMAGE_CACHE_MAX);
const after = h.cached(h.self.IMAGE_CACHE);
console.log(JSON.stringify({
  before, count: after.length,
  oldestGone: !after.includes(url(0)),
  newestKept: after.includes(url(400)),
  firstKept: after[0] === url(1),
  // A cache already under the cap is left completely alone.
  noopUnderCap: await (async () => {
    await h.self.trimCache(c, h.self.IMAGE_CACHE_MAX);
    return h.cached(h.self.IMAGE_CACHE).length;
  })(),
}));
""")
    assert js["before"] == 401
    assert js["count"] == 400
    assert js["oldestGone"] and js["newestKept"] and js["firstKept"]
    assert js["noopUnderCap"] == 400


def test_shell_and_data_answer_from_cache_and_refresh_behind_it():
    """(c) stale-while-revalidate over this client's own files: the first
    request is a plain network fetch, the second is answered from cache
    INSTANTLY (the stale copy) while a second fetch refreshes the entry for
    the load after. That is how a deploy lands without ever costing a tap a
    round trip."""
    js = node("""
const url = ORIGIN + "/lotr-lcg-presto-hud/tablet/js/app.js";
const h = harness({ routes: { [url]: { body: "v1" } } });
const first = await h.request(url);
await settle();
h.routes[url] = { body: "v2" };            // a deploy lands between the two
const second = await h.request(url);
await settle();
console.log(JSON.stringify({
  claimed: h.self.isShellOrData(url),
  calls: h.calls.length,
  first: first.body,
  second: second.body,
  cachedAfter: (await (await h.caches.open(h.self.SHELL_CACHE)).match(url)).body,
  // The shared docs/js and docs/data the tablet imports are claimed too -
  // the client is not self-contained under /tablet/.
  sharedJs: h.self.isShellOrData(ORIGIN + "/lotr-lcg-presto-hud/js/gamestate.js"),
  sharedData: h.self.isShellOrData(ORIGIN + "/lotr-lcg-presto-hud/data/index.json"),
}));
""")
    assert js["claimed"] and js["sharedJs"] and js["sharedData"]
    assert js["calls"] == 2, "one network fetch per request: the first, then the refresh"
    assert js["first"] == "v1"
    assert js["second"] == "v1", "the SECOND request is answered from cache, stale"
    assert js["cachedAfter"] == "v2", "and the refresh landed behind it"


def test_a_shell_request_survives_the_network_being_gone():
    """The offline half of the same rule: with a warm cache a dead network is
    invisible; with a cold one the request simply fails the way it would have
    without a worker."""
    js = node("""
const url = ORIGIN + "/lotr-lcg-presto-hud/tablet/js/app.js";
const h = harness({ routes: { [url]: { body: "v1" } } });
await h.request(url);
await settle();
h.routes[url] = "error";                   // the tablet goes offline
const offline = await h.request(url);
await settle();
console.log(JSON.stringify({ offline: offline.body,
                             stillCached: (await (await h.caches.open(h.self.SHELL_CACHE)).match(url)).body }));
""")
    assert js["offline"] == "v1"
    assert js["stillCached"] == "v1", "a failed refresh must not evict the good copy"


def test_a_prefetch_message_warms_the_cache_and_skips_what_it_has():
    """(d) app.js posts this once, when the players commit to a scenario.
    Everything not already cached is fetched; everything cached costs
    nothing."""
    js = node("""
const url = i => PREFIX + "prefetch-" + i + ".jpg";
const h = harness();
const c = await h.caches.open(h.self.IMAGE_CACHE);
await c.put(url(1), new Res(url(1)));      // already warm from a past game
await h.message({ type: "prefetch", urls: [url(1), url(2), url(3)] });
console.log(JSON.stringify({
  fetched: h.calls,
  entries: h.cached(h.self.IMAGE_CACHE).length,
}));
""")
    assert js["fetched"] == [PREFIX + "prefetch-2.jpg", PREFIX + "prefetch-3.jpg"], \
        "an already-cached url must not be refetched"
    assert js["entries"] == 3


def test_a_prefetch_ignores_other_messages_and_survives_a_dead_url():
    """One dead url must not abandon the rest of the list, and a message this
    worker does not own is not a prefetch with no urls - it is not handled at
    all."""
    js = node("""
const url = i => PREFIX + "prefetch-" + i + ".jpg";
const h = harness({ routes: { [url(2)]: "error" } });
await h.message({ type: "something-else", urls: [url(1)] });
const afterOther = h.calls.length;
await h.message({ type: "prefetch", urls: [url(1), url(2), url(3)] });
console.log(JSON.stringify({
  afterOther,
  attempted: h.calls.length,
  entries: h.cached(h.self.IMAGE_CACHE).sort(),
}));
""")
    assert js["afterOther"] == 0, "a foreign message must not fetch anything"
    assert js["attempted"] == 3, "the dead url is attempted, and the list continues past it"
    assert js["entries"] == [PREFIX + "prefetch-1.jpg", PREFIX + "prefetch-3.jpg"]


def test_a_prefetch_of_more_than_the_cap_leaves_the_cache_at_the_cap():
    """The trim runs after a prefetch too, so a scenario with more cards than
    the cap cannot blow past it."""
    js = node("""
const h = harness();
const urls = [];
for (let i = 0; i < 405; i++) urls.push(PREFIX + "many-" + String(i).padStart(4, "0") + ".jpg");
await h.message({ type: "prefetch", urls });
console.log(JSON.stringify({ fetched: h.calls.length,
                             entries: h.cached(h.self.IMAGE_CACHE).length }));
""")
    assert js["fetched"] == 405
    assert js["entries"] == 400


def test_anything_unclaimed_is_left_entirely_alone():
    """(e) No respondWith at all - not an empty one, not a passthrough fetch:
    the browser then does exactly what it would with no worker installed. A
    worker that answers everything is a worker that can break a page it was
    never meant to touch."""
    js = node("""
const h = harness();
const post = h.request(ORIGIN + "/lotr-lcg-presto-hud/tablet/js/app.js", { method: "POST" });
console.log(JSON.stringify({
  foreignJson: h.request("https://other.test/api/thing.json") === null,
  foreignPage: h.request("https://other.test/") === null,
  // Same origin but outside this client and the shared data it reads (the
  // web twin's own page, say) - not ours to cache.
  otherPage: h.request(ORIGIN + "/lotr-lcg-presto-hud/index.html") === null,
  // A non-GET never goes through the shell cache (Cache.put rejects one).
  postNotClaimed: post === null,
  calls: h.calls.length,
}));
""")
    assert js["foreignJson"] and js["foreignPage"] and js["otherPage"]
    assert js["postNotClaimed"]
    assert js["calls"] == 0, "an unclaimed request must not be fetched by the worker either"


def test_a_dead_network_on_a_cold_cache_rejects_cleanly_and_caches_nothing():
    """(f) Task 6b finding 4: cacheFirst has no try/catch around `fetch` - a
    cold cache plus a dead network means the `await fetch(...)` inside it
    throws, so the promise handed to respondWith rejects too (a real browser
    turns a rejected respondWith into a network error for the page, exactly
    as if no worker were installed). The probe wraps its own await in
    try/catch, the same way a real caller of a rejecting respondWith would
    never crash the page - this only asserts the harness sees a clean
    rejection, not a hang or an unhandled-rejection crash, and that nothing
    half-written lands in the cache."""
    js = node("""
const h = harness({ routes: { ["%s"]: "error" } });
let rejected = false;
try {
  await h.request("%s");
} catch (e) {
  rejected = true;
}
console.log(JSON.stringify({ rejected, entries: h.cached(h.self.IMAGE_CACHE) }));
""" % (IMG, IMG))
    assert js["rejected"] is True
    assert js["entries"] == []


def test_the_worker_is_a_classic_script_with_no_module_syntax():
    """Plan ruling R7: the iPad this client targets predates module workers,
    and a {type:"module"} worker there does not degrade - it never installs.
    A stray `import`/`export` would also break the vm harness above, but this
    says WHY out loud so nobody "modernises" the file."""
    with open(SW) as f:
        src = f.read()
    code = [ln for ln in src.splitlines() if not ln.strip().startswith("//")]
    for bad in ("import ", "export ", "importScripts", "require("):
        assert not any(bad in ln for ln in code), "sw.js must stay a classic worker (%s)" % bad
