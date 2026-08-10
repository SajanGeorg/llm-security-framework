"""
main.py — the orchestrator. Instantiates every test category, runs each
against the configured model, then (optionally) builds reports.

This is a FUNCTION, not a class — it just wires the test classes together.
Adding a new category = add its class to the TESTS list below.

Run:  python main.py
"""

import yaml
from core import reporter
from dotenv import load_dotenv
load_dotenv()
from tests.llm01_jailbreak import LLM01Test
from tests.llm02_sensitive import LLM02Test
from tests.llm05_output import  LLM05Test
from tests.llm07_leakage import LLM07Test
from tests.llm09_misinfo import LLM09Test
from tests.llm10_consumption import LLM10Test

# the framework's registered test categories — add new ones here
TESTS = [
  LLM01Test(), 
  LLM02Test(),LLM05Test(),LLM07Test(), LLM09Test(), LLM10Test(),
]


def load_model():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["target_model"]


def main():
    model = load_model()
    print("=" * 60)
    print(f"RUNNING {len(TESTS)} test categories against {model}")
    print("=" * 60)

    for test in TESTS:
        test.run(model)

    print("\n" + "=" * 60)
    print("All categories complete. Run 'python core/reporter.py' to build reports.")
    print("=" * 60)
    reporter.build_all_reports()
if __name__ == "__main__":
    main()