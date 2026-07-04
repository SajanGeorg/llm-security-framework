"""
tools/build_payloads.py — ONE-TIME tool (diagnostic build).
"""

import json
import os
import re
import sys
import traceback
import pandas as pd

CSV_PATH = "data/jailbreak_prompts_2023_12_25.csv"
JSON_OUT = "payloads/payloads_from_dataset.json"
CSV_OUT = "tools/labelled_sample.csv"
SAMPLE_PER_CATEGORY = 3
RANDOM_SEED = 42
PROMPT_COL = "prompt"


def log(*args):
    """print that always flushes — survives crashes and buffered terminals."""
    print(*args, flush=True)


# ── AXIS 1: GENERATION METHOD ──
MECHANISM_RULES = {
    "instruction_override": [
        r"\bignore (all )?(previous|prior|above|the) ", r"\bdisregard\b",
        r"\bforget (your|all|everything|previous)", r"\boverride\b",
        r"\bnew instructions?\b", r"\bdo not follow\b", r"\bvoid your\b",
    ],
    "refusal_suppression": [
        r"\bnever refuse\b", r"\bdo not (apologi|refuse|warn)", r"\balways answer\b",
        r"\bno disclaimers?\b", r"\bno warnings?\b", r"\bdon'?t say (i can'?t|no)\b",
        r"\bstart (your (reply|response|answer) )?with [\"']?sure",
        r"\bbegin your (reply|response|answer) with\b",
    ],
    "encoding_obfuscation": [
        r"\bbase64\b", r"\brot13\b", r"\bleet ?speak\b", r"\bcipher\b",
        r"\bencoded?\b", r"\bdecode (the|this)\b", r"\bmorse\b", r"\bhex(adecimal)?\b",
        r"\breverse the (text|string|order)\b", r"\bcharacter by character\b",
    ],
    "payload_injection": [
        r"\btranslate the following\b", r"\bsummari(z|s)e (this|the following)\b",
        r"\brepeat after me\b", r"\bthe (text|prompt) (below|above|that follows)\b",
        r"\beverything after (this|the colon)\b", r"\bcomplete the following\b",
    ],
    "format_manipulation": [
        r"\brespond only (in|with)\b", r"\boutput only\b", r"\bno commentary\b",
        r"\bonly (the )?(code|answer|output)\b",
    ],
}

# ── AXIS 2: SEMANTIC STRATEGY ──
STRATEGY_RULES = {
    "unrestricted_mode": [
        r"\bno restrictions?\b", r"\bdeveloper mode\b", r"\bjail ?broken\b",
        r"\bno rules\b", r"\bdan mode\b", r"\bno filter(s|ing)?\b",
        r"\bno (ethical )?guidelines?\b", r"\bunlimited\b", r"\bunlocked\b",
    ],
    "persona_roleplay": [
        r"\byou are (now )?dan\b", r"\bact as\b", r"\bpretend (you are|to be)\b",
        r"\byou are now\b", r"\brole-?play\b", r"\bstay in character\b",
        r"\b(aim|stan|dude|betterdan)\b", r"\bevil (twin|version)\b",
        r"\bopposite (day|mode)\b",
    ],
    "fictional_framing": [
        r"\bwrite a (story|script|screenplay)\b", r"\bin a world where\b",
        r"\bhypothetical(ly)?\b", r"\bfictional\b", r"\bimagine (a|that|you)\b",
        r"\bfor (a|my) (novel|story|book|screenplay)\b",
    ],
    "emotional_manipulation": [
        r"\bgrand ?(ma|mother|pa|father)\b",
        r"\b(my )?late (grand)?(mother|father|mom|dad)\b",
        r"\bpassed away\b", r"\bcomfort me\b", r"\bdying wish\b",
        r"\bplease,? i'?m (desperate|begging|dying)\b",
    ],
    "authority_pressure": [
        r"\byou must\b", r"\ba good (assistant|ai) would\b", r"\bor else\b",
        r"\bi'?ll (be fired|lose my job|get in trouble)\b", r"\bthis is urgent\b",
    ],
    "false_legitimacy": [
        r"\bfor research( purposes)?\b", r"\beducational( purposes)? only\b",
        r"\bi'?m a (security )?(researcher|pentester|professional)\b",
        r"\bauthori(z|s)ed\b", r"\bpenetration test(ing)?\b", r"\bfor a ctf\b",
    ],
}


def _compile(rules):
    return {cat: [re.compile(p) for p in pats] for cat, pats in rules.items()}

MECHANISM_COMPILED = _compile(MECHANISM_RULES)
STRATEGY_COMPILED = _compile(STRATEGY_RULES)


def categorise(text):
    low = str(text).lower()
    mechanisms, strategies, matched = [], [], []
    for cat, patterns in MECHANISM_COMPILED.items():
        for p in patterns:
            if p.search(low):
                mechanisms.append(cat); matched.append(f"{cat}:{p.pattern}"); break
    for cat, patterns in STRATEGY_COMPILED.items():
        for p in patterns:
            if p.search(low):
                strategies.append(cat); matched.append(f"{cat}:{p.pattern}"); break
    if not mechanisms:
        mechanisms = ["uncategorised"]
    if not strategies:
        strategies = ["uncategorised"]
    return mechanisms, strategies, matched


