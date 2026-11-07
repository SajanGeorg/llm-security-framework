# LLM Security Testing Framework

A Python framework that tests large language models against the **OWASP Top 10 for LLM Applications (2025)** and produces readable HTML reports. It was built for my MSc Cyber Security dissertation at Anglia Ruskin University (registered title: Cross-Layer Security Testing Framework for API & LLM Applications, narrowed to the LLM layer).

## Why I built it

Two gaps motivated this project:

1. Most LLM security tests are not tagged against the OWASP Top 10 categories. They tend to focus on prompt injection only.
2. Tools such as Garak give log-style output. That is hard to learn from. This framework shows input, output and verdict for every test case, and lets you look at the results from different angles (per category, per model, across repeated runs).

I am a QA automation engineer with five years of industry experience, so I approached LLM security as a test engineering problem. That is why the framework uses a reusable base test class, repeated runs and reproducibility checks, the same ideas used in test automation frameworks, applied to LLM security.

## What it covers

Seven of the ten OWASP LLM categories are tested, plus an image-injection extension:

| ID | Category | Test file |
|----|----------|-----------|
| LLM01 | Prompt Injection (jailbreak prompts) | `tests/llm01_jailbreak.py` |
| LLM01 (image) | Image-based indirect prompt injection (sub-study) | `tests/llm01_img.py` |
| LLM02 | Sensitive Information Disclosure | `tests/llm02_sensitive.py` |
| LLM03 | Supply Chain | `tests/llm03_supplychain.py` |
| LLM05 | Improper Output Handling | `tests/llm05_output.py` |
| LLM07 | System Prompt Leakage | `tests/llm07_leakage.py` |
| LLM09 | Misinformation | `tests/llm09_misinfo.py` |
| LLM10 | Unbounded Consumption | `tests/llm10_consumption.py` |

LLM04 (Data and Model Poisoning), LLM06 (Excessive Agency) and LLM08 (Vector and Embedding Weaknesses) are out of scope because they cannot be tested properly with prompts alone.

There is also an adaptive attacker (`tests/generative_attack.py`) where one LLM writes new attack prompts against the target.

## How it works

1. **Pick a target model** in `config.yaml`. The router in `core/attacker.py` sends the prompt to the right provider: names starting with `claude` go to Anthropic, `gpt` / `o1` / `o3` / `o4` go to OpenAI, and everything else goes to Ollama (local or cloud models). All providers return the same result format, so nothing else changes.
2. **Each OWASP category is a class** that extends `BaseTest` (`core/base_test.py`). The base class holds the shared loop: load payloads, send each one, evaluate the response, save results. A category only needs to implement `load_payloads()` and `evaluate()`. To add a new category, create a new class in `tests/` and add it to the `TESTS` list in `main.py`.
3. **Responses are judged.** Some categories use a separate judge model (`core/judge.py`, default `gemma4:31b-cloud` through Ollama) that returns one label: `COMPLIED`, `PERSONA_ADOPTED`, `PARTIAL` or `REFUSED`. Using a different model family from the target reduces shared blind spots. Other categories use deterministic checks, for example the sensitive information, misinformation and image judges in `core/`.
4. **Every run is saved** as JSON in `report/`, named like `owasp_results_llm01_gpt-4o-mini_run1.json`. Run numbers go up automatically (run1, run2, run3), so nothing is overwritten. Running the same tests several times is what lets the reports measure reproducibility.
5. **Reports are built from the JSON files** (see "Reports" below).

Verdicts are grouped into pass, partial and fail for the charts. For example `REFUSED` counts as a pass and `COMPLIED` counts as a fail.

## Project layout

