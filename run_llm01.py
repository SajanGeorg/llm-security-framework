"""
main.py — reads the labelled CSV, sends each prompt to the target model,
evaluates the response, saves results to JSON.

Run from project root:  python main.py
"""

import json
import os
import pandas as pd
import yaml

from core.attacker import send_payload
from core.evaluator import evaluate
from core.judge import judge_response

CONFIG_PATH = "config.yaml"


def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
    
def safe_model_name(model):
        return model.replace(":", "_").replace("/", "_")

def run_llm01():
    config = load_config()
    model = config["target_model"]
    csv_path = config.get("payloads_csv", "tools/labelled_sample.csv")
    results_path = f"report/results_{safe_model_name(model)}.json"

    print("=" * 60)
    print(f"TARGET MODEL : {model}")
    print(f"READING CSV  : {csv_path}")
    print("=" * 60)

    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV not found at {csv_path}")
        print("  -> run tools/build_payloads.py first, or fix the path in config.yaml")
        return

    # pandas reads the CSV safely (handles quotes, newlines, special chars)
    df = pd.read_csv(csv_path, encoding="latin-1")
    print(f"Loaded {len(df)} rows. Columns: {list(df.columns)}\n")

    if "prompt" not in df.columns:
        print(f"[ERROR] No 'prompt' column. Found: {list(df.columns)}")
        return

    results = []
    counts = {"COMPLIED": 0, "REFUSED": 0, "PARTIAL": 0, "ERROR": 0}

    for i, row in df.iterrows():
        # build a payload dict so the evaluator (which expects a dict) works unchanged
        payload = {
            "id": f"DS-{i + 1:03d}",
            "category": "Prompt Injection / Jailbreak",
            "owasp": "LLM01",
            "mechanisms": row.get("mechanisms", ""),
            "strategies": row.get("strategies", ""),
            "payload": str(row["prompt"]),
            "success_marker": None,   # dataset rows use persona/refusal detection
            "expected": "refusal_or_normal",
        }

        print(f"[{payload['id']}] {payload['strategies']} | {payload['mechanisms']}")

        outcome = send_payload(model, payload["payload"])
       # LLM-as-judge instead of keyword evaluator
        judgment = judge_response(payload["payload"], outcome["response"])
        label = judgment["label"]
        counts[label] = counts.get(label, 0) + 1
        print(f"   -> {label}  ({outcome['latency']}s target)\n")

       

        results.append({
            "id": payload["id"],
            "platform": row.get("platform", ""),
            "source": row.get("source", ""),
            "mechanisms": row.get("mechanisms", ""),
            "strategies": row.get("strategies", ""),
            "prompt": payload["payload"],
            "ok": outcome["ok"],
            "response": outcome["response"],
            "latency": outcome["latency"],
            "error": outcome["error"],
            "judge_label": label,
            "judge_raw": judgment["raw"],
            "target_model": model,
            "judge_model": "gemma4:31b-cloud",
        })

    # save results
    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print(f"DONE. {len(results)} results saved to {results_path}")
    print(f"SUMMARY: " + " | ".join(f"{k}={v}" for k, v in counts.items()))
    print("=" * 60)


if __name__ == "__main__":
    run_llm01()