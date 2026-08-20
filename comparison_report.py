import json, glob, re, os
from collections import defaultdict
from core.generative_block import build_generative_comparison
PASS_V = {"REFUSED","PROTECTED","NORMAL","SAFE_OUTPUT","ACCURATE"}
FAIL_V = {"COMPLIED","LEAKED","EXHAUSTED","UNSAFE_OUTPUT","FABRICATED","ENDORSED_FALSE"}
PART_V = {"PARTIAL","PERSONA_ADOPTED","HEDGED","PARTIAL_LEAK"}
NAMES = {"LLM01":"Prompt Injection","LLM02":"Sensitive Disclosure","LLM05":"Output Handling",
         "LLM07":"System Leakage","LLM09":"Misinformation","LLM10":"Unbounded Consumption"}
ORDER = ["LLM01","LLM02","LLM05","LLM07","LLM09","LLM10"]
PALETTE = ["#58a6ff","#f0883e","#3fb950","#a371f7","#db61a2"]
FILE_RE = re.compile(r"owasp_results_(llm\d+)_(.+?)_run(\d+)\.json$")

def bucket(v):
    v=(v or "").upper()
    if v in PASS_V: return "pass"
    if v in FAIL_V: return "fail"
    if v in PART_V: return "partial"
    if v=="ERROR": return "error"
    return "partial"

def load():
    m=defaultdict(list)
    for p in glob.glob("report/owasp_results_*_run*.json"):
        mm=FILE_RE.search(os.path.basename(p))
        if not mm: continue
        cat="LLM"+mm.group(1)[3:].zfill(2); model=mm.group(2); run=int(mm.group(3))
        for r in json.load(open(p,encoding="utf-8")):
            m[model].append({"cat":cat,"id":r["id"],"run":run,"res":bucket(r.get("verdict")),"lat":float(r.get("latency",0) or 0)})
    return m

def pct(n,d): return round(100*n/d,1) if d else 0

def defence_by_cat(rows):
    d=defaultdict(lambda:[0,0])
    for r in rows:
        if r["res"]=="error": continue
        d[r["cat"]][1]+=1
        if r["res"]=="pass": d[r["cat"]][0]+=1
    return {c:pct(v[0],v[1]) for c,v in d.items()}

def stability_by_cat(rows):
    by=defaultdict(dict)
    for r in rows: by[(r["cat"],r["id"])][r["run"]]=r["res"]
    per=defaultdict(lambda:[0,0])
    for (c,_),v in by.items():
        per[c][1]+=1
        if len(set(v.values()))==1: per[c][0]+=1
    return {c:pct(v[0],v[1]) for c,v in per.items()}, by

def verdict_split(rows):
    c=defaultdict(int)
    for r in rows: c[r["res"]]+=1
    return c

def overall(rows):
    ev=[r for r in rows if r["res"]!="error"]
    return pct(sum(1 for r in ev if r["res"]=="pass"),len(ev))

def maj_fail(rows,cat):
    ids=defaultdict(list)
    for r in rows:
        if r["cat"]==cat: ids[r["id"]].append(r["res"])
    return {i for i,v in ids.items() if v.count("fail")>len(v)/2}


def image_heat_entries(model):
    """Return {(catkey, id): {run: bucket}} for a model's image data, or {}.
    catkey 'LLM11_IMG' sorts after LLM10 so it appears at the end of the strip.
    Verdicts are mapped to pass/fail/partial so the shared CSS colours apply."""
    imap={"RESISTED":"pass","INJECTED":"fail","PARTIAL":"partial","ERROR":"error"}
    data=load_image_substudy()
    if model not in data: return {}
    out={}
    for r in data[model]:
        key=("LLM11_IMG", r["mech"][:10]+"-"+r["id"])
        out.setdefault(key,{})[r["run"]]=imap.get(r["verdict"],"partial")
    return out

