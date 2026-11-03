/*
  intro.js — the opening screen (what r/OneOrangeBraincell is, and what the project is).

  It covers the page when it loads; the cats are drawn underneath it, so they are ready the moment
  it closes. "Meet the cats" or Esc closes it; the About button in the heading opens it again.
  The text itself is in index.html.
*/
const FADE_MS = 250;

export function setupIntro() {
  const intro = document.getElementById("intro");
  const go = document.getElementById("intro-go");
  const about = document.getElementById("about");

  function open() {
    intro.hidden = false;
    intro.classList.remove("leaving");
    intro.scrollTop = 0;
    go.focus({ preventScroll: true });
  }

  function close() {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    intro.classList.add("leaving");                 // CSS fades it out
    setTimeout(() => { intro.hidden = true; }, reduced ? 0 : FADE_MS);
    document.getElementById("arrange").focus({ preventScroll: true });
  }

  go.addEventListener("click", close);
  about.addEventListener("click", open);
  // Esc closes the intro; stopPropagation keeps the page's own Esc (close the zoom) out of it.
  intro.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { event.stopPropagation(); close(); }
  });

  go.focus({ preventScroll: true });
}
