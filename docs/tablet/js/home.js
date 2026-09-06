// The landing screen - the first thing the app shows, on every launch.
//
// The Presto has had one since the beginning (ui/screen_boot.py: full-bleed
// box art, Resume Game with a save stamp, New Game, a disclaimers link); the
// tablet dropped straight into the picker, which meant a player with a game
// in progress was shown a scenario chooser and a player without one was
// given no way to say "not yet".
//
// The art is deliberately NOT the Presto's: `boot_bg.png` is FFG's printed
// box art, which is fine on a device in one person's hands and is not fine
// on a public web build (see CLAUDE.md's data policy - the line is verbatim
// third-party content, wherever it ships). `.home-art` is an empty layer
// waiting for royalty-free/community art; until it is filled the wordmark
// carries the screen on type alone.
//
// Pure string builder like every other tablet render module. Everything it
// draws comes off `ui.home` ({ resume: {name, round, savedAt} | null }),
// seated by app.js's boot().
import { h, raw } from "./dom.js";
import { CHROME } from "./copy.js";
import { cta } from "./primitives.js";

// The save stamp under Resume: what game you would be going back into, in
// falling order of usefulness - the quest's name, how far in, and when you
// last touched it. Each piece is dropped rather than faked when the save
// cannot answer it (a bare/manual game carries no scenario name at all), so
// the line never shows a stranded separator or a "Round undefined".
function resumeMeta(r) {
  const when = r.savedAt ? new Date(r.savedAt).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  }) : "";
  return [r.name, r.round ? `${CHROME.round} ${r.round}` : "", when]
    .filter(Boolean).join(" · ");
}

export function renderHome(ui) {
  const resume = ui.home?.resume ?? null;
  // Resume is the primary action whenever there is something to resume: a
  // player who left a game running is far more likely to be coming back to
  // it than starting another. With no save there is only one thing to do,
  // and it takes the green.
  // `grow: false` matters: .cta.grow is `flex: 1 1 0`, which is right in a
  // horizontal .cta-row and wrong here - in a COLUMN it makes the button's
  // flex-basis its height, and both buttons collapse to 26px. These are full
  // width by their own rule, not by growing.
  //
  // cta() returns an html STRING; raw() only marks one for interpolation, so
  // any concatenation has to happen before the marker, never after it (two
  // raw() markers added together stringify to "[object Object]").
  const newGame = cta({
    act: "home_new", label: h`${CHROME.newGame}`,
    tone: resume ? "plain" : "ok", grow: false,
  });
  // The stamp belongs to Resume - it says what you would be going back into -
  // so it sits directly under that button, not at the foot of the group where
  // it would read as a caption for both.
  const buttons = resume
    ? cta({ act: "home_resume", label: h`${CHROME.resumeGame}`, tone: "ok", grow: false })
      + h`<p class="body secondary home-stamp">${resumeMeta(resume)}</p>`
      + newGame
    : newGame;

  return h`<main class="home">
<div class="home-art" aria-hidden="true"></div>
<div class="home-plate">
<h1 class="home-wordmark">${CHROME.wordmark}</h1>
<p class="home-sub label">${CHROME.wordmarkSub}</p>
<div class="home-actions">${raw(buttons)}</div>
</div>
<p class="home-foot label">${CHROME.disclaimer}</p>
</main>`;
}
