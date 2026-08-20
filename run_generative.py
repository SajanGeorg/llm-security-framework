"""run_generative.py — runs the generative adversarial attack agent.

Run numbers AUTO-INCREMENT like the other tests: each execution scans report/
and writes the next run file (run1, run2, run3...). Just run it again for another
run; it never overwrites.

Two ways to use it:
1. Standalone:    python run_generative.py
2. From main.py:  from run_generative import run_generative_attack
                  run_generative_attack(target)
"""
import yaml
from tests.generative_attack import GenerativeAttackTest   # the class this runner drives

ATTACKER = "gemma4:31b-cloud"        # the model that generates attack prompts
TRIALS_PER_TECHNIQUE = 5        # samples per technique (gives a per-technique rate)


def run_generative_attack(target, attacker=ATTACKER, run_number=None,
                          trials_per_technique=TRIALS_PER_TECHNIQUE):
    """Run the adaptive attacker against `target`. run_number auto-increments
    if left as None, so repeated calls produce run1, run2, run3... without overwriting."""
    agent = GenerativeAttackTest(attacker_model=attacker, runs=trials_per_technique)
    return agent.run(target, run_number=run_number)


if __name__ == "__main__":
    with open("config.yaml") as f:
        target = yaml.safe_load(f)["target_model"]
    run_generative_attack(target)   # auto-numbers; run again for run2, run3...