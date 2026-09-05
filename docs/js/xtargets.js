// GENERATED from xtargets.py - do not edit (tools/gen_web_data.py)
export const AUTO_ENEMIES = "enemies";
export const AUTO_HIGHEST_THREAT = "highest_threat";
export const AUTO_PLAYERS = "players";
export const AUTO_STAGE = "stage";
export const AUTO_STAGING_LOCATIONS = "staging_locations";
export const TARGETS = {"players": {"label": "Players", "auto": "players"}, "stage_number": {"label": "Main quest stage", "auto": "stage"}, "highest_threat": {"label": "Highest player threat", "auto": "highest_threat"}, "enemies_in_play": {"label": "Enemies in play", "auto": "enemies"}, "nazgul_in_play": {"label": "Nazgul enemies in play", "auto": null}, "dark_locations_in_play": {"label": "Dark locations in play", "auto": null}, "quest_cards_in_play": {"label": "Quest cards in play", "auto": null}, "allies_in_play": {"label": "Ally cards in play", "auto": null}, "characters_in_play": {"label": "Characters in play", "auto": null}, "damaged_characters": {"label": "Damaged characters", "auto": null}, "locations_in_staging": {"label": "Locations in staging", "auto": "staging_locations"}, "snow_in_staging": {"label": "Snow cards in staging", "auto": null}, "ally_cost_in_staging": {"label": "Total ally cost in staging", "auto": null}, "first_player_characters": {"label": "First player's characters", "auto": null}, "first_player_hand": {"label": "Cards in first player's hand", "auto": null}, "heroes_questing": {"label": "Heroes committed to the quest", "auto": null}, "allies_most": {"label": "Allies of the player with the most", "auto": null}, "allies_breelanders": {"label": "Bree-landers player's allies", "auto": null}, "clue_objectives": {"label": "Clue objectives controlled", "auto": null}, "captive_allies": {"label": "Captive objective allies", "auto": null}, "mount_objectives": {"label": "Mount objectives controlled", "auto": null}, "locations_controlled": {"label": "Locations controlled", "auto": null}, "castle_side_quests_victory": {"label": "Castle side quests in victory", "auto": null}, "quest_stages_victory": {"label": "Quest stages in victory", "auto": null}, "resources_on_main_quest": {"label": "Resources on the main quest", "auto": null}, "resources_here": {"label": "Resource tokens here", "auto": null}, "progress_on_to_the_tower": {"label": "Progress on To the Tower", "auto": null}, "cards_captured_here": {"label": "Cards captured here", "auto": null}, "highest_wose_archery": {"label": "Highest Wose archery value", "auto": null}};

export function labelFor(target) {
  return TARGETS[target]?.label ?? null;
}

export function autoFor(target) {
  return TARGETS[target]?.auto ?? null;
}

// value = mul * count + add, never below zero.
export function valueOf(count, mul = 1, add = 0) {
  return Math.max(0, mul * count + add);
}

// The number to put on screen, or null when the player has not supplied a
// count yet. An auto target ignores `count` and recomputes from the tracked
// value - that is the whole point of tagging those separately: "X is 4 per
// player" must follow the player count without anyone touching a stepper.
// GameState.xContext() supplies every tracked value by these option names.
export function resolve(spec, { count = null, players = 1, stage = 1,
                                highestThreat = 0, enemies = 0,
                                stagingLocations = 0 } = {}) {
  if (!spec) return null;
  const mul = spec.mul ?? 1, add = spec.add ?? 0;
  switch (autoFor(spec.target)) {
    case AUTO_PLAYERS: return valueOf(players, mul, add);
    case AUTO_STAGE: return valueOf(stage, mul, add);
    case AUTO_HIGHEST_THREAT: return valueOf(highestThreat, mul, add);
    case AUTO_ENEMIES: return valueOf(enemies, mul, add);
    case AUTO_STAGING_LOCATIONS: return valueOf(stagingLocations, mul, add);
  }
  if (count === null) return null;
  return valueOf(count, mul, add);
}
