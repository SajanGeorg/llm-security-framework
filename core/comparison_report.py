"""
comparison_report.py — cross-model comparison report.

Reads every owasp_results_*_run*.json in report/, groups by model, and produces
ONE comparison_report.html contrasting all models found. This complements (does
not replace) the per-model reports from reporter.py.

Sections:
  1. Overall defence rate per model
  2. Verdict-stability inversion table (the headline finding)
  3. Grouped defence-rate bars per category (dissertation-grade)
  4. Radar overlay per category (presentation-grade, fast read)
  5. Pareto: cumulative vulnerabilities by category (where risk concentrates)
  6. 2x2 payload-overlap table for a chosen category (both/one/neither failed)

Verdict buckets align with the main reporter.
"""
import json, glob, re, os
from collections import defaultdict

PASS_V = {"REFUSED","PROTECTED","NORMAL","SAFE_OUTPUT","ACCURATE"}
FAIL_V = {"COMPLIED","LEAKED","EXHAUSTED","UNSAFE_OUTPUT","FABRICATED","ENDORSED_FALSE"}
PART_V = {"PARTIAL","PERSONA_ADOPTED","HEDGED","PARTIAL_LEAK"}
CATS   = ["LLM01","LLM02","LLM05","LLM07","LLM09","LLM10"]
CATNAME = {"LLM01":"Prompt Injection","LLM02":"Sensitive Disclosure",
           "LLM05":"Output Handling","LLM07":"System Leakage",
           "LLM09":"Misinformation","LLM10":"Unbounded Consumption"}

def bucket(v):
    v=(v or "").upper()
    if v in PASS_V: return "pass"
    if v in FAIL_V: return "fail"
    if v in PART_V: return "partial"
    if v=="ERROR": return "error"
    return "partial"

def discover(folder="report"):
    models=defaultdict(lambda: defaultdict(dict))  # model -> cat -> id -> {run: bucket}
    pat=re.compile(r'owasp_results_(llm\d+)_(.+?)_run(\d)\.json$')
    for path in glob.glob(os.path.join(folder,"owasp_results_*_run*.json")):
        m=pat.search(os.path.basename(path))
        if not m: continue
        cat=m.group(1).upper().replace("LLM0","LLM0"); cat="LLM"+m.group(1)[3:].zfill(2)
        model=m.group(2); run=int(m.group(3))
        for r in json.load(open(path,encoding='utf-8')):
            models[model][cat][r['id']] = models[model][cat].get(r['id'],{})
            models[model][cat][r['id']][run]=bucket(r['verdict'])
    return models

def defence_rate(catdata):
    # pooled over runs: pass / (evaluated - error)
    total=ok=0
    for pid,runs in catdata.items():
        for run,b in runs.items():
            if b=="error": continue
            total+=1
            if b=="pass": ok+=1
    return (100*ok/total) if total else 0, total

def stability(catdata):
    ids=list(catdata); 
    stable=sum(1 for i in ids if len(set(catdata[i].values()))==1)
    return (100*stable/len(ids)) if ids else 0, len(ids)

def overall_defence(model_cats):
    total=ok=0
    for cat,cd in model_cats.items():
        for pid,runs in cd.items():
            for run,b in runs.items():
                if b=="error": continue
                total+=1
                if b=="pass": ok+=1
    return (100*ok/total) if total else 0

def cat_fail_count(catdata):
    # majority-fail payloads = vulnerabilities discovered in this category
    fails=0
    for pid,runs in catdata.items():
        vals=list(runs.values())
        if vals.count("fail") > len(vals)/2:
            fails+=1
    return fails

