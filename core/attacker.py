"""
core/attacker.py — sends a payload to the model, returns the response.
Supports optional system prompt (LLM07/LLM02), output cap (LLM10), and optional
image input (multimodal sub-study). Captures reasoning 'thinking' separately.

Routes by model name:
  "claude..."            -> Anthropic API
  "gpt..." / "o1"/"o3"   -> OpenAI API
  everything else        -> Ollama  (original behaviour, unchanged)

All paths return the IDENTICAL dict shape so nothing downstream changes.
"""

import os
import time
import ollama
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
_anthropic_client = None
_openai_client = None


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY
    return _anthropic_client


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI()                    # reads OPENAI_API_KEY
    return _openai_client


def _is_openai(model):
    m = str(model).lower()
    return m.startswith("gpt") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4")


def send_payload(model, payload_text, system_prompt=None, max_tokens=None,
                 temperature=0.0, image_path=None):
    """Router. image_path (optional) enables the multimodal sub-study for
    providers that support vision (Claude, OpenAI); ignored by Ollama text models."""
    if str(model).startswith("claude"):
        return _send_anthropic(model, payload_text, system_prompt, max_tokens, temperature, image_path)
    if _is_openai(model):
        return _send_openai(model, payload_text, system_prompt, max_tokens, temperature, image_path)
    return _send_ollama(model, payload_text, system_prompt, max_tokens, temperature)


# ---------------------------------------------------------------- Ollama (original, unchanged)
def _send_ollama(model, payload_text, system_prompt=None, max_tokens=None, temperature=0.0):
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
        return {"ok": True, "response": text, "thinking": thinking,
                "thinking_words": len(thinking.split()),
                "latency": round(time.time() - start, 2),
                "output_chars": len(text), "output_words": len(text.split()),
                "done_reason": response.get("done_reason", "unknown"),
                "output_tokens": response.get("eval_count", None), "error": None}
    except Exception as e:
        return {"ok": False, "response": None, "thinking": "", "thinking_words": 0,
                "latency": round(time.time() - start, 2), "output_chars": 0,
                "output_words": 0, "done_reason": "error", "output_tokens": None,
                "error": str(e)}


# ---------------------------------------------------------------- Anthropic (Claude)
DEFAULT_MAX_TOKENS = 1024

def _b64_image(image_path):
    import base64, mimetypes
    mt = mimetypes.guess_type(image_path)[0] or "image/png"
    with open(image_path, "rb") as f:
        return mt, base64.standard_b64encode(f.read()).decode("utf-8")

def _send_anthropic(model, payload_text, system_prompt=None, max_tokens=None,
                    temperature=0.0, image_path=None):
    client = _get_anthropic()
    if image_path:
        mt, b64 = _b64_image(image_path)
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}},
            {"type": "text", "text": payload_text},
        ]
    else:
        content = payload_text
    kwargs = {"model": model,
              "max_tokens": max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
              "temperature": temperature,
              "messages": [{"role": "user", "content": content}]}
    if system_prompt:
        kwargs["system"] = system_prompt
    start = time.time()
    try:
        resp = client.messages.create(**kwargs)
        text_parts, think_parts = [], []
        for block in resp.content:
            bt = getattr(block, "type", None)
            if bt == "text": text_parts.append(getattr(block, "text", ""))
            elif bt == "thinking": think_parts.append(getattr(block, "thinking", "") or "")
        text = "".join(text_parts); thinking = "".join(think_parts)
        out_tokens = getattr(resp.usage, "output_tokens", None) if getattr(resp, "usage", None) else None
        return {"ok": True, "response": text, "thinking": thinking,
                "thinking_words": len(thinking.split()),
                "latency": round(time.time() - start, 2),
                "output_chars": len(text), "output_words": len(text.split()),
                "done_reason": getattr(resp, "stop_reason", "unknown"),
                "output_tokens": out_tokens, "error": None}
    except Exception as e:
        return {"ok": False, "response": None, "thinking": "", "thinking_words": 0,
                "latency": round(time.time() - start, 2), "output_chars": 0,
                "output_words": 0, "done_reason": "error", "output_tokens": None,
                "error": str(e)}


# ---------------------------------------------------------------- OpenAI (GPT)
def _send_openai(model, payload_text, system_prompt=None, max_tokens=None,
                 temperature=0.0, image_path=None):
    client = _get_openai()
    # OpenAI uses a messages array; system prompt is a system-role message.
    # Image input uses content blocks with type image_url (data URL for local files).
    user_content = payload_text
    if image_path:
        import base64, mimetypes
        mt = mimetypes.guess_type(image_path)[0] or "image/png"
        with open(image_path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode("utf-8")
        user_content = [
            {"type": "text", "text": payload_text},
            {"type": "image_url", "image_url": {"url": f"data:{mt};base64,{b64}"}},
        ]
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})

    kwargs = {"model": model, "messages": messages, "temperature": temperature}
    # OpenAI param name is max_tokens (older) / max_completion_tokens (newer).
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    start = time.time()
    try:
        resp = client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        text = choice.message.content or ""
        out_tokens = resp.usage.completion_tokens if getattr(resp, "usage", None) else None
        return {"ok": True, "response": text, "thinking": "",
                "thinking_words": 0,
                "latency": round(time.time() - start, 2),
                "output_chars": len(text), "output_words": len(text.split()),
                "done_reason": choice.finish_reason or "unknown",
                "output_tokens": out_tokens, "error": None}
    except Exception as e:
        return {"ok": False, "response": None, "thinking": "", "thinking_words": 0,
                "latency": round(time.time() - start, 2), "output_chars": 0,
                "output_words": 0, "done_reason": "error", "output_tokens": None,
                "error": str(e)}