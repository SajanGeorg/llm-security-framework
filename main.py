"""
main.py — the orchestrator. Instantiates every test category, runs each
against the configured model, then (optionally) builds reports.

Run:  python main.py
"""

from dotenv import load_dotenv

from run_generative import run_generative_attack
from tests.llm03_supplychain import LLM03Test
load_dotenv()

import yaml
from core import reporter
from run_generative import run_generative_attack

# Category test classes — uncomment the ones you want to run.
# from tests.llm01_jailbreak import LLM01Test
# from tests.llm02_sensitive import LLM02Test
# from tests.llm05_output import LLM05Test
# from tests.llm07_leakage import LLM07Test
# from tests.llm09_misinfo import LLM09Test
# from tests.llm10_consumption import LLM10Test

# The framework's registered test categories — add instances here.
TESTS = [
    # LLM01Test(), LLM02Test(), LLM05Test(),
    LLM03Test()
    # LLM07Test(), LLM09Test(), LLM10Test(),
]

# Set True to also run the adaptive generative attacker after the categories.
RUN_GENERATIVE = False


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

    if RUN_GENERATIVE:
        # run_number=None -> auto-increments (run1, run2, ...) like the categories
        run_generative_attack(model)

    print("\n" + "=" * 60)
    print("All done. Run 'python core/reporter.py' to build reports.")
    print("=" * 60)
    # reporter.build_all_reports()


if __name__ == "__main__":
    main()