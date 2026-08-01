"""
tests/llm09_misinfo.py — Misinformation (OWASP LLM09, 2025).

Two payload kinds, scored against a known ground truth by the misinformation
judge:
  fabrication   -> model should say the thing does not exist
  false_premise -> model should correct the false claim

Payload CSV columns:
  id, kind, ground_truth, payload
  (technique optional; mechanisms/strategies unused for this category)
"""

import pandas as pd
from core.base_test import BaseTest
from core.judge_misinfo import judge_misinfo

CSV_PATH = "payloads/llm09_misinfo.csv"

# judge label -> framework verdict (must align with reporter's pass/fail/partial)
LABEL_TO_VERDICT = {
    "ACCURATE": "ACCURATE",         # pass
    "FABRICATED": "FABRICATED",     # fail
    "ENDORSED_FALSE": "ENDORSED_FALSE",  # fail
    "HEDGED": "HEDGED",             # partial
    "ERROR": "ERROR",
}


class LLM09Test(BaseTest):
    owasp_id = "LLM09"
    name = "Misinformation"
    results_prefix = "owasp_results_llm09"

    def load_payloads(self):
        df = pd.read_csv(CSV_PATH)
        return [{"id": r["id"],
                 "kind": r["kind"],
                 "ground_truth": r["ground_truth"],
                 "technique": r.get("kind", ""),   # surface kind as technique in report
                 "payload": r["payload"]}
                for _, r in df.iterrows()]

    # default send() is fine: no system prompt, no cap
    def evaluate(self, payload, outcome):
        if not outcome["ok"]:
            return {"verdict": "ERROR", "reason": outcome["error"], "evidence": None}
        resp = outcome.get("response") or ""
        result = judge_misinfo(
            prompt=str(payload["payload"]),
            response=resp,
            ground_truth=str(payload["ground_truth"]),
            kind=str(payload["kind"]),
        )
        label = LABEL_TO_VERDICT.get(result["label"], "ERROR")
        return {"verdict": label,
                "reason": f"{result['reason']} (raw: {result.get('raw')})",
                "evidence": payload["kind"]}
