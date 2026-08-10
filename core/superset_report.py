"""
superset_report.py — ONE combined HTML: cross-model comparison on top, then each
model's full per-model report below in a collapsible section.

Place this file NEXT TO reporter.py (same folder) and run it. It imports the
existing reporter, so it inherits all its charts, styling, and any fixes you make
there. It does not duplicate reporter logic.

Output: report/superset_report.html

Requires reporter.py in the same directory (or on the Python path).
"""
import os, glob, re, json
from collections import defaultdict

import reporter as R   # your existing reporter.py

CATNAME = R.OWASP_NAMES


# ---------- comparison computations (reuse reporter's classify + load) ----------
def gather_by_model():
    """model -> list of rows (using reporter's own loader for consistency)."""
    models = R.discover()
    out = {}
    for mkey, paths in models.items():
        out[mkey] = R.load_rows(paths)
    return out


def cat_defence(rows):
    d = defaultdict(lambda: {"pass": 0, "ev": 0})
    for r in rows:
        if r["result"] == "error":
            continue
        c = r["owasp"]
        d[c]["ev"] += 1
        if r["result"] == "pass":
            d[c]["pass"] += 1
    return {c: R.pct(v["pass"], v["ev"]) for c, v in d.items()}


def cat_stability(rows):
    runs = sorted({r["run"] for r in rows})
    by_id = defaultdict(dict)
    for r in rows:
        by_id[(r["owasp"], r["id"])][r["run"]] = r["result"]
    per = defaultdict(lambda: {"s": 0, "t": 0})
    for (c, _), v in by_id.items():
        per[c]["t"] += 1
        if len(set(v.values())) == 1:
            per[c]["s"] += 1
    return {c: R.pct(v["s"], v["t"]) for c, v in per.items()}, len(runs)


def overall_defence(rows):
    ev = [r for r in rows if r["result"] != "error"]
    return R.pct(sum(1 for r in ev if r["result"] == "pass"), len(ev))


def majority_fail_ids(rows, cat):
    ids = defaultdict(list)
    for r in rows:
        if r["owasp"] == cat:
            ids[r["id"]].append(r["result"])
    fails = set()
    for i, vs in ids.items():
        if vs.count("fail") > len(vs) / 2:
            fails.add(i)
    return fails


def build_comparison(bymodel):
    mnames = sorted(bymodel)
    cats = [c for c in R.OWASP_NAMES if any(
        any(r["owasp"] == c for r in bymodel[m]) for m in mnames)]

    defence = {m: cat_defence(bymodel[m]) for m in mnames}
    stab = {}
    for m in mnames:
        stab[m], _ = cat_stability(bymodel[m])
    overall = {m: overall_defence(bymodel[m]) for m in mnames}

    labels = json.dumps(cats)
    defence_js = json.dumps({m: [round(defence[m].get(c, 0), 1) for c in cats] for m in mnames})

    # cards
    cards = "".join(
        f'<div class="card"><div class="k">{R.escape(m)}</div>'
        f'<div class="v" style="color:var(--pass)">{overall[m]:.1f}%</div>'
        f'<div class="s">overall defence (pooled)</div></div>' for m in mnames)

    # stability inversion table
    head = "".join(f"<th>{R.escape(m)}</th>" for m in mnames)
    rows_html = ""
    for c in cats:
        cells = "".join(
            f"<td>{stab[m].get(c):.0f}%</td>" if c in stab[m] else "<td>-</td>"
            for m in mnames)
        rows_html += f'<tr><td class="bar-label">{R.escape(R.owasp_label(c))}</td>{cells}</tr>'

    # pareto for first model
    pm = mnames[0]
    fails = [(c, len(majority_fail_ids(bymodel[pm], c))) for c in cats]
    fails.sort(key=lambda x: -x[1])
    p_labels = json.dumps([c for c, _ in fails])
    p_vals = json.dumps([v for _, v in fails])
    cum = []
    s = 0
    for _, v in fails:
        s += v
        cum.append(s)
    p_cum = json.dumps(cum)

    # 2x2 overlap if exactly 2 models
    overlap = ""
    if len(mnames) == 2:
        a, b = mnames
        best = None
        bestdiff = -1
        for c in cats:
            fa = majority_fail_ids(bymodel[a], c)
            fb = majority_fail_ids(bymodel[b], c)
            ids = {r["id"] for r in bymodel[a] if r["owasp"] == c} | \
                  {r["id"] for r in bymodel[b] if r["owasp"] == c}
            both = len(fa & fb)
            oA = len(fa - fb)
            oB = len(fb - fa)
            neither = len(ids) - both - oA - oB
            if oA + oB > bestdiff:
                bestdiff = oA + oB
                best = (c, both, oA, oB, neither)
        if best:
            c, both, oA, oB, neither = best
            overlap = f"""<div class="panel"><h3>Payload Failure Overlap &mdash; {R.escape(R.owasp_label(c))}</h3>
<p class="note">Where both models fail the same payloads versus different ones. This shows the
set-overlap information a Venn diagram would imply, read exactly as a table.</p>
<table><tr><th></th><th>{R.escape(b)} fails</th><th>{R.escape(b)} defends</th></tr>
<tr><td class="bar-label">{R.escape(a)} fails</td>
<td style="background:rgba(248,81,73,.18);font-weight:700;">{both}</td><td>{oA}</td></tr>
<tr><td class="bar-label">{R.escape(a)} defends</td><td>{oB}</td><td>{neither}</td></tr></table>
<p class="note">Top-left: shared weakness (both vulnerable). Off-diagonal ({oA}+{oB}):
model-specific weaknesses that a single aggregate defence rate conceals.</p></div>"""

    return f"""
<div class="eyebrow">Cross-Model Comparison</div>
<h1>Comparison: {" vs ".join(R.escape(m) for m in mnames)}</h1>
<div class="sub">Generated from all runs present. Per-model detail follows below.</div>
<div class="cards">{cards}</div>

<div class="panel"><h3>Verdict Stability by Category (the inversion)</h3>
<p class="note">Proportion of payloads with an identical verdict across all runs. Comparable
overall but opposite by category is the finding: no single model is uniformly more reliable
to measure.</p>
<table><thead><tr><th>Category</th>{head}</tr></thead><tbody>{rows_html}</tbody></table></div>

<div class="grid2">
<div class="panel"><h3>Defence Rate by Category</h3><div style="height:320px;"><canvas id="cmpBars"></canvas></div></div>
<div class="panel"><h3>Defence Profile (radar)</h3><div style="height:320px;"><canvas id="cmpRadar"></canvas></div>
<p class="note">Presentation view. The bars are the precise version of the same data.</p></div>
</div>

<div class="panel"><h3>Where Vulnerabilities Concentrate (Pareto)</h3>
<div style="height:300px;"><canvas id="cmpPareto"></canvas></div>
<p class="note">Categories ordered by number of payloads failed (majority of runs), with the
cumulative line. Answers which categories account for most of the risk.</p></div>

{overlap}

<script>
(function(){{
const labels={labels};const defence={defence_js};
const models=Object.keys(defence);
const palette=['#58a6ff','#f0883e','#3fb950','#a371f7','#db61a2'];
new Chart(document.getElementById('cmpBars'),{{type:'bar',
 data:{{labels:labels,datasets:models.map((m,i)=>({{label:m,data:defence[m],backgroundColor:palette[i%5]}}))}},
 options:{{maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},
 scales:{{x:{{ticks:{{color:'#8b949e'}},grid:{{display:false}}}},
 y:{{beginAtZero:true,max:100,ticks:{{color:'#8b949e'}},grid:{{color:'#2d3340'}}}}}}}}}});
new Chart(document.getElementById('cmpRadar'),{{type:'radar',
 data:{{labels:labels,datasets:models.map((m,i)=>({{label:m,data:defence[m],
  borderColor:palette[i%5],backgroundColor:palette[i%5]+'33',borderWidth:2}}))}},
 options:{{maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},
 scales:{{r:{{min:0,max:100,ticks:{{color:'#8b949e',backdropColor:'transparent'}},
 grid:{{color:'#2d3340'}},angleLines:{{color:'#2d3340'}},pointLabels:{{color:'#e6edf3'}}}}}}}}}});
new Chart(document.getElementById('cmpPareto'),{{
 data:{{labels:{p_labels},datasets:[
 {{type:'bar',label:'{R.escape(pm)} failures',data:{p_vals},backgroundColor:'#f0883e'}},
 {{type:'line',label:'cumulative',data:{p_cum},borderColor:'#58a6ff',borderWidth:2,pointRadius:3}}]}},
 options:{{maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},
 scales:{{x:{{ticks:{{color:'#8b949e'}},grid:{{display:false}}}},
 y:{{beginAtZero:true,ticks:{{color:'#8b949e'}},grid:{{color:'#2d3340'}}}}}}}}}});
}})();
</script>
"""


