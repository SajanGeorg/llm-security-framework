"""
run_img_substudy.py — runs the image-injection sub-study end to end.
Two models (Claude, GPT-4o-mini), 8 images, 3 runs each. ~48 calls total.

Writes one JSON per model per run into report/, matching your naming so the
existing tooling can read them:
    owasp_results_llm01img_{model}_run{N}.json

Run from project root:  python run_img_substudy.py
"""
import os, json, re, time
from tests.llm01_img import LLM01ImgTest

MODELS = ["claude-haiku-4-5-20251001", "gpt-4o-mini"]
RUNS = 3
os.makedirs("report", exist_ok=True)

def safe(name):
    return re.sub(r'[^A-Za-z0-9._-]', '_', name)

test = LLM01ImgTest()
payloads = test.load_payloads()

for model in MODELS:
    for run in range(1, RUNS + 1):
        records = []
        for p in payloads:
            outcome = test.send(model, p)
            verdict = test.evaluate(p, outcome)
            records.append({
                "id": p["id"],
                "owasp": "LLM01_IMG",
                "technique": p["mechanism"],
                "mechanisms": p["mechanism"],
                "strategies": "",
                "prompt": p["benign_prompt"],
                "response": outcome.get("response"),
                "thinking_words": outcome.get("thinking_words", 0),
                "latency": outcome.get("latency", 0),
                "output_words": outcome.get("output_words", 0),
                "verdict": verdict["verdict"],
                "verdict_reason": verdict["reason"],
                "verdict_evidence": verdict["evidence"],
                "target_model": model,
            })
            print(f"  {model} run{run} {p['id']}: {verdict['verdict']}")
        out = f"report/owasp_results_llm01img_{safe(model)}_run{run}.json"
        json.dump(records, open(out, "w", encoding="utf-8"), indent=2)
        print(f"wrote {out}")

print("\nImage sub-study complete.")
