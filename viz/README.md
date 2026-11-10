# viz: first prototype (superseded)

The single-file version of the typical-cat page, kept for reference. The current page is in `viz_d3/`.

- `oobc_cat_viz.html`: open it directly in a browser, no server needed
- Rebuild: `python oobc_archive/viz/build_viz_data.py`, then `python viz/build_viz.py` (fills `viz_template.html`
  with the data, the kit and `cat_tail_viz_template.js`)