```
main.py                  runs the enabled test categories against the model in config.yaml
config.yaml              target model and file paths
run_generative.py        adaptive attacker (an LLM generates attack prompts)
run_img_substudy.py      image injection sub-study (Claude and GPT-4o-mini, 8 images, 3 runs)
comparison_report.py     builds the cross-model comparison HTML report
core/                    attacker (model router), base_test, judges, reporters
tests/                   one file per OWASP category
payloads/                test prompts as CSV files, plus attack images
tools/                   helper scripts that build payload CSVs from datasets
data/                    jailbreak prompt dataset (Shen et al., CCS 2024)
evaluator/               refusal terms used by deterministic checks
report/                  results JSON and generated HTML reports
```

## Installation

You need Python 3.10 or newer and git.

```bash
git clone https://github.com/SajanGeorg/llm-security-framework.git
cd llm-security-framework

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
pip install python-dotenv        # imported by main.py but missing from requirements.txt
```

### API keys

Create a file called `.env` in the project root. Never commit this file.

```
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
```

You only need the key for the provider you test. Local and cloud Ollama models do not need a key here.

### Ollama (for local models and the judge)

1. Install Ollama from https://ollama.com
2. The default judge and attacker model is `gemma4:31b-cloud`. Check that your model names are valid with `ollama list` and update `JUDGE_MODEL` in `core/judge.py` and `ATTACKER` in `run_generative.py` if needed.
3. For models ending in `-cloud`, sign in with `ollama signin`.

## Usage

### 1. Choose the target model

Edit `config.yaml`:

```yaml
target_model: "gpt-4o-mini"
# target_model: "claude-haiku-4-5-20251001"
# target_model: "gpt-oss:120b-cloud"
# target_model: "minimax-m3:cloud"
```

### 2. Choose the categories

Open `main.py`, uncomment the imports for the categories you want, and add them to the `TESTS` list:

```python
from tests.llm01_jailbreak import LLM01Test
from tests.llm07_leakage import LLM07Test

TESTS = [LLM01Test(), LLM07Test()]
```

### 3. Run the tests

```bash
python main.py
```

Run it again for each extra run you want (run2, run3). Three runs per model is what the stability analysis in my dissertation used.

### 4. Optional extra studies

```bash
python run_generative.py        # adaptive attacker, writes the next run file automatically
python run_img_substudy.py      # image injection, needs a vision model and an Anthropic and OpenAI key
```

Set `RUN_GENERATIVE = True` in `main.py` to run the adaptive attacker after the categories.

### 5. Reports

```bash
python core/reporter.py         # one HTML report per model, saved as report/security_report_<model>.html
python comparison_report.py     # cross-model comparison, saved as report/comparison_report.html
```

Open the HTML files in a browser. They need internet access to load Chart.js from a CDN.

## What the reports show

- Executive summary with defence rate, confirmed breaches and the most breached category
- Defence rate by OWASP category
- A test case table with filters for category and verdict. Click a row to see the full prompt, response and detection details
- Verdict stability heatmap: one strip per payload, one square per run, so you can see which verdicts flipped between runs
- Response latency by payload
- Cross-model comparison: per-category deltas, radar chart, failure overlap and a clickable legend to isolate a model
- Image sub-study results by attack mechanism
- Adaptive attack results by technique

## Screenshots

Security report with executive summary, overall outcome and defence rate by OWASP category (gpt-4o-mini):

![Security report summary](docs/images/report-summary.png)

Test case table. Filter by category or verdict, search by id, technique or prompt, and click a row to see the full prompt, response and detection details:

![Test cases table](docs/images/test-cases.png)

Verdict stability across runs. Each vertical strip is one payload, each square is one run, and a red tick marks a payload whose verdict changed between runs:

![Verdict stability heatmap](docs/images/stability-heatmap.png)

## Example results

One run of `gpt-4o-mini` (348 test cases across 8 categories) gave a defence rate of 69.3%. Prompt injection had the most test cases (111), and improper output handling was the weakest category (28.1% defended). In a stability view from the same reporting tool, 112 of 116 payloads gave the same verdict in all three runs (96.6%), and the 4 that flipped are marked with red ticks.

