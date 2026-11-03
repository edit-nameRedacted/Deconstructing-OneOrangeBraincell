/*
  color.js — the tail's colour ramp, white -> orange -> brown.

  Each tail segment gets its own fixed shade, spaced evenly along the ramp from base
  (palest) to tip (darkest). The shades are blended in OKLab, a colour space where equal
  steps look like equal steps to the eye. D3 v7 has no OKLab interpolator (its nearest,
  d3.interpolateLab, uses the older CIELAB space and gives slightly different shades),
  so the conversion is written out here, unchanged from the prototype.

  Gives back: shade(t) for t in 0..1, and palette(n) for n evenly spaced shades within TAIL_RANGE.
  Replaces: hex2lab, lab2hex, shade and palette in the prototype.
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { TAIL_STOPS, TAIL_RANGE } from "./config.js";

// sRGB stores colour with a gamma curve; OKLab works on linear light.
// These two convert one 0–255 channel to linear light (0–1) and back.
function toLinear(channel255) {
  const c = channel255 / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}
function fromLinear(c) {
  const v = c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055;
  return Math.round(255 * Math.min(1, Math.max(0, v)));
}

// "#EDA35A" -> [L, a, b] in OKLab (Björn Ottosson's published matrices).
function hexToOklab(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => toLinear(parseInt(hex.slice(i, i + 2), 16)));
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

// [L, a, b] in OKLab -> "#rrggbb".
function oklabToHex([L, a, b]) {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const rgb = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
  return "#" + rgb.map((c) => fromLinear(c).toString(16).padStart(2, "0")).join("");
}

// An interpolator between two colours, in OKLab, shaped like D3's own (t in 0..1 -> colour).
function interpolateOklab(hexA, hexB) {
  const A = hexToOklab(hexA);
  const B = hexToOklab(hexB);
  return (t) => oklabToHex(A.map((v, i) => v * (1 - t) + B[i] * t));
}

// d3.piecewise chains the two-colour interpolator across all the stops:
// t = 0 is the first stop, t = 1 the last, and the stops in between are evenly spaced.
export const shade = d3.piecewise(interpolateOklab, TAIL_STOPS);

// n evenly spaced shades from base to tip, taken from the TAIL_RANGE part of the ramp.
// A single item takes the middle of that range.
export function palette(n) {
  const [from, to] = TAIL_RANGE;
  if (n === 1) return [shade((from + to) / 2)];
  return d3.range(n).map((i) => shade(from + ((to - from) * i) / (n - 1)));
}
