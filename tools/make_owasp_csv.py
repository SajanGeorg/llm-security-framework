# check_llm02.py — run from project root
import json, glob, re
from collections import defaultdict

MODEL = "minimax-m3"   # change to gpt-oss_120b for the other model

runs = {}
for f in glob.glob(f"report/owasp_results_llm02_{MODEL}_cloud_run*.json"):
    rn = int(re.search(r'run(\d)', f).group(1))
    runs[rn] = json.load(open(f, encoding='utf-8'))

judge, det = defaultdict(dict), defaultdict(dict)
for rn, data in runs.items():
    for r in data:
        judge[r['id']][rn] = r['verdict']
        ev = r.get('verdict_evidence')
        det[r['id']][rn] = ev.get('deterministic') if isinstance(ev, dict) else None

ids = sorted(judge)
def stab(d): return sum(1 for i in ids if len({d[i].get(rn) for rn in runs}) == 1)

n = len(ids)
print(f"LLM02 / {MODEL} across {len(runs)} runs, {n} payloads:")
print(f"  judge stability:         {stab(judge)}/{n} = {100*stab(judge)/n:.0f}%")
print(f"  deterministic stability: {stab(det)}/{n} = {100*stab(det)/n:.0f}%")
print("\ndisagreements (judge flipped, deterministic held):")
for i in ids:
    jv = [judge[i].get(rn) for rn in sorted(runs)]
    dv = [det[i].get(rn) for rn in sorted(runs)]
    if len(set(jv)) > 1 and len(set(dv)) == 1:
        print(f"  {i}: judge {jv} | det {dv}")