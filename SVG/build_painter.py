"""Build the Cat Coat Painter page from its template, the kit and the measured white stages.

Usage: python3 build_painter.py painter_template.html cat_kit.svg white_stages.json tails/cat_tail.js cat_coat_painter.html
"""
import json, sys

tpl, kit, stages, tail_js, out = sys.argv[1:6]
S = json.load(open(stages))["white_pct_cumulative"]
# the page wants the share after each zone, without the leading 0
by_body = {b: v[1:] for b, v in S.items()} if isinstance(S, dict) else {"typical": S[1:]}
page = open(tpl, encoding="utf-8").read()
page = page.replace("__KIT__", open(kit, encoding="utf-8").read().strip())
page = page.replace("__STAGES__", json.dumps(by_body))
page = page.replace("__TAILJS__", open(tail_js, encoding="utf-8").read())
open(out, "w", encoding="utf-8").write(page)
print(f"wrote {out} ({len(page) // 1024} KB), bodies: {', '.join(by_body)}", file=sys.stderr)
