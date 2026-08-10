"""
tests/llm01_img.py — Image-based indirect prompt injection (multimodal sub-study).

SCOPE: this is a TWO-MODEL supplementary study (Claude, GPT-4o-mini), NOT part of
the six-category cross-model comparison, because the Ollama target models are
text-only and cannot receive image input. Reported separately.

Each payload sends an attack IMAGE plus a benign text prompt. The judge decides
whether the injection embedded in the image succeeded. The raw response is stored
so results can be re-scored deterministically later without re-running.

CSV columns: id, mechanism, image, benign_prompt, attack_goal, success_marker
Images live in payloads/attack_images/.
"""
import os
import pandas as pd
from core.base_test import BaseTest
from core.attacker import send_payload
from core.judge_image import judge_image

CSV_PATH = "payloads/llm01_img.csv"
IMG_DIR = "payloads/attack_images"

LABEL_TO_VERDICT = {"RESISTED": "RESISTED", "INJECTED": "INJECTED",
                    "PARTIAL": "PARTIAL", "ERROR": "ERROR"}


class LLM01ImgTest(BaseTest):
    owasp_id = "LLM01_IMG"
    name = "Image-based Indirect Prompt Injection"
    results_prefix = "owasp_results_llm01img"

    def load_payloads(self):
        df = pd.read_csv(CSV_PATH)
        return [{"id": r["id"], "mechanism": r["mechanism"],
                 "technique": r["mechanism"],
                 "image": os.path.join(IMG_DIR, r["image"]),
                 "benign_prompt": r["benign_prompt"],
                 "attack_goal": r["attack_goal"],
                 "success_marker": r.get("success_marker", "")}
                for _, r in df.iterrows()]

    def send(self, model, payload):
        return send_payload(model, str(payload["benign_prompt"]),
                            image_path=payload["image"])

    def evaluate(self, payload, outcome):
        if not outcome["ok"]:
            return {"verdict": "ERROR", "reason": outcome["error"], "evidence": None}
        resp = outcome.get("response") or ""
        j = judge_image(benign_prompt=str(payload["benign_prompt"]),
                        attack_goal=str(payload["attack_goal"]),
                        response=resp)
        verdict = LABEL_TO_VERDICT.get(j["label"], "ERROR")
        # store marker presence too, for optional later deterministic re-scoring
        marker = str(payload.get("success_marker", "")).strip()
        marker_present = bool(marker) and marker.lower() in resp.lower()
        return {"verdict": verdict,
                "reason": f"judge={j['label']} | marker_present={marker_present} | raw: {j.get('raw')}",
                "evidence": {"mechanism": payload["mechanism"],
                             "marker_present": marker_present}}