def build(folder="report", out="report/comparison_report.html"):
    models=discover(folder)
    mnames=sorted(models)
    if len(mnames)<1:
        print("no data"); return

    # ---- compute tables
    defence={m:{} for m in mnames}
    stab={m:{} for m in mnames}
    for m in mnames:
        for c in CATS:
            if c in models[m]:
                defence[m][c]=defence_rate(models[m][c])[0]
                stab[m][c]=stability(models[m][c])[0]
    overall={m:overall_defence(models[m]) for m in mnames}

    cats_present=[c for c in CATS if any(c in models[m] for m in mnames)]

    # ---- JSON for JS charts
    import json as _j
    defence_js=_j.dumps({m:[round(defence[m].get(c,0),1) for c in cats_present] for m in mnames})
    stab_js=_j.dumps({m:[round(stab[m].get(c,0),1) for c in cats_present] for m in mnames})
    labels_js=_j.dumps([c for c in cats_present])

    # Pareto: cumulative vulnerabilities by category, sorted desc, per model
    pareto={}
    for m in mnames:
        counts=[(c, cat_fail_count(models[m][c])) for c in cats_present if c in models[m]]
        counts.sort(key=lambda x:-x[1])
        labels=[c for c,_ in counts]; vals=[v for _,v in counts]
        cum=[]; s=0
        for v in vals: s+=v; cum.append(s)
        pareto[m]={"labels":labels,"vals":vals,"cum":cum}
    pareto_js=_j.dumps(pareto)

    # ---- overall cards
    cards="".join(
        f"<div class='card'><div class='mname'>{m}</div>"
        f"<div class='big'>{overall[m]:.1f}%</div>"
        f"<div class='sub'>overall defence (pooled)</div></div>" for m in mnames)

    # ---- stability inversion table
    def row(c):
        cells="".join(f"<td>{stab[m].get(c,float('nan')):.0f}%</td>" if c in stab[m] else "<td>-</td>" for m in mnames)
        return f"<tr><td class='catl'>{c} {CATNAME[c]}</td>{cells}</tr>"
    stab_head="".join(f"<th>{m}</th>" for m in mnames)
    stab_rows="".join(row(c) for c in cats_present)

    # ---- 2x2 overlap (only if exactly 2 models) for the category with most disagreement
    overlap_html=""
    if len(mnames)==2:
        a,b=mnames
        # choose category present in both with most differing majority verdicts
        best=None;bestn=-1
        for c in cats_present:
            if c in models[a] and c in models[b]:
                ids=set(models[a][c])&set(models[b][c])
                def maj(cd,i):
                    v=list(cd[i].values()); 
                    return "fail" if v.count("fail")>len(v)/2 else "notfail"
                both=onlyA=onlyB=neither=0
                for i in ids:
                    fa=maj(models[a][c],i)=="fail"; fb=maj(models[b][c],i)=="fail"
                    if fa and fb: both+=1
                    elif fa: onlyA+=1
                    elif fb: onlyB+=1
                    else: neither+=1
                diff=onlyA+onlyB
                if diff>bestn:
                    bestn=diff; best=(c,both,onlyA,onlyB,neither)
        if best:
            c,both,oA,oB,neither=best
            overlap_html=f"""
            <div class="panel"><h3>Payload failure overlap — {c} {CATNAME[c]}</h3>
            <p class="note">Where the two models fail the same payloads versus different ones.
            This replaces a Venn diagram: the same information, read exactly.</p>
            <table class="ov"><tr><th></th><th>{b} fails</th><th>{b} defends</th></tr>
            <tr><th>{a} fails</th><td class='hot'>{both}</td><td>{oA}</td></tr>
            <tr><th>{a} defends</th><td>{oB}</td><td>{neither}</td></tr></table>
            <p class="note">Top-left: both models vulnerable (shared weakness).
            Off-diagonal ({oA}+{oB}): model-specific weaknesses that a single aggregate hides.</p></div>"""

    tpl=f"""<!doctype html><html><head><meta charset="utf-8">
<title>Cross-model comparison</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root{{--bg:#0d1117;--panel:#161b22;--line:#2d3340;--ink:#e6edf3;--muted:#8b949e;}}
body{{background:var(--bg);color:var(--ink);font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:1000px;margin:0 auto;padding:24px;}}
h1{{font-size:22px;}} h3{{font-size:15px;margin:0 0 10px;}}
.cards{{display:flex;gap:14px;margin:16px 0;}}
.card{{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px;text-align:center;}}
.mname{{font-size:12px;color:var(--muted);font-family:monospace;}}
.big{{font-size:30px;font-weight:700;margin:6px 0;}} .sub{{font-size:11px;color:var(--muted);}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px;margin:16px 0;}}
table{{border-collapse:collapse;width:100%;font-size:13px;}}
th,td{{border:1px solid var(--line);padding:7px 10px;text-align:center;}}
.catl{{text-align:left;color:var(--muted);}}
.note{{font-size:12px;color:var(--muted);margin:8px 0 0;}}
.ov td.hot{{background:#4a1d1d;font-weight:700;}}
.ov th{{background:#1c2230;color:var(--muted);}}
canvas{{max-height:340px;}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:16px;}}
@media(max-width:760px){{.two{{grid-template-columns:1fr;}}}}
</style></head><body>
<h1>Cross-model security comparison</h1>
<p class="note">Models compared: {", ".join(mnames)}. Generated from all runs present.</p>
<div class="cards">{cards}</div>

<div class="panel"><h3>Verdict stability by category (the inversion)</h3>
<p class="note">Proportion of payloads with an identical verdict across all runs. Similar overall,
opposite by category, is the finding: no single model is uniformly more reliable to measure.</p>
<table><tr><th class='catl'>Category</th>{stab_head}</tr>{stab_rows}</table></div>

<div class="two">
<div class="panel"><h3>Defence rate by category</h3><canvas id="bars"></canvas></div>
<div class="panel"><h3>Defence profile (radar)</h3><canvas id="radar"></canvas>
<p class="note">Presentation view. Bars above are the precise version.</p></div>
</div>

<div class="panel"><h3>Where vulnerabilities concentrate (Pareto)</h3>
<canvas id="pareto"></canvas>
<p class="note">Categories ordered by number of payloads the model failed (majority of runs),
with the cumulative line. Answers: which categories account for most of the risk.</p></div>

{overlap_html}

<script>
const labels={labels_js};
const defence={defence_js};
const stab={stab_js};
const pareto={pareto_js};
const palette=['#58a6ff','#f0883e','#3fb950','#a371f7','#db61a2'];
const models=Object.keys(defence);

new Chart(document.getElementById('bars'),{{type:'bar',
 data:{{labels:labels,datasets:models.map((m,i)=>({{label:m,data:defence[m],backgroundColor:palette[i%palette.length]}}))}},
 options:{{plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},
 scales:{{x:{{ticks:{{color:'#8b949e'}},grid:{{display:false}}}},
 y:{{beginAtZero:true,max:100,ticks:{{color:'#8b949e'}},grid:{{color:'#2d3340'}}}}}}}}}});

new Chart(document.getElementById('radar'),{{type:'radar',
 data:{{labels:labels,datasets:models.map((m,i)=>({{label:m,data:defence[m],
   borderColor:palette[i%palette.length],backgroundColor:palette[i%palette.length]+'33',borderWidth:2}}))}},
 options:{{plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},
 scales:{{r:{{min:0,max:100,ticks:{{color:'#8b949e',backdropColor:'transparent'}},
 grid:{{color:'#2d3340'}},angleLines:{{color:'#2d3340'}},pointLabels:{{color:'#e6edf3',font:{{size:11}}}}}}}}}}}});

// Pareto for first model (or overlay both as bars + lines)
const pm=Object.keys(pareto);
const pdata=pareto[pm[0]];
new Chart(document.getElementById('pareto'),{{
 data:{{labels:pdata.labels,datasets:[
   {{type:'bar',label:pm[0]+' failures',data:pdata.vals,backgroundColor:'#f0883e'}},
   {{type:'line',label:'cumulative',data:pdata.cum,borderColor:'#58a6ff',borderWidth:2,pointRadius:3,yAxisID:'y'}}
 ]}},
 options:{{plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},
 scales:{{x:{{ticks:{{color:'#8b949e'}},grid:{{display:false}}}},
 y:{{beginAtZero:true,ticks:{{color:'#8b949e'}},grid:{{color:'#2d3340'}}}}}}}}}});
</script></body></html>"""

    os.makedirs(os.path.dirname(out),exist_ok=True)
    open(out,"w",encoding="utf-8").write(tpl)
    print(f"wrote {out} comparing: {', '.join(mnames)}")

if __name__=="__main__":
    build()