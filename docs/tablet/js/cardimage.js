// Card art (Task 6): one card's picture, and the list of every picture a
// scenario can put on screen (for sw.js's prefetch).
//
// Pure string builders like every other tablet render helper - no Image()
// probe, no fetch, no DOM. A card image is a plain hotlink to the pinned S3
// prefix (tools/data/cardDb.SOURCE.txt's `image_prefix=`, surfaced as
// index.json's `imagePrefix` and read by quest_catalog.js's imagePrefix()),
// so nothing is bundled and nothing is copied into docs/data/ - the tablet
// M5 ruling: hotlink the art, let the service worker cache it.
//
// A missing picture is a first-class state, not an error path: there is no
// pinned prefix on an index built before the pin existed, the card may carry
// no art at all, and an offline reload with a cold cache 404s. In every one
// of those the FIGCAPTION is what the player reads, so it is never optional
// - see style.css's `.card-frame.is-missing img` pair, and app.js's one
// delegated capture-phase `error` listener (shared with seticon.js) that
// adds `is-missing` to this wrapper when the <img> fails.
import { h, raw } from "./dom.js";

// The full URL for one card's art, or null when there is nothing to build
// one from.
//
// The FILENAME comes off the card record (`image`), it is not rebuilt from
// the id: it is usually "<id>.jpg" but 24 of 1016 catalog locations print on
// the BACK of a two-sided card and carry "<id>.B.jpg" - rebuilding would
// show the wrong face. `id` is the fallback for a caller that only has one
// (and for the pre-`image` picker entries a saved game may still hold).
//
// An `image` that is already an absolute URL (2 catalog locations carry a
// Hall of Beorn hotlink) is returned untouched - prefixing it would produce
// nonsense.
export function cardUrl(prefix, card) {
  const file = card?.image || (card?.id ? card.id + ".jpg" : null);
  if (!file) return null;
  if (/^https?:\/\//i.test(file)) return file;
  return prefix ? prefix + file : null;
}

// <figure class="card-frame"> for one card. `caption` is appended to the
// name after a middot - the picker passes the printed threat/quest points
// its rows have always shown, so the one caption carries both the card's
// identity and its numbers whether or not the art loads.
export function cardImage({ prefix, id, image, name, caption }) {
  const src = cardUrl(prefix, { id, image });
  const img = src ? h`<img src="${src}" alt="" loading="lazy">` : "";
  return h`<figure class="card-frame">${raw(img)}<figcaption class="body">${name ?? ""}${caption ? " · " + caption : ""}</figcaption></figure>`;
}

// Every card picture the scenario `bundle` can put on screen, each URL once,
// for app.js to hand sw.js as a `prefetch` message when the players commit
// to a scenario. [] for a null prefix (nothing to build a URL from) - the
// worker is then never asked to warm a cache it could not fill.
//
// `bundle.images` is db.bundle()'s pinned list (quest_catalog's
// cardImagesFor()/card_images_for()): every card, every type, across the
// scenario's own set AND its gathered sets (Task 6b's ruling - "Begin setup
// prefetches the scenario's own set and its gathered sets"). A bundle from
// before that field existed (an old save, or a twin mid-upgrade) has no
// `images` key at all, so `oldUnion()` rebuilds the narrower set this
// function used to cover on its own: `scenario`'s own file (every
// `encounter.*` group, all card types) plus `locations`, the picker's
// already-flattened union across the gather list - purely additive, so
// nothing that rendered before stops rendering.
//
// Absolute hotlinks are skipped either way: they are not under `prefix`, so
// sw.js's isImage() never matches them and the image cache could never serve
// one.
function oldUnion(bundle) {
  const cards = [];
  for (const group of Object.values(bundle?.scenario?.encounter ?? {})) {
    if (Array.isArray(group)) cards.push(...group);
  }
  cards.push(...(bundle?.locations ?? []));
  return cards;
}

export function imageUrls(bundle, prefix) {
  if (!prefix) return [];
  const cards = bundle?.images ?? oldUnion(bundle);
  const out = [];
  const seen = new Set();
  for (const card of cards) {
    const url = cardUrl(prefix, card);
    if (!url || !url.startsWith(prefix) || seen.has(url)) continue;
    seen.add(url);
    out.push(url);
  }
  return out;
}
