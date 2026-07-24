"""
core/attacker.py — sends a payload to the model, returns the response.
Supports optional system prompt (for LLM07) and measures output size (for LLM10).
Captures reasoning-model 'thinking' output separately from visible content.
"""

import time
import ollama


def send_payload(model, payload_text, system_prompt=None, max_tokens=None, temperature=0.0):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": payload_text})

    options = {"temperature": temperature}
    if max_tokens is not None:
        options["num_predict"] = max_tokens

    start = time.time()
    try:
        response = ollama.chat(model=model, messages=messages, options=options)
        msg = response["message"]
        text = msg.get("content") or ""
        thinking = msg.get("thinking") or ""

        return {
            "ok": True,
            "response": text,
            "thinking": thinking,
            "thinking_words": len(thinking.split()),
            "latency": round(time.time() - start, 2),
            "output_chars": len(text),
            "output_words": len(text.split()),
            "done_reason": response.get("done_reason", "unknown"),
            "output_tokens": response.get("eval_count", None),
            "error": None,
        }
    except Exception as e:
        return {
            "ok": False, "response": None, "thinking": "", "thinking_words": 0,
            "latency": round(time.time() - start, 2),
            "output_chars": 0, "output_words": 0,
            "done_reason": "error", "output_tokens": None,
            "error": str(e),
        }