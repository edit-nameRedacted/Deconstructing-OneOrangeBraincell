/*
  state.js — the one object that says what the page is showing.

    arrange  the category shown as the row of cats: a hand-code key ("braincell")
             or "tail:<variable>" for a "Tails of" view
    vars     the tail variables drawn as segments (a Set of keys)
    stripes  the hand codes drawn as tail stripes (a Set of keys)
    zoom     index of the cat whose tail is zoomed, or null for the row
    sel      the selected segment ("score") or stripe ("code:failure"), or null
    model    true while the zoomed cat's tail is shown as two models read it (modelView.js)

  Nothing changes the page directly. Controls call set({...}); set() works out which keys
  actually changed and tells every subscriber, and main.js decides what to redraw from that.

  Replaces: the prototype's `state` object and the render()/fixMix()/closeZoom() calls that each
  control made in its own order.
*/

export function createStore(initial) {
  const state = { ...initial };
  const subscribers = [];

  // Change some keys at once. Subscribers hear about it once, with the set of keys that changed.
  function set(patch) {
    const changed = new Set();
    for (const [key, value] of Object.entries(patch)) {
      if (state[key] !== value) {
        state[key] = value;
        changed.add(key);
      }
    }
    if (changed.size > 0) for (const fn of subscribers) fn(state, changed);
  }

  function subscribe(fn) {
    subscribers.push(fn);
  }

  return { state, set, subscribe };
}
