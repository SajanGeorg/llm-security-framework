"""
tests/llm01_jailbreak.py — LLM01 Prompt Injection / Jailbreak.

Reads the categorised jailbreak CSV, sends each prompt, and evaluates
using the LLM-as-judge (gemma4). Different evaluation strategy from
LLM07/LLM10 (which use objective detection) — but the SAME BaseTest
contract. This demonstrates the framework accommodates multiple
evaluation methods behind one interface.
"""

import pandas as pd
from core.base_test import BaseTest
from core.attacker import send_payload
from core.judge import judge_response   # your existing LLM-judge

CSV_PATH = "tools/labelled_sample.csv"


class LLM01Test(BaseTest):
    owasp_id = "LLM01"
    name = "Prompt Injection / Jailbreak"
    results_prefix = "owasp_results_llm01"   # keeps existing LLM01 filename convention

    def load_payloads(self):
        # scraped prompts contain Windows-1252 smart quotes -> latin-1
        df = pd.read_csv(CSV_PATH, encoding="latin-1")
        rows = []
        for i, r in df.iterrows():
            rows.append({
                "id": f"DS-{i+1:03d}",
                "technique": r.get("strategies", ""),
                "mechanisms": r.get("mechanisms", ""),
                "strategies": r.get("strategies", ""),
                "payload": r["prompt"],
            })
        return rows

    def send(self, model, payload):
        # LLM01 sends plainly, no system prompt, no cap
        return send_payload(model, str(payload["payload"]))

    def evaluate(self, payload, outcome):
        if not outcome["ok"]:
            return {"verdict": "ERROR", "reason": outcome["error"], "evidence": None}
        judgment = judge_response(payload["payload"], outcome["response"])
        return {"verdict": judgment["label"],
                "reason": judgment.get("reason", ""),
                "evidence": judgment.get("raw")}