def build_superset(out="report/superset_report.html"):
    bymodel = gather_by_model()
    if not bymodel:
        print("no data in report/")
        return
    mnames = sorted(bymodel)

    comparison_html = build_comparison(bymodel)

    # each model's full report body, wrapped in a <details>
    per_model_sections = ""
    for m in mnames:
        rows = bymodel[m]
        full = R.render(m, rows)
        # extract just the inner <div class="wrap">...</div> body of the per-model report
        body = re.search(r'<div class="wrap">(.*)</div>\s*<script>', full, re.S)
        inner = body.group(1) if body else full
        # extract that report's trailing chart <script> (the second script block)
        scripts = re.findall(r'<script>(.*?)</script>', full, re.S)
        chart_script = scripts[-1] if scripts else ""
        per_model_sections += f"""
<details class="model-block"><summary>Full report &mdash; {R.escape(m)}</summary>
<div class="model-inner">{inner}</div>
<script>{chart_script}</script>
</details>"""

    # one document: shared CSS + JS from reporter, comparison on top, models below
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Superset Security Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>{R.CSS}
details.model-block{{margin:22px 0;border:1px solid var(--line);border-radius:12px;
background:var(--panel);}}
details.model-block>summary{{cursor:pointer;padding:16px 20px;font-size:15px;font-weight:650;
list-style:none;}}
details.model-block>summary::-webkit-details-marker{{display:none;}}
details.model-block>summary:before{{content:'\\25B8 ';color:var(--muted);}}
details.model-block[open]>summary:before{{content:'\\25BE ';}}
.model-inner{{padding:0 20px 20px;}}
.model-inner .wrap{{max-width:100%;padding:0;}}
</style></head><body>
<button id="themeBtn" onclick="toggleTheme()"
 style="position:fixed;top:16px;right:16px;z-index:99;background:var(--panel2);
 color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:8px 12px;
 font-size:12.5px;cursor:pointer;font-family:inherit;">Light mode</button>
<div class="wrap">
{comparison_html}
<div class="eyebrow" style="margin-top:40px;">Per-Model Detail</div>
<h1>Individual Model Reports</h1>
<div class="sub">Each model's complete report, expandable.</div>
{per_model_sections}
</div>
<script>{R.JS}</script>
</body></html>"""

    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(html)
    print(f"wrote {out}: comparison + {len(mnames)} model(s): {', '.join(mnames)}")


if __name__ == "__main__":
    build_superset()