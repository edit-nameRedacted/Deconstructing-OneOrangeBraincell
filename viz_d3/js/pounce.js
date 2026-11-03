/*
  pounce.js — the cat chases its own tail (AC's storyboard sketch, 2026-11-02).

  Plays when "Chase this tail" is pressed in the tail view, as the bridge from the zoomed tail to
  the regrouped row. The stages follow the sketch (their times are POUNCE in config.js):
    1. settle   the details panel and labels fade; the cat appears on the right, sitting, eyes
                half shut, while its big zoomed tail sways on the left
    2. notice   its eyes snap open
    3. crouch   it squashes down and wiggles its rear (head still, eyes on the tail); its own
                little tail twitches
    4. leap     wide, wonky eyes; it leaps at the tail and toward the viewer, growing until it
                fills the screen, while the big tail whips away off the left edge
       swap     at the end of the leap, with the cat covering the screen, the page regroups
                underneath (onSwap)
    5. clear    the cat sails on past the viewer and fades, and the new row shows

  How it is drawn:
    - The cat is a fresh copy of the zoomed cat (kit + its row-sized tail) in an overlay laid over
      the page. The overlay also swallows clicks, so nothing is pressed twice mid-pounce.
    - The big tail is the tail view's own svg, moved with a CSS transform.
    - One d3.timer drives everything: on every frame, poseAt(ms) works out where each piece is at
      that moment, from the stage times alone. A single function of time is easier to read and to
      tune than a chain of transitions, and it can never get out of step.

  Skipping: a click or a key press jumps straight to the regrouped row. Under
  prefers-reduced-motion the pounce doesn't play at all.

  Takes: the zoomed cat, the view it belongs to, the kit, the tail geometry, the row's viewBox,
  and onSwap() (regroups the page).
  Gives back: nothing; pounce(...) runs to the end by itself.
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { POUNCE } from "./config.js";
import { cloneCat, tilt, boxOf, bodyOf } from "./kit.js";
import { drawTail } from "./tail.js";
import { tailOptions } from "./catView.js";

const $ = (id) => document.getElementById(id);

export function pounce({ cat, view, kit, geometry, rowViewBox, onSwap }) {
  const tailSvg = document.querySelector("#zoom-stage svg");
  if (!cat || !tailSvg || prefersReducedMotion()) {
    onSwap();
    return;
  }
  const T = POUNCE;

  // ---- The pieces that move or fade ----
  const main = document.querySelector("main");
  const panel = $("info");
  const head = document.querySelector(".zoom-head");
  const labels = tailSvg.querySelector(".t-labels");

  // ---- Where things are on screen at the start (px, viewport coordinates) ----
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  // On a phone the Chase button is below the tail, so the tail may be scrolled out of sight:
  // bring it back into view first (instantly, so the measurements below are of where it ends up).
  const stageTop = $("zoom-stage").getBoundingClientRect().top;
  if (stageTop < 0 || stageTop > vh * 0.5) $("zoom").scrollIntoView({ block: "start", behavior: "instant" });
  const stageBox = $("zoom-stage").getBoundingClientRect();
  const panelBox = panel.getBoundingClientRect();
  const tailBox = tailSvg.querySelector(".cat-tail").getBoundingClientRect();
  const svgBox = tailSvg.getBoundingClientRect();

  // The cat sits where the details panel was (beside the tail, as in the sketch). On a narrow
  // screen the panel is below the tail, so the cat sits to the right of the tail, level with
  // its base.
  const sideBySide = panelBox.width > 0 && panelBox.left >= stageBox.right - 10;
  // No taller than most of the tail, so the tail still looks big beside it.
  const catHeight = Math.min(T.catPx, stageBox.height * 0.35, tailBox.height * 0.7);
  const catWidth = catHeight * (rowViewBox[2] / rowViewBox[3]);
  let baseX = sideBySide ? panelBox.left + panelBox.width * 0.45 : tailBox.right + (vw - tailBox.right) * 0.45;
  const baseY = sideBySide ? stageBox.top + stageBox.height * 0.72 : tailBox.bottom;

  // Where the leap ends: the cat's feet below the screen, under the middle of the tail, and the
  // cat big enough to cover the screen from top to bottom.
  const targetX = tailBox.left + tailBox.width / 2;
  const targetY = vh * 1.25;
  const fullScale = (vh * 1.6) / catHeight;

  // The big tail turns about its base (the lower-left corner of its box).
  tailSvg.style.transformOrigin = `${tailBox.left - svgBox.left}px ${tailBox.bottom - svgBox.top}px`;

  // ---- The overlay and the cat ----
  const overlay = d3.select(document.body).append("div").attr("class", "pounce").attr("aria-hidden", "true");
  // The holder sits with its bottom middle on the cat's base point; the leap moves and scales it.
  const holder = overlay.append("div").attr("class", "pounce-cat")
    .style("left", `${baseX - catWidth / 2}px`).style("top", `${baseY - catHeight}px`)
    .style("width", `${catWidth}px`).style("height", `${catHeight}px`);
  const svg = cloneCat(kit, cat.look, T.eyesCalm);
  svg.setAttribute("viewBox", rowViewBox.join(" "));
  holder.node().append(svg);
  tilt(svg);                                   // the svg must be on the page to be measured
  // The frame includes the tail, which sticks out to the right, so the body's middle is left of
  // the frame's middle. Measure it (before the tail is drawn) and make it the point the cat
  // stands on, grows from and wiggles about.
  const bodyBox = boxOf(svg, [bodyOf(svg)]);
  const middle = (bodyBox[0] + bodyBox[2] / 2 - rowViewBox[0]) / rowViewBox[2];   // 0-1 across
  baseX = Math.min(baseX, vw - (1 - middle) * catWidth - 8);   // keep its own tail on screen
  holder.style("left", `${baseX - middle * catWidth}px`).style("transform-origin", `${middle * 100}% 100%`);
  svg.style.transformOrigin = `${middle * 100}% 0%`;
  drawTail(svg, tailOptions(cat, view, geometry));
  // Wrap the cat's own tail in a group of its own, so it can twitch about its base without
  // disturbing the transform that places it on the body.
  const ownTail = svg.querySelector(".cat-tail");
  const twitch = document.createElementNS("http://www.w3.org/2000/svg", "g");
  twitch.setAttribute("class", "pounce-twitch");
  ownTail.before(twitch);
  twitch.append(ownTail);

  // ---- Running it ----
  let swapped = false;
  const timer = d3.timer((ms) => {
    poseAt(ms);
    if (ms >= T.leap && !swapped) swap();
    if (ms >= T.clear) finish();
  });
  // Any click or key press skips to the end (keydown in the capture phase, so Esc doesn't also
  // reach main.js's handler; the regroup has already been asked for).
  overlay.on("pointerdown", finish);
  window.addEventListener("keydown", skipKey, true);

  // Where everything is, `ms` after the button was pressed.
  function poseAt(ms) {
    // Progress through a time window, 0 before it and 1 after it.
    const through = (from, to) => Math.max(0, Math.min(1, (ms - from) / (to - from)));
    const wave = (period) => Math.sin((2 * Math.PI * ms) / period);

    // 1. Settle: the panel, heading and labels fade; the cat fades in, dropping a few pixels.
    const settled = d3.easeCubicOut(through(0, T.settle));
    for (const el of [panel, head, labels]) if (el) el.style.opacity = 1 - settled;
    let opacity = settled;
    let dx = 0;
    let dy = (1 - settled) * -12;

    // 2. Notice: eyes open, with a small start.
    let sx = 1, sy = 1;
    const start = Math.sin(Math.PI * through(T.notice, T.notice + 160));
    sy += 0.06 * start;

    // 3. Crouch: squash down, wiggle the rear, then squash a little more just before the leap.
    const crouchFrom = T.notice + 150;
    const squash = d3.easeCubicOut(through(crouchFrom, crouchFrom + 300));
    const windUp = d3.easeCubicIn(through(T.crouch - 160, T.crouch));
    const leapT = through(T.crouch, T.leap);
    const unsquash = 1 - d3.easeCubicOut(through(T.crouch, T.crouch + 0.25 * (T.leap - T.crouch)));
    sy -= (0.14 * squash + 0.06 * windUp) * unsquash;
    sx += (0.07 * squash + 0.03 * windUp) * unsquash;
    const wiggleFrom = crouchFrom + 300;
    const wiggleTo = T.crouch - 120;
    const wiggleT = through(wiggleFrom, wiggleTo);
    const wiggle = wiggleT > 0 && wiggleT < 1 ? 5 * Math.sin(Math.PI * wiggleT) * wave(200) : 0;

    // 4. Leap. The cat comes toward the viewer, so it grows the way a thing approaching does:
    // slowly at first, then fast. `depth` runs 0 -> 1 along with that growth.
    let scale = 1 / (1 - (1 - 1 / fullScale) * leapT);
    const depth = (scale - 1) / (fullScale - 1);
    // Across: it covers most of the distance to the tail early, while still small, so the leap
    // reads as going AT the tail. Down: its feet drop below the screen only as it nears the
    // viewer. Plus an arc on the way.
    dx += (targetX - baseX) * d3.easeCubicOut(leapT);
    dy += (targetY - baseY) * depth - vh * 0.1 * Math.sin(Math.PI * leapT);
    const stretch = Math.sin(Math.PI * leapT);
    sy *= 1 + 0.18 * stretch;
    sx *= 1 - 0.08 * stretch;
    let turn = -14 * stretch;                            // leaning into the leap

    // 5. Clear: the cat keeps coming, slides past to the left and fades.
    const cleared = through(T.leap, T.clear);
    scale *= 1 + 1.5 * d3.easeCubicIn(cleared);
    dx -= vw * 0.25 * cleared;
    opacity *= 1 - d3.easeQuadOut(cleared);

    // The eyes for this moment: half shut, then its own (or the kit's ordinary eyes, if its own are
    // the half-shut ones), then wide and wonky once it commits.
    const openEyes = cat.eyes === T.eyesCalm ? "original" : cat.eyes;
    const eyes = ms < T.notice ? T.eyesCalm : ms < T.crouch ? openEyes : T.eyesPounce;
    if (svg.dataset.eyes !== eyes) svg.dataset.eyes = eyes;

    holder
      .style("opacity", opacity)
      .style("transform", `translate(${dx}px, ${dy}px) rotate(${turn}deg) scale(${scale * sx}, ${scale * sy})`);
    // The wiggle turns the cat about the top of its frame, so the head stays put and the rear swings.
    svg.style.transform = `rotate(${wiggle}deg)`;
    // Its own tail: twitches while it watches, streams back in the leap.
    const twitchAngle = ms < T.crouch ? 8 * wave(320) * through(T.notice, T.notice + 200) : -12 * leapT;
    twitch.style.transform = `rotate(${twitchAngle}deg)`;

    // The big tail sways (faster once the cat has seen it), then whips away to the left.
    const sway = (ms < T.notice ? 3 * wave(900) : 4 * wave(420)) * through(0, 300);
    const escape = d3.easeCubicIn(through(T.crouch + 0.1 * (T.leap - T.crouch), T.crouch + 0.65 * (T.leap - T.crouch)));
    tailSvg.style.transform = `translateX(${-escape * (tailBox.right + 80)}px) rotate(${sway * (1 - escape) - 30 * escape}deg)`;

    // The page fades out under the cat as it arrives, and back in (regrouped) as it leaves.
    const pageOut = d3.easeQuadIn(through(T.crouch + 0.55 * (T.leap - T.crouch), T.leap));
    const pageIn = d3.easeQuadOut(cleared);
    main.style.opacity = ms < T.leap ? 1 - pageOut : pageIn;
  }

  // Put the tail view back as it was (it is hidden by the regroup, but the panel and heading are
  // reused the next time a tail is opened), then regroup.
  function swap() {
    swapped = true;
    for (const el of [panel, head, labels]) if (el) el.style.opacity = "";
    tailSvg.style.transform = "";
    tailSvg.style.transformOrigin = "";
    onSwap();
  }

  function finish() {
    timer.stop();
    window.removeEventListener("keydown", skipKey, true);
    if (!swapped) swap();
    main.style.opacity = "";
    overlay.remove();
  }

  function skipKey(event) {
    if (event.repeat) return;
    event.stopPropagation();
    finish();
  }
}

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