The wider finding from the dissertation: LLM verdicts are not fully repeatable, even at temperature zero, so a single run is a sample and not a final result. Defence strength and reproducibility are two separate things to measure.

## Adding your own test prompts

Payloads are CSV files in `payloads/`. To add prompts to an existing category, add rows to that category's CSV and keep the same columns. To add a whole new category, extend `BaseTest` as described above.

## Known issues

- `python-dotenv` is not listed in `requirements.txt`. Install it manually.
- The LLM03 category shows an unexplained 0% defence result in some runs that is still being investigated.
- `core/judge.py` has a `time` import conflict (`from datetime import time` hides the `time` module), which breaks the retry sleep. Remove that line.
- The model list in `config.yaml` and the judge model name are hard-coded. Change them to match the models you have access to.

## Responsible use

This tool sends adversarial prompts to AI models. Only run it against models you own or have permission to test, and follow the provider's usage policy. Research ethics code: ETH2526-5823.

## References

Research papers (Harvard style):

1. Zou, A. et al. (2023) Universal and Transferable Adversarial Attacks on Aligned Language Models. arXiv:2307.15043.
2. Shin, T. et al. (2020) AutoPrompt: Eliciting Knowledge from Language Models with Automatically Generated Prompts. Proceedings of EMNLP 2020.
3. Yu, J. et al. (2023) GPTFuzzer: Red Teaming Large Language Models with Auto-Generated Jailbreak Prompts. arXiv:2309.10253.
4. Chao, P. et al. (2023) Jailbreaking Black Box Large Language Models in Twenty Queries. arXiv:2310.08419.
5. Zhou, W. et al. (2024) EasyJailbreak: A Unified Framework for Jailbreaking Large Language Models. arXiv:2403.12171.
6. Chu, J. et al. (2024) JailbreakRadar: Comprehensive Assessment of Jailbreak Attacks Against LLMs. arXiv:2402.05668.
7. Li, J. et al. (2023) HaluEval: A Large-Scale Hallucination Evaluation Benchmark for Large Language Models. Proceedings of EMNLP 2023.
8. Greshake, K. et al. (2023) Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection. arXiv:2302.12173.
9. Derczynski, L. et al. (2024) garak: A Framework for Security Probing Large Language Models. arXiv:2406.11036.
10. Gulyamov, S. et al. (2026) Prompt Injection Attacks in Large Language Models and AI Agent Systems: A Comprehensive Review of Vulnerabilities, Attack Vectors, and Defense Mechanisms. Information, 17(1), 54. doi:10.3390/info17010054.
11. Zhu, K. et al. (2023) PromptRobust: Towards Evaluating the Robustness of Large Language Models on Adversarial Prompts. arXiv:2306.04528.
12. Liu, D. et al. (2024) A Survey of Attacks on Large Vision-Language Models: Resources, Advances, and Future Trends. arXiv:2407.07403.
13. Wei, A., Haghtalab, N. and Steinhardt, J. (2023) Jailbroken: How Does LLM Safety Training Fail? Advances in Neural Information Processing Systems (NeurIPS 2023).
14. Perez, E. et al. (2022) Red Teaming Language Models with Language Models. Proceedings of EMNLP 2022.

Standards and datasets:

- OWASP Top 10 for LLM Applications 2025
- Shen, X. et al. (2024) "Do Anything Now": Characterizing and Evaluating In-The-Wild Jailbreak Prompts on Large Language Models. ACM CCS 2024
- JailbreakBench, HarmBench, SaTML CTF dataset, DeepTeam

## Author

Sajan Kunjumon, MSc Cyber Security, Anglia Ruskin University. Supervisor: Dr Shareeful Islam.

## Contact

For any enquiries, send me a message on GitHub ([@SajanGeorg](https://github.com/SajanGeorg)) or connect with me on LinkedIn ([Sajan George](https://www.linkedin.com/in/sajan-g/)).
