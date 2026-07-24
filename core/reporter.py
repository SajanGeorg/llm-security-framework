"""
core/reporter.py — scans report/ for per-category, per-model result files
and generates ONE HTML report per model (combining that model's categories).

Filename pattern:  owasp_results_llm{NN}_{model}.json
Output:            security_report_{model}.html  (one per model)

Run:  python core/reporter.py
"""

import json, os, glob, re
from datetime import datetime
from collections import defaultdict
from html import escape

REPORT_DIR = "report"
PASS_V = {"REFUSED", "PROTECTED", "NORMAL", "SAFE_OUTPUT"}
FAIL_V = {"COMPLIED", "LEAKED", "EXHAUSTED", "UNSAFE_OUTPUT"}
PARTIAL_V = {"PARTIAL", "PERSONA_ADOPTED"}

# matches: owasp_results_llm01_<model>.json  -> captures ("01", "<model>")
FILE_RE = re.compile(r"^owasp_results_llm(\d+)_(.+)\.json$")


def classify(v):
    v = (v or "").upper()
    if v in PASS_V: return "pass"
    if v in PARTIAL_V: return "partial"
    if v in FAIL_V: return "fail"
    return "partial"


def discover():
    """Group all category files by model. Returns {model: [filepaths]}."""
    models = defaultdict(list)
    for path in glob.glob(os.path.join(REPORT_DIR, "owasp_results_llm*_*.json")):
        m = FILE_RE.match(os.path.basename(path))
        if m:
            model = m.group(2)          # everything after llmNN_
            models[model].append(path)
    return models


def load_rows(paths):
    rows = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        for r in data:
            verdict = r.get("verdict") or r.get("judge_label") or "UNKNOWN"
            rows.append({
                "id": r.get("id", "?"),
                "owasp": r.get("owasp", ""),
                "technique": r.get("technique", "") or r.get("strategies", ""),
                "mechanisms": r.get("mechanisms", ""),
                "strategies": r.get("strategies", ""),
                "prompt": r.get("prompt", ""),
                "response": r.get("response", ""),
                "latency": r.get("latency", 0),
                "verdict": verdict,
                "result": classify(verdict),
                "model": r.get("target_model", ""),
            })
    return rows


def pct(n, d): return round(100 * n / d, 1) if d else 0.0


