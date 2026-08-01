"""
core/base_test.py — the framework contract.

Every OWASP category test (LLM01, LLM07, LLM10, ...) is a class that
extends BaseTest. BaseTest provides the SHARED run() loop (send each
payload, evaluate, collect results, save) written ONCE. Each category
only implements what is unique to it:
    load_payloads()  -> where its test prompts come from
    evaluate()       -> how it judges a response (leak? exhausted? jailbroken?)

This is the same base-test pattern used in test-automation frameworks:
a base class with shared lifecycle logic, concrete subclasses that fill
in the specifics. It is what makes this a FRAMEWORK rather than a script —
adding a new category means implementing this interface, nothing else.
"""

import json
import os
import glob
import re
from xml.parsers.expat import model
from core.attacker import send_payload



def safe_model_name(model):
    """'gpt-oss:120b-cloud' -> 'gpt-oss_120b-cloud' for safe filenames."""
    return model.replace(":", "_").replace("/", "_")

def next_run_number(prefix, model):
    """Scan report/ for existing runN files for this category+model and
    return the next number. First run for a category is 1."""
    safe = safe_model_name(model)
    pattern = f"report/{prefix}_{safe}_run*.json"
    existing = glob.glob(pattern)
    nums = []
    for path in existing:
        m = re.search(r"_run(\d+)\.json$", path)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1 if nums else 1

class BaseTest:
    # ---- subclasses MUST set these ----
    owasp_id = None          # e.g. "LLM07"
    name = None              # human-readable, e.g. "System Prompt Leakage"
    results_prefix = None    # filename prefix, e.g. "owasp_results" or "results"

    # ---- subclasses MUST implement these ----
    def load_payloads(self):
        """Return a list of payload dicts. Each dict needs at least
        'id' and 'payload'. Category-specific fields (system_prompt,
        mechanisms, etc.) are allowed."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement load_payloads()")

    def evaluate(self, payload, outcome):
        """Given the payload and the model outcome dict from send_payload,
        return a dict: {'verdict': str, 'reason': str, 'evidence': any}."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement evaluate()")

    # ---- subclasses MAY override this (default: no system prompt, no cap) ----
    def send(self, model, payload):
        """How this category sends a payload. Override for system prompts
        (LLM07) or output caps (LLM10)."""
        return send_payload(model, str(payload["payload"]))

    # ---- SHARED: written once, used by every category ----
    def run(self, model):
        payloads = self.load_payloads()
        print(f"\n=== {self.owasp_id} — {self.name} ({len(payloads)} tests) on {model} ===")

        results = []
        counts = {}
        for p in payloads:
            outcome = self.send(model, p)
            verdict = self.evaluate(p, outcome)
            v = verdict["verdict"]
            counts[v] = counts.get(v, 0) + 1
            print(f"  [{p['id']}] -> {v}  ({outcome['latency']}s)")

            results.append({
                "id": p.get("id"),
                "owasp": self.owasp_id,
                "technique": p.get("technique", "") or p.get("strategies", ""),
                "mechanisms": p.get("mechanisms", ""),
                "strategies": p.get("strategies", ""),
                "prompt": str(p.get("payload", "")),
                "thinking_words": outcome.get("thinking_words", 0),
                "response": outcome.get("response"),
                "latency": outcome.get("latency"),
                "output_words": outcome.get("output_words"),
                "verdict": v,
                "verdict_reason": verdict.get("reason"),
                "verdict_evidence": verdict.get("evidence"),
                "target_model": model,
            })

        # save to a per-category, per-model file
        os.makedirs("report", exist_ok=True)
        run = next_run_number(self.results_prefix, model)
        out = f"report/{self.results_prefix}_{safe_model_name(model)}_run{run}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        summary = " | ".join(f"{k}={v}" for k, v in counts.items())
        print(f"  saved {len(results)} -> {out}   [{summary}]")
        return results