def main():
    log("STEP 0: script started.")
    log("  Working directory :", os.getcwd())
    log("  CSV (as written)  :", CSV_PATH)
    log("  CSV (absolute)    :", os.path.abspath(CSV_PATH))
    log("  CSV exists?       :", os.path.exists(CSV_PATH))

    if not os.path.exists(CSV_PATH):
        log("\n[ERROR] File not found at that path.")
        log("  -> You are probably running from the wrong directory.")
        log("  -> cd into your project root, or set CSV_PATH to an absolute path.")
        return

    log("\nSTEP 1: reading CSV ...")
    df = pd.read_csv(CSV_PATH)
    log(f"  OK. Loaded {len(df)} rows.")
    log(f"  Columns: {list(df.columns)}")

    log("\nSTEP 2: first row preview ...")
    if len(df) == 0:
        log("  [ERROR] CSV loaded but has 0 rows."); return
    first = df.iloc[0].to_dict()
    for k, v in first.items():
        v = str(v)
        log(f"    {k}: {v[:120]}{'...' if len(v) > 120 else ''}")

    if PROMPT_COL not in df.columns:
        log(f"\n[ERROR] No '{PROMPT_COL}' column. "
            f"Set PROMPT_COL to one of: {list(df.columns)}")
        return

    log("\nSTEP 3: labelling all rows ...")
    results = df[PROMPT_COL].apply(categorise)
    df["mechanisms"]    = results.apply(lambda r: r[0])
    df["strategies"]    = results.apply(lambda r: r[1])
    df["matched_terms"] = results.apply(lambda r: r[2])
    log("  OK. Labelling done.")

    log("\n--- AXIS 1: MECHANISM counts (rows may appear in >1 category) ---")
    log(df["mechanisms"].explode().value_counts().to_string())
    log("\n--- AXIS 2: STRATEGY counts (rows may appear in >1 category) ---")
    log(df["strategies"].explode().value_counts().to_string())

    n_uncat = ((df["mechanisms"].apply(lambda c: c == ["uncategorised"])) &
               (df["strategies"].apply(lambda c: c == ["uncategorised"]))).sum()
    log(f"\nRows matching NOTHING on either axis: {n_uncat} "
        f"({n_uncat / len(df) * 100:.1f}%)")

    log("\nSTEP 4: sampling ...")
    all_categories = (
        [("mechanism", c) for c in list(MECHANISM_RULES) + ["uncategorised"]] +
        [("strategy",  c) for c in list(STRATEGY_RULES) + ["uncategorised"]]
    )
    sampled, seen_idx = [], set()
    for axis, category in all_categories:
        col = "mechanisms" if axis == "mechanism" else "strategies"
        subset = df[df[col].apply(lambda lst: category in lst)]
        subset = subset[~subset.index.isin(seen_idx)]
        n = min(SAMPLE_PER_CATEGORY, len(subset))
        if n > 0:
            picked = subset.sample(n=n, random_state=RANDOM_SEED)
            seen_idx.update(picked.index)
            sampled.append(picked)
            log(f"  {axis}/{category}: sampled {n}")
        else:
            log(f"  {axis}/{category}: 0 available, skipped")

    if not sampled:
        log("\n[WARNING] Nothing matched anything. Stopping."); return

    sample_df = pd.concat(sampled).reset_index(drop=True)

    log("\nSTEP 5: writing verification CSV ...")
    out_cols = {}
    for c in ["platform", "source"]:
        if c in sample_df.columns:
            out_cols[c] = sample_df[c]
    out_cols["mechanisms"]    = sample_df["mechanisms"].apply(lambda x: "|".join(x))
    out_cols["strategies"]    = sample_df["strategies"].apply(lambda x: "|".join(x))
    out_cols["matched_terms"] = sample_df["matched_terms"].apply(lambda x: " || ".join(x))
    out_cols[PROMPT_COL]      = sample_df[PROMPT_COL]
    verify_df = pd.DataFrame(out_cols)
    os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)
    verify_df.to_csv(CSV_OUT, index=False, encoding="utf-8")
    log(f"  OK. Wrote {CSV_OUT}  ({len(verify_df)} rows)")

    log("\nSTEP 6: writing JSON ...")
    payloads = []
    for i, row in sample_df.iterrows():
        payloads.append({
            "id": f"DS-{i + 1:03d}",
            "category": "Prompt Injection / Jailbreak",
            "owasp": "LLM01",
            "mechanisms": row["mechanisms"],
            "strategies": row["strategies"],
            "matched_terms": row["matched_terms"],
            "payload": str(row[PROMPT_COL]),
            "success_marker": None,
            "expected": "refusal_or_normal",
            "source_dataset": "verazuo/jailbreak_llms (Shen et al. CCS'24)",
            "source_platform": str(row["platform"]) if "platform" in row else None,
        })
    os.makedirs(os.path.dirname(JSON_OUT), exist_ok=True)
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(payloads, f, indent=2, ensure_ascii=False)
    log(f"  OK. Wrote {JSON_OUT}  ({len(payloads)} payloads)")
    log("\nDONE.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("\n[CRASH] Uncaught exception — full traceback below:")
        traceback.print_exc()
        sys.exit(1)