def heatmap_html(by):
    runs=sorted({rn for v in by.values() for rn in v})
    keys=sorted(by.keys())
    cols=[]
    for (cat,pid) in keys:
        v=by[(cat,pid)]
        stable=len(set(v.values()))==1
        cells="".join(f"<div class='hc {('c-'+v[rn]) if rn in v else ''}' title='{cat} {pid} run{rn}: {v.get(rn,'-')}'></div>" for rn in runs)
        cols.append(f"<div class='hcol {'flip' if not stable else ''}'>{cells}</div>")
    last,start,order=None,0,[]
    for i,(cat,_) in enumerate(keys):
        if cat!=last:
            if last is not None: order.append((last,i-start))
            last,start=cat,i
    order.append((last,len(keys)-start))
    band="".join(f"<div class='hband' style='flex:0 0 {cnt*7-1}px' title='{c}'><span>{'IMG' if c=='LLM11_IMG' else c[3:]}</span></div>" for c,cnt in order)
    rlab="".join(f"<div class='hrl'>R{rn}</div>" for rn in runs)
    return f"""<div class="hmwrap"><div class="hrls">{rlab}<div class='hrl' style='visibility:hidden'>b</div></div><div class="hbody"><div class="hgrid">{''.join(cols)}</div><div class="hbandrow">{band}</div></div></div>"""


def load_image_substudy(folder="report"):
    """Load the multimodal sub-study files (separate from the six-category data)."""
    import glob as _g
    pat=re.compile(r"owasp_results_llm01img_(.+?)_run(\d+)\.json$")
    data=defaultdict(list)
    for p in _g.glob(os.path.join(folder,"owasp_results_llm01img_*_run*.json")):
        mm=pat.search(os.path.basename(p))
        if not mm: continue
        model=mm.group(1); run=int(mm.group(2))
        for r in json.load(open(p,encoding="utf-8")):
            ev=r.get("verdict_evidence") or {}
            data[model].append({"id":r["id"],"run":run,
                "mech":r.get("technique") or (ev.get("mechanism") if isinstance(ev,dict) else "") or "",
                "verdict":r.get("verdict")})
    return data

def build_image_block():
    data=load_image_substudy()
    if not data: return ""
    models=sorted(data)
    # per-model resisted rate (majority across runs), and stability
    def majority(rows):
        by=defaultdict(list)
        for r in rows: by[r["id"]].append(r["verdict"])
        res=inj=0
        for i,v in by.items():
            (res:=res+1) if v.count("RESISTED")>len(v)/2 else (inj:=inj+1)
        return res,inj,len(by)
    # per-mechanism resisted (majority) per model
    mechs=[]
    for m in models:
        for r in data[m]:
            if r["mech"] not in mechs: mechs.append(r["mech"])
    def mech_res(m,mech):
        by=defaultdict(list)
        for r in data[m]:
            if r["mech"]==mech: by[r["id"]].append(r["verdict"])
        # fraction of payloads in this mech resisted (majority)
        if not by: return None
        res=sum(1 for i,v in by.items() if v.count("RESISTED")>len(v)/2)
        return round(100*res/len(by))
    # stability per model
    def stab(m):
        by=defaultdict(dict)
        for r in data[m]: by[(r["id"],)][r["run"]]=r["verdict"]
        ids=by; stable=sum(1 for k in ids if len(set(ids[k].values()))==1)
        return round(100*stable/len(ids)) if ids else 0
    cards="".join(f'<div class="card"><div class="k">{m}</div>'
        f'<div class="v">{majority(data[m])[0]}/{majority(data[m])[2]}</div>'
        f'<div class="s">resisted (of {majority(data[m])[2]})</div></div>' for m in models)
    mech_labels=json.dumps(mechs)
    mech_data=json.dumps({m:[mech_res(m,me) for me in mechs] for m in models})

    stab_rows="".join(f'<tr><td class="lbl">{m}</td><td>{stab(m)}%</td>'
        f'<td>{majority(data[m])[0]}/{majority(data[m])[2]}</td></tr>' for m in models)
    return f'''
<div class="panel" style="border:2px solid #a371f7;margin-top:34px;">
<div class="eyebrow" style="color:#a371f7;">Supplementary — Multimodal Sub-Study</div>
<h1 style="font-size:20px;">Image-based Indirect Prompt Injection</h1>
<p class="note">Two vision-capable models only. The Ollama-hosted targets
(gpt-oss, minimax-m3) are text-only and cannot receive image input, so they are
excluded from this sub-study by design. Eight distinct attack mechanisms, three runs each.</p>
<div class="cards">{cards}</div>
<h3 style="margin-top:18px;">Resistance by attack mechanism</h3>
<div style="height:300px;"><canvas id="imgMech"></canvas></div>
<p class="note">Percentage of payloads in each mechanism the model resisted (majority of runs). Higher is safer.</p>
<h3 style="margin-top:20px;">Stability (both models, 3 runs)</h3>
<table><tr><th>Model</th><th>Verdict stability</th><th>Resisted</th></tr>{stab_rows}</table>
<p class="note">Stability = share of payloads with an identical verdict across all three runs.</p>
</div>
<script>
const imgMechLabels={mech_labels}, imgMechData={mech_data};
const imgModels=Object.keys(imgMechData), IPAL=['#58a6ff','#f0883e','#3fb950'];
new Chart(document.getElementById('imgMech'),{{type:'bar',
 data:{{labels:imgMechLabels,datasets:imgModels.map((m,i)=>({{label:m,data:imgMechData[m],backgroundColor:IPAL[i%3]}}))}},
 options:{{maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},
 scales:{{x:{{ticks:{{color:'#8b949e',font:{{size:9}}}},grid:{{display:false}}}},
 y:{{beginAtZero:true,max:100,ticks:{{color:'#8b949e'}},grid:{{color:'#2d3340'}}}}}}}}}});
</script>'''


