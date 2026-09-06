// The location picker's own acts (Task 5) - mirrors LocationPickModal's
// onButton/_commit (docs/js/screens.js) with no "how it arrived" toggle:
// arrival is read off `ui.sheet.back` instead (see the module comment in
// sheet_locpick.js). `back === "play"` means the players are paying the
// travel cost (the Travel pane's own CTA); anything else (the quest sheet's
// "+ Add location", acts_quest.js's lReplace) is a card effect.
// changeLocation() never reads arrival at all (its log line is the same
// either way), so this uniform rule is exactly as safe for mode "change" as
// it is for "new". Split out of actions.js's single dispatch() (review
// finding 6, task-4 fix round 1) - one of the per-area handlers dispatch()
// tries in order, `handle` returns null for any act it does not own.
export function openLocPick(ui, mode, idx, back) {
  ui.sheet = {
    kind: "locpick", mode, idx, back, selected: null, page: 0,
    manual: (ui.locations ?? []).length ? null : { points: 3, contrib: 2 },
  };
}

export function handle(game, ui, act, arg) {
  // Every caller dispatches this same act - the quest sheet's "+ Add
  // location" chip (sheet_quest.js, no arg at all) and the Travel pane's own
  // CTA (pane.js) - distinguished only by `arg`, "<mode>:<idx>:<back>"
  // (idx/back default the same way an empty `commit`/`thr` field would:
  // absent means "the common case", here mode "new", idx 0, back "quest" -
  // exactly what the already-landed quest-sheet chip needs since it renders
  // with no arg at all).
  if (act === "open_locpick") {
    const [modeArg, idxArg, backArg] = (arg || "").split(":");
    openLocPick(ui, modeArg || "new", idxArg ? Number(idxArg) : 0, backArg || "quest");
    return true;
  }
  if (act === "locpick_row") {
    if (ui.sheet?.kind !== "locpick") return false;
    ui.sheet.selected = arg;
    return true;
  }
  if (act === "locpick_manual") {
    if (ui.sheet?.kind !== "locpick" || ui.sheet.manual) return false;
    ui.sheet.manual = { points: 3, contrib: 2 };
    return true;
  }
  if (act === "locpick_pts" || act === "locpick_contrib") {
    const m = ui.sheet?.kind === "locpick" ? ui.sheet.manual : null;
    if (!m) return false;
    const key = act === "locpick_pts" ? "points" : "contrib";
    const hi = act === "locpick_pts" ? 30 : 9;
    const lo = act === "locpick_pts" ? 1 : 0;
    const next = Math.max(lo, Math.min(hi, m[key] + Number(arg)));
    if (next === m[key]) return false;
    m[key] = next;
    return true;
  }
  if (act === "locpick_travel") {
    const sheet = ui.sheet;
    if (sheet?.kind !== "locpick" || sheet.selected === null) return false;
    const e = (ui.locations ?? []).find(x => x.id === sheet.selected);
    if (!e) return false;
    const arrival = sheet.back === "play" ? "travel" : "effect";
    const entry = { ...e, arrival };
    if (sheet.mode === "new") game.travelTo(e.points ?? 0, e.threat ?? 0, e.name, entry);
    else game.changeLocation(e.points ?? 0, e.threat ?? 0, e.name, sheet.idx, entry);
    ui.sheet = sheet.back === "quest" ? { kind: "quest" } : null;
    return true;
  }
  if (act === "locpick_save") {
    const sheet = ui.sheet;
    if (sheet?.kind !== "locpick" || !sheet.manual) return false;
    const { points, contrib } = sheet.manual;
    const arrival = sheet.back === "play" ? "travel" : "effect";
    const entry = { arrival };
    // A manual entry has no catalog row to carry a threat, but the
    // contribution stepper's own caption says the same thing: "its threat
    // leaves the staging area while it is active" - so that number IS the
    // location's threat once it is seated (LocationPickModal._commit's own
    // rule, verbatim: without this, travelling took N out of staging and
    // "Back to staging" put 0 back).
    if (contrib) entry.threat = contrib;
    if (sheet.mode === "new") game.travelTo(points, contrib, null, entry);
    else game.changeLocation(points, contrib, null, sheet.idx, entry);
    ui.sheet = sheet.back === "quest" ? { kind: "quest" } : null;
    return true;
  }
  if (act === "locpick_cancel") {
    const sheet = ui.sheet;
    if (sheet?.kind !== "locpick") return false;
    ui.sheet = sheet.back === "quest" ? { kind: "quest" } : null;
    return true;
  }
  return null;
}
