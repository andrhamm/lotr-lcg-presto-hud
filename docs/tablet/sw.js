// The tablet's network layer: shell + data served from cache with a network
// refresh behind it; card images cache-first in their own cache, newest-N
// kept.
//
// CLASSIC worker - importScripts-style globals, no `import`, no
// `importScripts` either (there is nothing to pull in). Plan ruling R7: the
// iPad this client targets predates module workers, and a `{type:"module"}`
// registration there does not degrade, it simply never installs. So this
// file is deliberately dependency-free and deliberately not an ES module.
//
// Every helper hangs off `self`, for two reasons that happen to agree: a
// classic worker has no exports, and tests/test_tablet_sw.py loads THIS file
// into a vm sandbox with a stub self/caches/fetch and drives the helpers
// directly - the alternative would be testing a copy of this logic, which is
// how the two halves of a cache drift apart.
//
// This is the one file under docs/ besides quest_catalog.js that may call
// `fetch` (tests/test_no_stray_io.py allow-lists it by name): a service
// worker IS the network, so routing it through the data client is not
// something it declines to do, it is something it cannot do - it runs in its
// own global scope, beneath every page module, and the client's own reads
// are among the requests passing through here.

// Bump either name to retire that cache wholesale (activate does not sweep
// old names yet - there is exactly one version of each so far, and a sweep
// that guesses at which names are "ours" is how a shared origin loses
// someone else's cache).
self.SHELL_CACHE = "lotr-tablet-shell-v1";
self.IMAGE_CACHE = "lotr-tablet-images-v1";

// The image cache is capped by COUNT, not bytes: a card scan is ~100-200 KB,
// so 400 is a few tens of MB - one scenario's own cards plus its gather list
// is well under that, and the trim only ever bites after several sessions
// with different quests. Measuring the real quota on the iPad is milestone
// 7's first soak item; until then a count cap is the honest lever, since a
// no-cors opaque response reports no size at all.
self.IMAGE_CACHE_MAX = 400;

// The pinned card-art host lays every scan out as /cards/<Language>/<file>.jpg
// (tools/data/cardDb.SOURCE.txt's image_prefix=). Matching on the shape
// rather than on the host keeps this working if the pin is refreshed to a
// different bucket, and keeps it from claiming anything else the page loads.
// `<file>` is not always the bare uuid: 18-24 catalog locations print on a
// card's BACK and carry "<id>.B.jpg" (see cardimage.js's cardUrl/locationsFor
// - the filename is the card's recorded `image`, never rebuilt from the id),
// so this matches any single filename segment, not just a hex uuid.
self.isImage = url => /\/cards\/[A-Za-z]+\/[^\/]+\.jpg$/.test(url);

// The shell and the compiled catalog: this client's own files under
// /tablet/, plus the shared /js/ modules and /data/ card files it imports -
// same-origin only, so a hotlink is never swept in here by accident. The
// path tests are relative because the site is not at the origin root on
// GitHub Pages (/lotr-lcg-presto-hud/tablet/), so a leading-anchor test
// would match nothing there.
self.isShellOrData = url => {
  const u = new URL(url);
  return u.origin === self.location.origin
    && (/\/tablet\//.test(u.pathname) || /\/js\/|\/data\//.test(u.pathname));
};

// Drop the OLDEST entries past `max`. Cache.keys() is insertion-ordered and
// cacheFirst deletes-then-puts, so "oldest" is genuinely least-recently-
// written rather than merely first-seen.
self.trimCache = async (cache, max) => {
  const keys = await cache.keys();
  for (const k of keys.slice(0, Math.max(0, keys.length - max))) await cache.delete(k);
};

// Card art: whatever is cached wins outright and costs no network at all.
// Art is immutable - the URL carries the card's uuid - so there is nothing
// to revalidate, which is exactly what makes an offline reload show the
// pictures. `no-cors` because the art host sends no CORS headers: the
// opaque response cannot be read by script but caches and renders fine, so
// `res.type === "opaque"` is a SUCCESS here, not a fallback.
//
// The flip side is accepted, not fixed: an opaque response also hides a 404
// (script cannot read its status either), so a genuinely missing card gets
// cached as if it were a hit and stays that way until it ages out. The
// `.is-missing` caption (app.js's delegated `error` listener) still covers
// the render either way, so a dead url just looks the same both times.
self.cacheFirst = async (name, req, max) => {
  const c = await caches.open(name);
  const hit = await c.match(req);
  if (hit) return hit;
  const res = await fetch(req, { mode: "no-cors" });
  if (res && (res.ok || res.type === "opaque")) {
    await c.put(req, res.clone());
    await self.trimCache(c, max);
  }
  return res;
};

// Shell and data: answer from cache instantly, refresh behind the answer, so
// a deploy lands on the NEXT load rather than costing this one a round trip.
// A cold cache falls through to the network response itself; a network
// failure with a warm cache is invisible, which is the offline story.
self.staleWhileRevalidate = async (name, req) => {
  const c = await caches.open(name);
  const hit = await c.match(req);
  const net = fetch(req)
    .then(res => { if (res && res.ok) c.put(req, res.clone()); return res; })
    .catch(() => hit);
  return hit || net;
};

// Take over immediately rather than waiting for every tab to close: this is
// a single-page client on a tablet that is usually left open on the table,
// so "the update lands next week" is the realistic alternative.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));

// Anything this worker does not claim - a foreign-origin request that is not
// card art - is left entirely alone: no respondWith at all, so the browser
// does exactly what it would have done with no worker installed.
self.addEventListener("fetch", e => {
  const url = e.request.url;
  if (self.isImage(url)) {
    e.respondWith(self.cacheFirst(self.IMAGE_CACHE, e.request, self.IMAGE_CACHE_MAX));
  } else if (self.isShellOrData(url) && e.request.method === "GET") {
    e.respondWith(self.staleWhileRevalidate(self.SHELL_CACHE, e.request));
  }
});

// Prefetch (app.js posts this once, when the players commit to a scenario):
// warm the image cache for every card that scenario can show, so the first
// location picker of the game is already drawn. Serial on purpose - it runs
// while the players are still setting up, and a burst of a few hundred
// parallel requests on hotel wifi is how the shell's own fetches get
// starved. Already-cached urls cost nothing, and a single failure is
// swallowed so one dead url never abandons the rest of the list.
self.addEventListener("message", e => {
  if (e.data?.type !== "prefetch") return;
  e.waitUntil((async () => {
    const c = await caches.open(self.IMAGE_CACHE);
    for (const u of e.data.urls || []) {
      if (await c.match(u)) continue;
      try {
        const r = await fetch(u, { mode: "no-cors" });
        if (r) await c.put(u, r);
      } catch (err) { /* one dead url must not abandon the list */ }
    }
    await self.trimCache(c, self.IMAGE_CACHE_MAX);
  })());
});
