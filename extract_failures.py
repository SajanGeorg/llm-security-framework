#!/usr/bin/env python3
"""
extract_failures.py — pulls every FAILED (and PARTIAL) case with full context
into readable files for dissertation analysis.

For each failure it captures: model, category, id, technique, the FULL prompt,
the FULL response, the verdict, and the detector's reason/evidence — everything
you need to analyse *what* happened and *why*, and to screenshot for the writeup.

Outputs (into failures/):
  failures_index.md            one-line-per-failure index (scan, then dig in)
  failures_full.md             full prompt+response for every failure, grouped
  failures_<model>.md          per-model full detail (easier to screenshot)
  failures.csv                 structured, for filtering/counting in Excel

Run:  python extract_failures.py            (reads ./report)
      python extract_failures.py <folder>
"""
import json, glob, os, re, sys, csv
from collections import defaultdict

FOLDER = sys.argv[1] if len(sys.argv) > 1 else "report"
OUT = "failures"
os.makedirs(OUT, exist_ok=True)

FAIL_V = {"COMPLIED","LEAKED","EXHAUSTED","UNSAFE_OUTPUT","FABRICATED",
          "ENDORSED_FALSE","INJECTED","HALLUCINATED_PACKAGE"}
PARTIAL_V = {"PARTIAL","PERSONA_ADOPTED","HEDGED","PARTIAL_LEAK"}

OWASP_NAMES = {
    "llm01":"Prompt Injection","llm01img":"Prompt Injection (Image)",
    "llm02":"Sensitive Information Disclosure","llm03":"Supply Chain",
    "llm05":"Improper Output Handling","llm07":"System Prompt Leakage",
    "llm09":"Misinformation","llm10":"Unbounded Consumption","llmgen":"Adaptive Generative Attack",
}

CAT_RE = re.compile(r"owasp_results_(llm\w+?)_(.+?)_run(\d+)\.json$")

def cat_name(c): return OWASP_NAMES.get(c, c)

# ---- collect failures
failures = []   # dicts with unified fields
for p in sorted(glob.glob(os.path.join(FOLDER, "owasp_results_*_run*.json"))):
    m = CAT_RE.search(os.path.basename(p))
    if not m:
        continue
    cat, model, run = m.group(1), m.group(2), int(m.group(3))
    for r in json.load(open(p, encoding="utf-8")):
        verdict = (r.get("verdict") or "").upper()
        # generative files use leaked/verdict LEAKED
        is_fail = verdict in FAIL_V
        is_partial = verdict in PARTIAL_V
        if not (is_fail or is_partial):
            continue
        # unified prompt field: six-cat uses 'prompt', generative uses 'attack_prompt'
        prompt = r.get("prompt") or r.get("attack_prompt") or ""
        failures.append({
            "severity": "FAIL" if is_fail else "PARTIAL",
            "model": model,
            "category": cat,
            "category_name": cat_name(cat),
            "id": r.get("id",""),
            "run": run,
            "technique": r.get("technique") or r.get("seed_technique") or "",
            "verdict": verdict,
            "reason": r.get("verdict_reason") or "",
            "evidence": r.get("verdict_evidence") or "",
            "prompt": prompt,
            "response": r.get("response") or "",
            "latency": r.get("latency",""),
        })

if not failures:
    print("No failures found. Check the folder path and that result files are present.")
    sys.exit(0)

# ---- sort: by model, category, id
failures.sort(key=lambda f: (f["model"], f["category"], str(f["id"]), f["run"]))

# ---- 1. index (scan-able)
with open(os.path.join(OUT, "failures_index.md"), "w", encoding="utf-8") as f:
    f.write("# Failure index\n\n")
    f.write(f"Total: {len(failures)} cases "
            f"({sum(1 for x in failures if x['severity']=='FAIL')} FAIL, "
            f"{sum(1 for x in failures if x['severity']=='PARTIAL')} PARTIAL)\n\n")
    f.write("| Severity | Model | Category | ID | Run | Verdict | Technique |\n")
    f.write("|---|---|---|---|---|---|---|\n")
    for x in failures:
        f.write(f"| {x['severity']} | {x['model']} | {x['category']} | {x['id']} "
                f"| {x['run']} | {x['verdict']} | {str(x['technique'])[:30]} |\n")

# ---- 2. full detail (all), grouped by model then category
def write_full(fh, items):
    cur_model = cur_cat = None
    for x in items:
        if x["model"] != cur_model:
            cur_model = x["model"]; cur_cat = None
            fh.write(f"\n\n{'#'*1} MODEL: {cur_model}\n")
        if x["category"] != cur_cat:
            cur_cat = x["category"]
            fh.write(f"\n{'#'*2} {x['category']} — {x['category_name']}\n")
        fh.write(f"\n{'-'*70}\n")
        fh.write(f"### [{x['severity']}] {x['id']}  (run {x['run']})  verdict={x['verdict']}\n")
        if x["technique"]: fh.write(f"**Technique:** {x['technique']}\n\n")
        if x["reason"]:    fh.write(f"**Detector reason:** {x['reason']}\n\n")
        if x["evidence"]:  fh.write(f"**Evidence:** {x['evidence']}\n\n")
        fh.write(f"**PROMPT:**\n```\n{x['prompt']}\n```\n\n")
        fh.write(f"**RESPONSE:**\n```\n{x['response']}\n```\n")

with open(os.path.join(OUT, "failures_full.md"), "w", encoding="utf-8") as f:
    f.write("# All failures — full prompt and response\n")
    write_full(f, failures)

# ---- 3. per-model files (easier to screenshot one model at a time)
by_model = defaultdict(list)
for x in failures: by_model[x["model"]].append(x)
for model, items in by_model.items():
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', model)
    with open(os.path.join(OUT, f"failures_{safe}.md"), "w", encoding="utf-8") as f:
        f.write(f"# Failures — {model}\n")
        write_full(f, items)

# ---- 4. CSV (structured, for Excel filtering/counting)
with open(os.path.join(OUT, "failures.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["severity","model","category","category_name","id","run",
                "technique","verdict","reason","prompt","response","latency"])
    for x in failures:
        w.writerow([x["severity"],x["model"],x["category"],x["category_name"],x["id"],
                    x["run"],x["technique"],x["verdict"],x["reason"],
                    x["prompt"],x["response"],x["latency"]])

# ---- console summary
print(f"Extracted {len(failures)} cases into {OUT}/")
print(f"  FAIL: {sum(1 for x in failures if x['severity']=='FAIL')}   "
      f"PARTIAL: {sum(1 for x in failures if x['severity']=='PARTIAL')}")
print("\nBy model / category (FAIL only):")
counts = defaultdict(int)
for x in failures:
    if x["severity"]=="FAIL": counts[(x["model"],x["category"])]+=1
for (mdl,cat),n in sorted(counts.items()):
    print(f"  {mdl:32} {cat:10} {n} fails")
print(f"\nFiles: failures_index.md, failures_full.md, failures_<model>.md, failures.csv")
