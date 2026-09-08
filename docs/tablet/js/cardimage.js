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

// Every image filename this card can show, front first, deduped. A card's
// `faces` each carry their own `image` and 198 encounter cards in the catalog
// have two DIFFERENT ones (a two-sided card: "<id>.jpg" and "<id>.B.jpg"), so
// this is what makes a flip real rather than a control that shows the same
// picture twice. Falls back to the record's own `image`/`id` for a caller
// that has no faces (the location picker's flattened entries).
export function faceFiles(card) {
  const out = [];
  for (const f of card?.faces ?? []) {
    if (f?.image && !out.includes(f.image)) out.push(f.image);
  }
  if (!out.length) {
    const one = card?.image || (card?.id ? card.id + ".jpg" : null);
    if (one) out.push(one);
  }
  return out;
}

// One card. `caption` is appended to the name after a middot - the picker
// passes the printed threat/quest points its rows have always shown, so the
// one caption carries both the card's identity and its numbers whether or not
// the art loads.
//
// It is a BUTTON, not a figure: every card on screen opens the quick view, and
// this client's rule is that a thing you can tap is a real <button> with a
// data-act for app.js to delegate on. The files ride along in the dataset so
// the modal needs no lookup table and the renderers stay pure - app.js reads
// them off the element it was handed.
//
// A card with no art at all stays an inert <figure>: there is nothing to
// enlarge, and a control that opens an empty modal is worse than no control.
// The caption is what the player reads in that case (see the module header),
// which is exactly why it is never optional.
// What the quick view's table says about a card. Everything here is READ OFF
// THE RECORD - the printed values, the printed traits, the printed keywords,
// how many copies the set contains - and anything the card does not print is
// simply absent rather than shown as a zero, which would be a claim the card
// does not make.
//
// The card's own picture is not repeated in words: its text, its art and its
// stat column are all legible at this size, so the table carries what the
// PICTURE cannot say - which set it belongs to, when that came out, and how
// many copies of it are in the deck.
export function cardFacts({ card, packDate }) {
  const f = (card?.faces ?? [])[0] ?? {};
  const rows = [];
  const put = (k, v) => { if (v !== null && v !== undefined && v !== "") rows.push([k, String(v)]); };
  put("quantity", card?.quantity);
  put("set", card?.encounterSet);
  put("pack", card?.pack);
  put("released", packDate);
  put("type", card?.type);
  put("traits", (card?.traits ?? "").replace(/\.$/, "").replace(/\.\s*/g, " · "));
  put("keywords", (card?.keywords ?? "").replace(/\.$/, "").replace(/\.\s*/g, " · "));
  put("engagement", f.engagementCost);
  put("threat", f.threat);
  put("willpower", f.willpower);
  put("attack", f.attack);
  put("defense", f.defense);
  put("hitPoints", f.hitPoints);
  put("questPoints", f.questPoints);
  put("victory", f.victoryPoints);
  return rows;
}

export function cardImage({ prefix, id, image, name, caption, faces = null, facts = null }) {
  const files = faceFiles({ id, image, faces });
  const src = cardUrl(prefix, { id, image });
  const img = src ? h`<img src="${src}" alt="" loading="lazy">` : "";
  // The caption rides in its own nowrap span: as a bare " · " + text it
  // wrapped between the two, leaving a separator dangling at the start of
  // the second line ("East Bight Patrol" / "· x1").
  const label = caption
    ? h`${name ?? ""}${raw(h` <span class="card-copies">· ${caption}</span>`)}`
    : h`${name ?? ""}`;
  if (!files.length || !prefix) {
    return h`<figure class="card-frame">${raw(img)}<figcaption class="body">${raw(label)}</figcaption></figure>`;
  }
  // The facts ride as JSON in the dataset alongside the files, for the same
  // reason: the modal needs no lookup table and every renderer stays pure.
  const factAttr = facts && facts.length
    ? raw(h` data-facts="${JSON.stringify(facts)}"`) : "";
  return h`<button type="button" class="card-frame" data-act="open_card" data-arg="${name ?? ""}" data-files="${files.join(",")}" data-caption="${caption ?? ""}"${factAttr}>${raw(img)}<span class="body card-cap">${raw(label)}</span></button>`;
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