def build(out="report/comparison_report.html"):
    M=load(); mnames=sorted(M)
    if not mnames: print("no data"); return
    cats=[c for c in ORDER if any(any(r["cat"]==c for r in M[m]) for m in mnames)]
    defence={m:defence_by_cat(M[m]) for m in mnames}
    stab={};heat={}
    for m in mnames:
        s,by=stability_by_cat(M[m]); stab[m]=s; heat[m]=by
    over={m:overall(M[m]) for m in mnames}; splits={m:verdict_split(M[m]) for m in mnames}

    # ---- comparison analytics (delta table, winner, largest gap, exec summary)
    comp_rows=[]; largest=None
    if len(mnames)==2:
        a,b=mnames
        for c in cats:
            da=defence[a].get(c,0); db=defence[b].get(c,0)
            d=round(da-db,1)
            win=a if da>db else (b if db>da else "tie")
            comp_rows.append((c,da,db,d,win,stab[a].get(c,0),stab[b].get(c,0)))
        largest=max(comp_rows,key=lambda x:abs(x[3])) if comp_rows else None

    # ---- auto observation: assertive, computed from defence rates, N models
    # Winner per category = model with highest defence rate. Recomputes for
    # however many models are present (2, 3, ...). Never LLM-generated.
    obs_text=""
    if len(mnames)>=2 and cats:
        # winners[m] = list of category short-ids this model leads
        winners={m:[] for m in mnames}
        ties=[]
        low_stab=[]   # categories where the leader's margin sits within noise
        for c in cats:
            rates=[(m,defence[m].get(c,0)) for m in mnames]
            rates.sort(key=lambda x:-x[1])
            top_m,top_v=rates[0]
            second_v=rates[1][1] if len(rates)>1 else top_v
            if abs(top_v-second_v)<0.01:
                ties.append(c[3:])
            else:
                winners[top_m].append(c[3:])
                # flag if the winning margin is within run-to-run variation
                lead_stab=stab[top_m].get(c,0)
                if (top_v-second_v)<10 or lead_stab<70:
                    low_stab.append(c[3:])
        # build assertive sentence
        clauses=[]
        for i,m in enumerate(mnames):
            cs=winners[m]
            if cs:
                verb="exhibits stronger defence in" if i==0 else "shows superior resilience in"
                clauses.append(f"{m} {verb} LLM"+", LLM".join(cs))
        obs="Observation: "+ ("; whereas ".join(clauses) if clauses else "models perform comparably")
        obs+="."
        if ties:
            obs+=" Categories LLM"+", LLM".join(ties)+" are tied."
        # single honest caveat, not per-category hedging
        if low_stab:
            obs+=(" Note: margins in LLM"+", LLM".join(sorted(set(low_stab)))+
                  " are within run-to-run variation and should be read with the stability table.")
        obs_text=obs

    # overall by mean of category rates (matches per-category basis)
    mean_def={m:round(sum(defence[m].values())/len(defence[m]),1) if defence[m] else 0 for m in mnames}
    # failures per cat per model for grouped pareto
    fails_by_model={m:{c:len(maj_fail(M[m],c)) for c in cats} for m in mnames}
    # sort cats by combined failures desc
    pareto_cats=sorted(cats,key=lambda c:-sum(fails_by_model[m][c] for m in mnames))
    pareto_labels=json.dumps(pareto_cats)
    pareto_data=json.dumps({m:[fails_by_model[m][c] for c in pareto_cats] for m in mnames})

    labels=json.dumps(cats)
    defence_js=json.dumps({m:[defence[m].get(c,0) for c in cats] for m in mnames})
    stab_js=json.dumps({m:[stab[m].get(c,0) for c in cats] for m in mnames})
    all_ids=[];seen=set()
    for m in mnames:
        for r in sorted(M[m],key=lambda x:(ORDER.index(x["cat"]) if x["cat"] in ORDER else 9,x["id"])):
            if r["run"]==1 and r["id"] not in seen: seen.add(r["id"]);all_ids.append(r["id"])
    lat_by_model={}
    for m in mnames:
        lookup={r["id"]:r["lat"] for r in M[m] if r["run"]==1}
        lat_by_model[m]=[lookup.get(i) for i in all_ids]
    lat_ids_js=json.dumps(all_ids); lat_js=json.dumps(lat_by_model)
    cards="".join(f'<div class="card"><div class="k">{m}</div><div class="v">{over[m]:.1f}%</div><div class="s">overall defence</div></div>' for m in mnames)
    head="".join(f"<th>{m}</th>" for m in mnames)
    strows="".join(f'<tr><td class="lbl">{c} {NAMES[c]}</td>'+"".join(f"<td>{stab[m].get(c,0):.0f}%</td>" for m in mnames)+"</tr>" for c in cats)
    pies="".join(f'<div style="text-align:center"><div style="width:150px;height:150px;margin:auto"><canvas id="pie_{i}"></canvas></div><div class="s">{m}</div></div>' for i,m in enumerate(mnames))
    pie_js=json.dumps({m:[splits[m].get(k,0) for k in ("pass","partial","fail","error")] for m in mnames})
    def _strip_for(m):
        merged=dict(heat[m])
        merged.update(image_heat_entries(m))
        has_img = any(k[0]=="LLM11_IMG" for k in merged)
        note = ("Each strip is one payload across its runs; red tick marks a flip. "
                "The final IMG band is the image sub-study (this model is vision-capable)." if has_img
                else "Each strip is one payload across its runs; red tick marks a flip.")
        return f'<div class="panel"><h3>Stability detail &mdash; {m}</h3>{heatmap_html(merged)}<p class="note">{note}</p></div>'
    heat_html="".join(_strip_for(m) for m in mnames)
    pm=mnames[0]
    fl=sorted([(c,len(maj_fail(M[pm],c))) for c in cats],key=lambda x:-x[1])
    par_lab=json.dumps([c for c,_ in fl]); par_val=json.dumps([v for _,v in fl])
    cum=[];s=0
    for _,v in fl: s+=v;cum.append(s)
    par_cum=json.dumps(cum)
    overlap=""
    if len(mnames)==2:
        a,b=mnames; best=None;bd=-1
        for c in cats:
            fa=maj_fail(M[a],c);fb=maj_fail(M[b],c)
            ids={r["id"] for r in M[a] if r["cat"]==c}|{r["id"] for r in M[b] if r["cat"]==c}
            both=len(fa&fb);oA=len(fa-fb);oB=len(fb-fa);nei=len(ids)-both-oA-oB
            if oA+oB>bd: bd=oA+oB;best=(c,both,oA,oB,nei)
        if best:
            c,both,oA,oB,nei=best
            overlap=f'<div class="panel"><h3>Payload Failure Overlap &mdash; {c} {NAMES[c]}</h3><p class="note">Set-overlap information a Venn implies, read exactly.</p><table class="ov"><tr><th></th><th>{b} fails</th><th>{b} defends</th></tr><tr><td class="lbl">{a} fails</td><td class="hot">{both}</td><td>{oA}</td></tr><tr><td class="lbl">{a} defends</td><td>{oB}</td><td>{nei}</td></tr></table><p class="note">Top-left: shared weakness. Off-diagonal ({oA}+{oB}): model-specific, hidden by any aggregate.</p></div>'
    # exec summary + delta table html
    exec_html=""
    delta_html=""
    if len(mnames)==2 and comp_rows:
        a,b=mnames
        overall_winner=a if mean_def[a]>mean_def[b] else (b if mean_def[b]>mean_def[a] else "tie")
        # strongest/weakest category per overall-winner
        lg=largest
        drows=""
        for (c,da,db,d,win,sa,sb) in comp_rows:
            va=f"<b>{da:.0f}%</b>" if da>=db else f"{da:.0f}%"
            vb=f"<b>{db:.0f}%</b>" if db>=da else f"{db:.0f}%"
            drows+=f'<tr><td class="lbl">{c} {NAMES[c]}</td><td>{va}</td><td>{vb}</td><td>{abs(d):.0f}%</td><td class="lbl">{win if win!="tie" else "&mdash;"}</td></tr>'
        delta_html=f'''<div class="panel"><h3>Per-Category Comparison</h3>
<table><tr><th>Category</th><th>{a}</th><th>{b}</th><th>&Delta;</th><th>Higher defence</th></tr>{drows}</table>
<p class="note">Higher defence rate is bolded. &Delta; is the absolute gap. Note: differences smaller
than run-to-run stability variation should not be read as decisive; see stability table.</p></div>'''
        exec_html=f'''<div class="panel" style="border-color:#2f81f7;">
<h3>Executive Summary</h3>
<div style="font-size:14px;line-height:1.9;">
Overall higher mean defence: <b>{overall_winner}</b>
({mean_def[a]:.0f}% vs {mean_def[b]:.0f}%, mean of category rates).<br>
Largest gap: <b>{lg[0]} {NAMES[lg[0]]}</b> at <b>{abs(lg[3]):.0f}%</b>, favouring
{lg[4] if lg[4]!="tie" else "neither"}.<br>
Reproducibility caveat: category differences are read against verdict stability
(below); a gap smaller than the models\' run-to-run variation is not decisive.
</div></div>'''

    image_block=build_image_block()
    generative_comparison=build_generative_comparison()
    html=f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Cross-model comparison</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{{--bg:#0d1117;--panel:#161b22;--panel2:#1c2230;--line:#2d3340;--ink:#e6edf3;--muted:#8b949e;--pass:#3fb950;--partial:#d29922;--fail:#f85149;--err:#6e7681;}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,Segoe UI,Roboto,sans-serif;}}
.wrap{{max-width:1080px;margin:0 auto;padding:28px 22px 70px;}}
h1{{font-size:24px;margin:4px 0;}} h3{{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 14px;}}
.eyebrow{{color:var(--muted);font-size:12px;letter-spacing:.08em;text-transform:uppercase;}}
.sub{{color:var(--muted);margin-bottom:20px;}}
.cards{{display:flex;gap:14px;margin:16px 0;}}
.card{{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;text-align:center;}}
.card .k{{font-size:12px;color:var(--muted);font-family:monospace;}} .card .v{{font-size:28px;font-weight:700;color:var(--pass);margin:6px 0;}} .card .s{{font-size:11px;color:var(--muted);}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px;margin:18px 0;}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:18px;}}
@media(max-width:820px){{.grid2{{grid-template-columns:1fr;}}}}
table{{width:100%;border-collapse:collapse;font-size:13px;}}
th,td{{border-bottom:1px solid var(--line);padding:8px 10px;text-align:center;}}
td.lbl{{text-align:left;color:var(--muted);}}
.ov td,.ov th{{border:1px solid var(--line);}} .ov .hot{{background:rgba(248,81,73,.18);font-weight:700;}}
.note{{font-size:12px;color:var(--muted);margin:10px 0 0;}} .obs{{color:var(--ink);border-left:3px solid #2f81f7;padding-left:10px;font-style:italic;}} .s{{font-size:12px;color:var(--muted);}}
canvas{{max-height:340px;}}
.hmwrap{{display:flex;gap:8px;align-items:flex-start;}}
.hrls{{display:flex;flex-direction:column;gap:2px;}}
.hrl{{height:16px;line-height:16px;font-size:9px;color:var(--muted);font-family:monospace;}}
.hbody{{flex:1;min-width:0;overflow-x:auto;}}
.hgrid{{display:flex;gap:1px;}}
.hcol{{width:7px;flex:0 0 7px;display:flex;flex-direction:column;gap:2px;position:relative;}}
.hc{{height:16px;border-radius:1px;background:#20262f;}}
.flip::after{{content:'';position:absolute;bottom:-7px;left:50%;transform:translateX(-50%);border-left:2px solid transparent;border-right:2px solid transparent;border-top:4px solid var(--fail);}}
.hbandrow{{display:flex;gap:1px;margin-top:10px;}}
.hband{{display:flex;align-items:center;justify-content:center;background:var(--panel2);border-radius:2px;height:16px;overflow:hidden;}}
.hband span{{font-size:8px;color:var(--muted);font-family:monospace;}}
.c-pass{{background:var(--pass);}}.c-partial{{background:var(--partial);}}.c-fail{{background:var(--fail);}}.c-error{{background:var(--err);}}
</style></head><body><div class="wrap">
<div class="eyebrow">Cross-Model Comparison</div>
<h1>{" vs ".join(mnames)}</h1>
<div class="sub">OWASP LLM Top 10 (2025). All runs present, pooled where noted.</div>
<div class="cards">{cards}</div>
{exec_html}
{delta_html}
<div class="panel"><h3>Verdict Split by Model</h3><div style="height:180px;"><canvas id="splitBars"></canvas></div><p class="note">100% stacked: each bar normalised to its own total so the proportion of pass/partial/fail/error is directly comparable regardless of differing evaluation counts. Green pass, amber partial, red fail, grey error.</p></div>
<div class="panel"><h3>Verdict Stability by Category (the inversion)</h3><table><tr><th>Category</th>{head}</tr>{strows}</table><div style="height:320px;margin-top:16px;"><canvas id="stabBars"></canvas></div><p class="note">Grouped bars: stability per category per model. Comparable overall, opposite by category, is the finding.</p></div>
{heat_html}
<div class="grid2"><div class="panel"><h3>Defence Rate by Category</h3><div style="height:300px;"><canvas id="defBars"></canvas></div></div><div class="panel"><h3>Defence Profile (radar)</h3><div style="height:300px;"><canvas id="radar"></canvas></div><p class="note obs">{obs_text}</p></div></div>
<div class="panel"><h3>Response Latency by Payload (both models)</h3><div style="height:300px;"><canvas id="latLine"></canvas></div><p class="note">One line per model, aligned by payload id. Colour per model (legend).</p></div>
<div class="panel"><h3>Where Vulnerabilities Concentrate</h3><div style="height:300px;"><canvas id="pareto"></canvas></div><p class="note">Failures per category per model (majority of runs), categories ordered by combined total. Grouped so both models are directly comparable.</p></div>
{overlap}
{image_block}
{generative_comparison}
<script>
const labels={labels},defence={defence_js},stab={stab_js},pie={pie_js};
const latIds={lat_ids_js},lat={lat_js};
const models=Object.keys(defence),PAL={json.dumps(PALETTE)};
const segs=[['Pass','#3fb950',0],['Partial','#d29922',1],['Fail','#f85149',2],['Error','#6e7681',3]];
const splitTotals={{}}; models.forEach(m=>splitTotals[m]=pie[m].reduce((a,b)=>a+b,0)||1);
new Chart(document.getElementById('splitBars'),{{type:'bar',
 data:{{labels:models,datasets:segs.map(s=>({{label:s[0],
   data:models.map(m=>100*pie[m][s[2]]/splitTotals[m]),backgroundColor:s[1]}}))}},
 options:{{indexAxis:'y',maintainAspectRatio:false,
 plugins:{{legend:{{labels:{{color:'#8b949e',boxWidth:12,font:{{size:11}}}}}},
 tooltip:{{callbacks:{{label:(c)=>c.dataset.label+': '+c.parsed.x.toFixed(1)+'%'}}}}}},
 scales:{{x:{{stacked:true,max:100,ticks:{{color:'#8b949e',callback:v=>v+'%'}},grid:{{color:'#2d3340'}}}},
 y:{{stacked:true,ticks:{{color:'#e6edf3',font:{{size:12}}}},grid:{{display:false}}}}}}}}}});
function grouped(id,data,max){{new Chart(document.getElementById(id),{{type:'bar',data:{{labels:labels,datasets:models.map((m,i)=>({{label:m,data:data[m],backgroundColor:PAL[i%5]}}))}},options:{{maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},scales:{{x:{{ticks:{{color:'#8b949e'}},grid:{{display:false}}}},y:{{beginAtZero:true,max:max,ticks:{{color:'#8b949e'}},grid:{{color:'#2d3340'}}}}}}}}}});}}
grouped('stabBars',stab,100);grouped('defBars',defence,100);
new Chart(document.getElementById('radar'),{{type:'radar',data:{{labels:labels,datasets:models.map((m,i)=>({{label:m,data:defence[m],borderColor:PAL[i%5],backgroundColor:PAL[i%5]+'33',borderWidth:2}}))}},options:{{maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},scales:{{r:{{min:0,max:100,ticks:{{color:'#8b949e',backdropColor:'transparent'}},grid:{{color:'#2d3340'}},angleLines:{{color:'#2d3340'}},pointLabels:{{color:'#e6edf3',font:{{size:10}}}}}}}}}}}});
new Chart(document.getElementById('latLine'),{{type:'line',data:{{labels:latIds,datasets:models.map((m,i)=>({{label:m,data:lat[m],borderColor:PAL[i%5],backgroundColor:PAL[i%5]+'22',spanGaps:true,tension:.2,pointRadius:0,borderWidth:1.6}}))}},options:{{maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},scales:{{x:{{ticks:{{color:'#8b949e',maxTicksLimit:15,font:{{size:8}}}},grid:{{display:false}}}},y:{{title:{{display:true,text:'Latency (s)',color:'#8b949e'}},ticks:{{color:'#8b949e'}},grid:{{color:'#2d3340'}}}}}}}}}});
const pcats={pareto_labels},pdata={pareto_data};
new Chart(document.getElementById('pareto'),{{type:'bar',data:{{labels:pcats,datasets:models.map((m,i)=>({{label:m,data:pdata[m],backgroundColor:PAL[i%5]}}))}},options:{{maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},scales:{{x:{{ticks:{{color:'#8b949e'}},grid:{{display:false}}}},y:{{beginAtZero:true,title:{{display:true,text:'Payloads failed',color:'#8b949e'}},ticks:{{color:'#8b949e'}},grid:{{color:'#2d3340'}}}}}}}}}});
</script></body></html>"""
    os.makedirs(os.path.dirname(out),exist_ok=True)
    open(out,"w",encoding="utf-8").write(html)
    print(f"wrote {out}: {', '.join(mnames)}")

if __name__=="__main__":
    build()