/* Cat tails for the cat kit: your two tail drawings, attached to each body, cut into labelled data segments.

   CatTail.draw(cat, options) puts a tail on the body showing in the kit's <svg id="cat"> and returns a controller.
   options:
     type      'long' | 'short'         which of your drawings
     length    0.3 – 1                  how much of it shows (the tip is rounded off where it ends)
     size      default 1.5              scale; 1 = life-size against the body, larger makes the data readable
     rings     true | false             tabby rings in the stripe colour (hidden when the kit's stripes are off)
     segments  [{ key, label, value, pct }]   one labelled segment per post variable, base to tip; pct 0–1
               shades the segment from --tail-lo (low) to --tail-hi (high). Omit for a plain tail.
     labels    true | false             segment labels beside the tail
     onSelect  (segment) => {}          called when a segment is clicked or chosen with Enter/Space
   controller.update(options), controller.select(key), controller.remove()

   Hovering a segment makes it bristle. The tail sits behind the body, entering at the gap in the haunch outline.
   Colours follow the kit's CSS variables: --cat-coat, --cat-stripes, --cat-outline, and --tail-lo / --tail-hi. */
(function () {
  const GEOM = __TAIL_GEOMETRY__;
  // Where the tail enters each body (kit units): the two ends of the opening in the haunch outline, upper first.
  // The chunky outline has no opening, so its tail starts just behind the line.
  const ATTACH = {
    typical: { up: [278, 421], low: [267, 447], size: 1 },
    kitten: { up: [226, 455], low: [215, 469], size: 0.7 },
    slender: { up: [280, 421], low: [281, 438], size: 0.95 },
    chunky: { up: [301, 422], low: [293, 446], size: 1.1 },
  };
  const SCALE = 0.62;      // drawing units -> kit units at size 1 (your long tail's base then matches the typical cat's opening)
  const SIZE = 1.5;        // default size: larger than life, so the data the tail carries can be read
  const INSET = 7;         // kit units at size 1: how far the base tucks in behind the body (grows with size)
  const BODY_CENTRE = [140, 330];
  const LINE = 3.8;        // outline width, kit units (matches the body outline)
  const SPIKE = 8;       // bristle length, kit units
  const SPIKE_GAP = 3.2;   // kit units between bristles
  const RINGS = [0.2, 0.36, 0.52, 0.67, 0.8];   // tabby rings, as fractions of the full tail
  const HIDDEN = 0.06;     // the first part of the tail is behind the body; segments start after it
  const NS = 'http://www.w3.org/2000/svg';

  const el = (name, attrs = {}, parent) => {
    const n = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.append(n);
    return n;
  };
  const f = (v) => +v.toFixed(2);
  const ord = (n) => n + ((n % 100 >= 11 && n % 100 <= 13) ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th'));

  // ----- geometry, in drawing units -----
  function prep(type) {
    const g = GEOM[type];
    const S = g.stroke;
    const at = (t) => {  // point at a fractional index along the stroke
      const i = Math.max(0, Math.min(S.length - 1, Math.floor(t))), j = Math.min(S.length - 1, i + 1), u = t - i;
      return [S[i][0] * (1 - u) + S[j][0] * u, S[i][1] * (1 - u) + S[j][1] * u];
    };
    // the run of stroke points between two fractional indices, ends included
    const run = (t0, t1) => {
      const out = [at(t0)];
      if (t1 >= t0) { for (let i = Math.ceil(t0); i < t1; i++) out.push(S[i]); }
      else { for (let i = Math.floor(t0); i > t1; i--) out.push(S[i]); }
      out.push(at(t1));
      return out;
    };
    // station at a fraction of the tail, interpolated between stored stations
    const st = g.stations;
    const station = (q) => {
      const x = q * (st.length - 1), i = Math.min(st.length - 2, Math.floor(x)), u = x - i;
      return [st[i][0] * (1 - u) + st[i + 1][0] * u, st[i][1] * (1 - u) + st[i + 1][1] * u];
    };
    const upper = S[0][1] < S[S.length - 1][1];  // is the stroke's start the upper end of the base?
    return { g, S, at, run, station, upper };
  }

  function resample(pts, n) {
    const d = [0];
    for (let i = 1; i < pts.length; i++) d.push(d[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    const L = d[d.length - 1] || 1, out = [];
    for (let k = 0; k < n; k++) {
      const t = (L * k) / (n - 1);
      let i = 1; while (i < d.length - 1 && d[i] < t) i++;
      const u = (t - d[i - 1]) / ((d[i] - d[i - 1]) || 1);
      out.push([pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * u, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * u]);
    }
    return out;
  }
  const len = (pts) => pts.reduce((s, p, i) => (i ? s + Math.hypot(p[0] - pts[i - 1][0], p[1] - pts[i - 1][1]) : 0), 0);

  // a band of the tail between two fractions q0 < q1, as one closed outline: edge A up, edge B back down.
  // If q1 is the visible end of a shortened tail, the end gets a rounded cap.
  function band(P, q0, q1, cap) {
    const [a0, b0] = P.station(q0), [a1, b1] = P.station(q1);
    const A = P.run(a0, a1), B = P.run(b1, b0);
    let C = [];
    if (cap) {  // half-round cap bulging toward the tip
      const pa = A[A.length - 1], pb = B[0], m = [(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2];
      const tipward = P.at((a1 + b1) / 2);
      let dx = tipward[0] - m[0], dy = tipward[1] - m[1]; const dl = Math.hypot(dx, dy) || 1; dx /= dl; dy /= dl;
      const r = Math.hypot(pa[0] - pb[0], pa[1] - pb[1]) / 2;
      for (let k = 1; k < 8; k++) {
        const ang = (Math.PI * k) / 8, ca = Math.cos(ang), sa = Math.sin(ang);
        const ux = (pa[0] - m[0]) / (r || 1), uy = (pa[1] - m[1]) / (r || 1);
        C.push([m[0] + r * (ux * ca + dx * sa), m[1] + r * (uy * ca + dy * sa)]);
      }
    }
    return { A, B, C };
  }

  const ptsD = (pts, close = true) => 'M' + pts.map((p) => f(p[0]) + ',' + f(p[1])).join(' L') + (close ? ' Z' : '');

  // the same band with bristles: both long edges zig-zag outward; equal point counts so the two shapes can morph
  function bandShapes(bd, s) {
    const step = SPIKE_GAP / s, spike = SPIKE / s;
    const nA = Math.max(6, Math.round(len(bd.A) / step) | 1), nB = Math.max(6, Math.round(len(bd.B) / step) | 1);
    const A = resample(bd.A, nA), B = resample(bd.B, nB);
    const ring = [...A, ...bd.C, ...B];
    // orientation, so "outward" is known
    let area = 0;
    for (let i = 0; i < ring.length; i++) { const p = ring[i], q = ring[(i + 1) % ring.length]; area += p[0] * q[1] - q[0] * p[1]; }
    const sgn = area > 0 ? -1 : 1;
    const out = (pts, i) => {
      const p = pts[Math.max(0, i - 1)], q = pts[Math.min(pts.length - 1, i + 1)];
      let tx = q[0] - p[0], ty = q[1] - p[1]; const l = Math.hypot(tx, ty) || 1; tx /= l; ty /= l;
      return [sgn * ty, -sgn * tx];
    };
    const zig = (pts) => pts.map((p, i) => {
      if (i === 0 || i === pts.length - 1) return p;
      const k = i % 2 ? spike : spike * 0.15, n = out(pts, i);
      return [p[0] + n[0] * k, p[1] + n[1] * k];
    });
    const C = bd.C.map((p, i) => { const n = out(bd.C, i); return [p[0] + n[0] * spike * (i % 2 ? 1 : 0.3), p[1] + n[1] * spike * (i % 2 ? 1 : 0.3)]; });
    return { smooth: ptsD(ring), bristled: ptsD([...zig(A), ...C, ...zig(B)]) };
  }

  // ----- placement on the body -----
  function placement(P, body, size) {
    const at = ATTACH[body] || ATTACH.typical;
    const s = SCALE * at.size * size;
    const inset = INSET * size;
    const S = P.S, U = P.upper ? S[0] : S[S.length - 1], Lw = P.upper ? S[S.length - 1] : S[0];
    const va = [Lw[0] - U[0], Lw[1] - U[1]], vk = [at.low[0] - at.up[0], at.low[1] - at.up[1]];
    const th = Math.atan2(vk[1], vk[0]) - Math.atan2(va[1], va[0]);
    const c = Math.cos(th) * s, sn = Math.sin(th) * s;
    const ma = [(U[0] + Lw[0]) / 2, (U[1] + Lw[1]) / 2], mk = [(at.up[0] + at.low[0]) / 2, (at.up[1] + at.low[1]) / 2];
    let nx = -vk[1], ny = vk[0]; const nl = Math.hypot(nx, ny); nx /= nl; ny /= nl;
    if ((BODY_CENTRE[0] - mk[0]) * nx + (BODY_CENTRE[1] - mk[1]) * ny < 0) { nx = -nx; ny = -ny; }
    const tx = mk[0] + nx * inset - (c * ma[0] - sn * ma[1]), ty = mk[1] + ny * inset - (sn * ma[0] + c * ma[1]);
    const M = [c, sn, -sn, c, tx, ty];
    return { s, M, apply: (p) => [M[0] * p[0] + M[2] * p[1] + M[4], M[1] * p[0] + M[3] * p[1] + M[5]], out: [-nx, -ny] };
  }

  // ----- drawing -----
  const STYLE = `
  .cat-tail .t-coat { fill: var(--cat-coat, #E8913A); }
  .cat-tail .t-ring { fill: var(--cat-stripes, #B4561E); }
  #cat[data-stripes="off"] .cat-tail .t-ring { display: none; }
  .cat-tail .t-line { fill: none; stroke: var(--cat-outline, #1B1714); stroke-linecap: round; stroke-linejoin: round; }
  .cat-tail .t-seg { stroke: none; cursor: pointer; outline: none; }
  .cat-tail .t-hl { stroke: var(--cat-outline, #1B1714); stroke-linejoin: round; pointer-events: none;
    transition: d 180ms ease-out; }
  .cat-tail .t-cut { stroke: var(--cat-outline, #1B1714); stroke-opacity: 0.35; fill: none; pointer-events: none; }
  .cat-tail .t-label { font: 500 13px/1 var(--tail-font, system-ui, sans-serif); fill: var(--tail-label, #5C564F); pointer-events: none; }
  .cat-tail .t-label.is-on { fill: var(--tail-label-on, var(--cat-outline, #1B1714)); font-weight: 700; }
  .cat-tail .t-lead { stroke: var(--tail-label, #5C564F); stroke-width: 0.8; stroke-opacity: 0.7; }
  @media (prefers-reduced-motion: reduce) { .cat-tail .t-hl { transition: none; } }`;

  function ensureStyle(cat) {
    if (cat.querySelector('style[data-cat-tail]')) return;
    const st = el('style', { 'data-cat-tail': '' });
    st.textContent = STYLE;
    (cat.querySelector('defs') || cat).append(st);
  }

  function draw(cat, options = {}) {
    let opts = { type: 'long', length: 1, size: SIZE, rings: true, segments: null, labels: true, onSelect: null, ...options };
    let root = null, labelsG = null, selected = null, sel = null, hov = null;
    ensureStyle(cat);

    function render() {
      root?.remove(); labelsG?.remove();
      const bodyKey = cat.dataset.body || 'typical';
      const bodyG = cat.querySelector(`.body[data-body="${bodyKey}"]`) || cat;
      const P = prep(opts.type);
      const pl = placement(P, bodyKey, opts.size);
      const s = pl.s;
      const q1 = Math.max(0.3, Math.min(1, opts.length));
      const short = q1 < 0.999;
      root = el('g', { class: 'cat-tail', 'data-tail': opts.type, transform: `matrix(${pl.M.map(f).join(' ')})` });
      bodyG.insertBefore(root, bodyG.firstChild);  // behind the body
      const whole = band(P, 0, q1, short);
      el('path', { class: 't-coat', d: ptsD([...whole.A, ...whole.C, ...whole.B]) }, root);

      if (opts.rings) {
        for (const r of RINGS) {
          const a = r, b = r + 0.055;
          if (b > q1) continue;
          const bd = band(P, a, b, false);
          el('path', { class: 't-ring', d: ptsD([...bd.A, ...bd.B]) }, root);
        }
      }

      const segs = opts.segments || [];
      const segG = el('g', { class: 't-segs' }, root);
      if (segs.length) {
        labelsG = el('g', { class: 'cat-tail t-labels' });
        bodyG.append(labelsG);  // labels sit above everything, in kit units
      }
      const nodes = [];
      segs.forEach((sg, i) => {
        const a = HIDDEN + ((q1 - HIDDEN) * i) / segs.length, b = HIDDEN + ((q1 - HIDDEN) * (i + 1)) / segs.length;
        const last = i === segs.length - 1;
        const bd = band(P, a, b, last && short);
        const shapes = bandShapes(bd, s);
        const pct = Math.max(0, Math.min(1, sg.pct ?? 0.5));
        const p = el('path', {
          class: 't-seg', d: shapes.smooth, tabindex: '0', role: 'button', 'data-key': sg.key,
          'aria-label': `${sg.label}${sg.value != null ? ': ' + sg.value : ''}${sg.pct != null ? ', ' + ord(Math.round(pct * 100)) + ' percentile' : ''}`,
        }, segG);
        p.style.fill = `color-mix(in oklab, var(--tail-hi, #9A3F0C) ${Math.round(pct * 100)}%, var(--tail-lo, #FCE6CC))`;
        const ttl = el('title', {}, p); ttl.textContent = p.getAttribute('aria-label');
        {  // a light cut where this segment starts
          const [ca, cb] = P.station(a);
          el('path', { class: 't-cut', d: ptsD([P.at(ca), P.at(cb)], false), 'stroke-width': f(0.8 / s) }, root);
        }
        // label beside the outer edge of the segment's middle
        let lab = null;
        if (opts.labels) {
          const [ma, mb] = P.station((a + b) / 2);
          const pa = pl.apply(P.at(ma)), pb = pl.apply(P.at(mb));
          const far = (q) => Math.hypot(q[0] - BODY_CENTRE[0], q[1] - BODY_CENTRE[1]);
          const edge = far(pa) > far(pb) ? pa : pb, other = edge === pa ? pb : pa;
          let ox = edge[0] - other[0], oy = edge[1] - other[1]; const ol = Math.hypot(ox, oy) || 1; ox /= ol; oy /= ol;
          const lx = edge[0] + ox * 14, ly = edge[1] + oy * 14;
          el('line', { class: 't-lead', x1: f(edge[0] + ox * 2), y1: f(edge[1] + oy * 2), x2: f(lx - ox * 2), y2: f(ly - oy * 2) }, labelsG);
          lab = el('text', { class: 't-label', x: f(lx + (ox >= 0 ? 1.5 : -1.5)), y: f(ly + 4), 'text-anchor': ox >= 0 ? 'start' : 'end' }, labelsG);
          lab.textContent = sg.label;
        }
        const node = { key: sg.key, p, lab, shapes };
        const on = () => { bristle(hov, node); lab?.classList.add('is-on'); };
        const off = () => { hov.style.display = 'none'; if (selected !== sg.key) lab?.classList.remove('is-on'); };
        const choose = () => { select(sg.key); opts.onSelect?.(sg); };
        p.addEventListener('pointerenter', on); p.addEventListener('pointerleave', off);
        p.addEventListener('focus', on); p.addEventListener('blur', off);
        p.addEventListener('click', choose);
        p.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(); } });
        nodes.push(node);
      });
      root._nodes = nodes;

      // the outline: your drawn edges (not the base, which is under the body), rounded off if shortened
      const line = band(P, 0, q1, short);
      el('path', { class: 't-line', d: ptsD([...line.A, ...line.C, ...line.B], false), 'stroke-width': f(LINE / s) }, root);
      // bristling copies on top: one for the chosen segment, one for the segment under the pointer
      sel = el('path', { class: 't-hl', 'stroke-width': f(LINE * 0.8 / s) }, root); sel.style.display = 'none';
      hov = el('path', { class: 't-hl', 'stroke-width': f(LINE * 0.8 / s) }, root); hov.style.display = 'none';
      if (selected) select(selected);
    }

    // show a segment's bristled shape on an overlay, growing out from its smooth shape
    function bristle(ov, node) {
      ov.style.fill = node.p.style.fill;
      ov.style.transition = 'none';
      ov.style.d = `path("${node.shapes.smooth}")`;
      ov.style.display = '';
      ov.getBoundingClientRect();
      ov.style.transition = '';
      ov.style.d = `path("${node.shapes.bristled}")`;
    }

    function select(key) {
      selected = key;
      const n = (root?._nodes || []).find((x) => x.key === key);
      for (const x of root?._nodes || []) x.lab?.classList.toggle('is-on', x === n);
      if (n) bristle(sel, n); else if (sel) sel.style.display = 'none';
    }

    render();
    return {
      update(o) { opts = { ...opts, ...o }; render(); },
      select,
      remove() { root?.remove(); labelsG?.remove(); },
    };
  }

  window.CatTail = { draw, ATTACH, SIZE };
})();