def render(model_key, rows):
    total = len(rows)
    n_pass = sum(1 for r in rows if r["result"] == "pass")
    n_partial = sum(1 for r in rows if r["result"] == "partial")
    n_fail = sum(1 for r in rows if r["result"] == "fail")
    model = next((r["model"] for r in rows if r["model"]), model_key)
    cats = sorted({r["owasp"] for r in rows if r["owasp"]})

    cat_stats = defaultdict(lambda: {"pass":0,"partial":0,"fail":0,"total":0})
    for r in rows:
        c = r["owasp"] or "OTHER"
        cat_stats[c][r["result"]] += 1; cat_stats[c]["total"] += 1

    mech = defaultdict(lambda: {"fp":0,"total":0}); strat = defaultdict(lambda: {"fp":0,"total":0})
    for r in rows:
        for m in str(r["mechanisms"]).split("|"):
            m=m.strip()
            if m and m!="uncategorised":
                mech[m]["total"]+=1
                if r["result"] in ("fail","partial"): mech[m]["fp"]+=1
        for s in str(r["strategies"]).split("|"):
            s=s.strip()
            if s and s!="uncategorised":
                strat[s]["total"]+=1
                if r["result"] in ("fail","partial"): strat[s]["fp"]+=1

    most_tested = max(cat_stats.items(), key=lambda kv: kv[1]["total"])[0] if cat_stats else "N/A"
    breached = {c:s for c,s in cat_stats.items() if s["fail"]>0}
    most_breached = max(breached.items(), key=lambda kv: kv[1]["fail"])[0] if breached else "None — all defended"
    now=datetime.now(); date_str=now.strftime("%d/%m/%Y"); time_str=now.strftime("%H:%M:%S")
    pp,parp,fp = pct(n_pass,total),pct(n_partial,total),pct(n_fail,total)

    def bar(l,n,d,c):
        p=pct(n,d)
        return f'<div class="bar-row"><div class="bar-label">{escape(l)}</div><div class="bar-track"><div class="bar-fill" style="width:{p}%;background:{c}"></div></div><div class="bar-val">{n}/{d} <span class="muted">{p}%</span></div></div>'
    cov="".join(bar(c,cat_stats[c]["pass"],cat_stats[c]["total"],"var(--pass)") for c in cats)
    mb="".join(bar(m,s["fp"],s["total"],"var(--fail)") for m,s in sorted(mech.items(),key=lambda kv:pct(kv[1]["fp"],kv[1]["total"]),reverse=True)) or "<p class='muted'>No mechanism data.</p>"
    sb="".join(bar(s,st["fp"],st["total"],"var(--partial)") for s,st in sorted(strat.items(),key=lambda kv:pct(kv[1]["fp"],kv[1]["total"]),reverse=True)) or "<p class='muted'>No strategy data.</p>"
    def pill(res,v):
        cls={"pass":"pill-pass","partial":"pill-partial","fail":"pill-fail"}[res]
        return f'<span class="pill {cls}">{escape(v)}</span>'
    crows="".join(f'<tr><td class="mono">{escape(str(r["id"]))}</td><td>{escape(r["owasp"])}</td><td>{escape(str(r["technique"])[:40])}</td><td>{pill(r["result"],r["verdict"])}</td><td class="muted">{r["latency"]}s</td><td class="prompt-cell">{escape(str(r["prompt"])[:150])}</td><td class="resp-cell">{escape(str(r["response"])[:180]) if r["response"] else "<em>none</em>"}</td></tr>' for r in rows)

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Security Report — {escape(model)}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>:root{{--bg:#0d1117;--panel:#161b22;--panel2:#1c2230;--line:#2d3340;--ink:#e6edf3;--muted:#8b949e;--pass:#3fb950;--partial:#d29922;--fail:#f85149;--mono:'SF Mono',Consolas,monospace;--sans:-apple-system,'Segoe UI',Roboto,sans-serif;}}*{{box-sizing:border-box;}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.5;}}.wrap{{max-width:1200px;margin:0 auto;padding:32px 24px 80px;}}.eyebrow{{color:var(--muted);font-size:13px;letter-spacing:.08em;text-transform:uppercase;}}h1{{font-size:28px;margin:6px 0 4px;font-weight:650;}}.sub{{color:var(--muted);margin-bottom:28px;}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px;}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px;}}.card .k{{color:var(--muted);font-size:13px;}}.card .v{{font-size:24px;font-weight:650;margin:6px 0 2px;}}.card .s{{color:var(--muted);font-size:12px;}}.summary{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:24px;margin-bottom:28px;}}.summary h2{{text-align:center;font-size:18px;margin:0 0 4px;}}.meta{{display:flex;gap:24px;justify-content:center;color:var(--muted);font-size:13px;margin-bottom:22px;flex-wrap:wrap;}}.meta b{{color:var(--ink);}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;}}.metric .k{{color:var(--muted);font-size:12px;}}.metric .v{{font-size:26px;font-weight:680;}}.metric .s{{color:var(--muted);font-size:12px;}}.passrate .v{{color:var(--pass);}}.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:28px;}}.panel{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px 22px;}}.panel h3{{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 16px;}}.bar-row{{display:grid;grid-template-columns:150px 1fr 90px;align-items:center;gap:12px;margin-bottom:10px;font-size:13px;}}.bar-label{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}.bar-track{{background:var(--panel2);border-radius:6px;height:14px;overflow:hidden;}}.bar-fill{{height:100%;border-radius:6px;}}.bar-val{{text-align:right;font-variant-numeric:tabular-nums;}}.muted{{color:var(--muted);}}table{{width:100%;border-collapse:collapse;font-size:13px;}}th,td{{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top;}}th{{color:var(--muted);font-weight:600;font-size:11px;letter-spacing:.05em;text-transform:uppercase;}}.mono{{font-family:var(--mono);font-size:12px;}}.prompt-cell,.resp-cell{{max-width:260px;color:var(--muted);font-size:12px;}}.pill{{padding:3px 9px;border-radius:20px;font-size:11px;font-weight:650;white-space:nowrap;}}.pill-pass{{background:rgba(63,185,80,.15);color:var(--pass);}}.pill-partial{{background:rgba(210,153,34,.15);color:var(--partial);}}.pill-fail{{background:rgba(248,81,73,.15);color:var(--fail);}}.legend{{display:flex;gap:18px;font-size:12px;color:var(--muted);margin:10px 0 18px;}}.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle;}}.table-panel{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px 22px;overflow-x:auto;}}footer{{color:var(--muted);font-size:12px;margin-top:30px;text-align:center;}}@media(max-width:840px){{.cards,.metrics,.grid2{{grid-template-columns:1fr;}}}}</style></head><body><div class="wrap">
<div class="eyebrow">Cross-Layer LLM Security Testing Framework</div><h1>Security Test Report</h1><div class="sub">OWASP LLM Top 10 evaluation of <b>{escape(model)}</b></div>
<div class="cards"><div class="card"><div class="k">Total Test Cases</div><div class="v">{total}</div><div class="s">{n_pass} passed · {n_partial} partial · {n_fail} failed</div></div><div class="card"><div class="k">Most Tested Category</div><div class="v">{escape(most_tested)}</div><div class="s">{cat_stats[most_tested]['total'] if most_tested in cat_stats else 0} cases</div></div><div class="card"><div class="k">Most Breached Category</div><div class="v">{escape(str(most_breached))}</div><div class="s">confirmed bypass</div></div></div>
<div class="summary"><h2>Executive Summary</h2><div class="meta"><span>Date <b>{date_str}</b></span><span>Time <b>{time_str}</b></span><span>Framework <b>OWASP Top 10 for LLMs (2025)</b></span><span>Judge <b>gemma4:31b-cloud</b></span></div><div class="metrics"><div class="metric passrate"><div class="k">Defence Rate</div><div class="v">{pp}%</div><div class="s">{n_pass} of {total} defended</div></div><div class="metric"><div class="k">Vulnerability Coverage</div><div class="v">{len(cats)}</div><div class="s">OWASP categories</div></div><div class="metric"><div class="k">Partial / Persona</div><div class="v">{n_partial}</div><div class="s">took bait</div></div><div class="metric"><div class="k">Confirmed Breaches</div><div class="v" style="color:var(--fail)">{n_fail}</div><div class="s">attacks succeeded</div></div></div></div>
<div class="legend"><span><span class="dot" style="background:var(--pass)"></span>Pass</span><span><span class="dot" style="background:var(--partial)"></span>Partial</span><span><span class="dot" style="background:var(--fail)"></span>Fail</span></div>
<div class="grid2"><div class="panel"><h3>Overall Outcome</h3><div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;"><div style="width:190px;height:190px;"><canvas id="pie"></canvas></div><div style="font-size:13px;line-height:2;"><div><span class="dot" style="background:var(--pass)"></span>Pass <b>{n_pass}</b> <span class="muted">({pp}%)</span></div><div><span class="dot" style="background:var(--partial)"></span>Partial <b>{n_partial}</b> <span class="muted">({parp}%)</span></div><div><span class="dot" style="background:var(--fail)"></span>Fail <b>{n_fail}</b> <span class="muted">({fp}%)</span></div></div></div></div><div class="panel"><h3>Defence Rate by OWASP Category</h3>{cov}</div></div>
<div class="grid2"><div class="panel"><h3>LLM01 Jailbreak Success by Mechanism</h3>{mb}</div><div class="panel"><h3>LLM01 Jailbreak Success by Strategy</h3>{sb}</div></div>
<div class="table-panel"><h3>Test Cases</h3><table><thead><tr><th>ID</th><th>OWASP</th><th>Technique</th><th>Verdict</th><th>Latency</th><th>Prompt</th><th>Response</th></tr></thead><tbody>{crows}</tbody></table></div>
<footer>Generated {date_str} {time_str} · {total} test cases · {escape(model)} · MSc Cyber Security dissertation framework</footer></div>
<script>new Chart(document.getElementById('pie'),{{type:'doughnut',data:{{labels:['Pass','Partial','Fail'],datasets:[{{data:[{n_pass},{n_partial},{n_fail}],backgroundColor:['#3fb950','#d29922','#f85149'],borderColor:'#161b22',borderWidth:3}}]}},options:{{plugins:{{legend:{{display:false}}}},cutout:'62%',responsive:true,maintainAspectRatio:false}}}});</script></body></html>"""


def build_all_reports():
    models = discover()
    if not models:
        print(f"[ERROR] No owasp_results_llm*_*.json files in {REPORT_DIR}/"); return
    print(f"Found {len(models)} model(s): {', '.join(models.keys())}\n")
    for model_key, paths in models.items():
        rows = load_rows(paths)
        if not rows:
            print(f"  [skip] {model_key}: no data"); continue
        html = render(model_key, rows)
        out = os.path.join(REPORT_DIR, f"security_report_{model_key}.html")
        with open(out, "w", encoding="utf-8") as f: f.write(html)
        np_=sum(1 for r in rows if r["result"]=="pass"); nf=sum(1 for r in rows if r["result"]=="fail")
        print(f"  {model_key}: {len(rows)} tests from {len(paths)} files, {np_} pass / {nf} fail -> {out}")
    print("\nDone.")


if __name__ == "__main__":
    build_all_reports()