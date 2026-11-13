# FTEC5660 Reproducibility Work: ACE on the Formula task

This fork of [ace-agent/ace](https://github.com/ace-agent/ace) (upstream commit `82709de`)
reproduces one result of *Agentic Context Engineering: Evolving Contexts for
Self-Improving Language Models* (Zhang et al., arXiv:2510.04618, ICLR 2026):
the **Formula** (XBRL financial numerical reasoning) accuracy of

* **R1** the base LLM with an empty context (paper: 67.5%), and
* **R2** ACE offline adaptation with ground-truth feedback (paper: 85.5%, Table 2),

and makes one measurable modification (a robust answer grader, see below).

## What changed vs upstream (one commit each)

| Commit | Purpose |
|---|---|
| Add DeepSeek as an OpenAI-compatible API provider | `--api_provider deepseek`, logs served model id, fingerprint, temperature per call |
| Add `--max_train/--max_val/--max_test` | deterministic first-N subsets for a budget-limited run |
| Save per-sample test predictions; count dropped samples; fix crash | enables offline re-scoring; exposes samples silently excluded from accuracy; fixes an `UnboundLocalError` |
| Modification: robust/tolerant grader option | `eval/finance/grading.py`, `--grader {strict,robust,tolerant}` (default `strict` = original) |
| tiktoken fallback | no crash when the encoding file cannot be downloaded |
| Reproduction scripts | `scripts/run_repro.sh`, `scripts/summarize.py`, this file |

## Install

```bash
git clone <this repo> && cd ace
git checkout repro-ftec5660
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv is not installed
uv sync                                            # Python 3.12, see .python-version
cp .env.example .env                               # then put your key in .env:
# DEEPSEEK_API_KEY=sk-...
```

Never commit `.env` (it is in `.gitignore`).

## Run

```bash
bash scripts/run_repro.sh smoke       # 5 questions, checks the key works
bash scripts/run_repro.sh baseline    # R1: 3 x 200 test questions, empty playbook
bash scripts/run_repro.sh train       # R2: ACE offline on 60 train / 100 val, then final test
bash scripts/run_repro.sh ace_eval    # R2: 2 more test runs with the learned best_playbook
PRICE_IN=<usd per 1M input> PRICE_OUT=<usd per 1M output> \
bash scripts/run_repro.sh summary     # re-scores everything -> results/summary.md
# optional, if time and budget allow:
bash scripts/run_repro.sh robust_train   # ACE trained with the robust grader as feedback
bash scripts/run_repro.sh summary
```

Knobs (environment variables): `MODEL` (default `deepseek-chat`), `TRIALS` (3),
`MAX_TRAIN` (60), `MAX_VAL` (100), `EVAL_STEPS` (20), `WORKERS` (10), `PY` (`uv run python`).
Use `PY=python` if you installed the dependencies with pip instead of uv.

## Controlled variables

| Item | Paper | This reproduction |
|---|---|---|
| LLM (generator / reflector / curator) | DeepSeek-V3.1 (via SambaNova) | `deepseek-chat` via api.deepseek.com; served id logged in `detailed_llm_logs/*.json` (`served_model`) |
| Decoding | repo code: temperature 0.0 | temperature 0.0, max_tokens 4096 (hard-coded in `llm.py`) |
| Prompts | repo prompts | unchanged |
| Train / val / test | 500 / 300 / 200 | 60 / 100 / 200 (first N in file order) |
| Epochs, reflection rounds | repo defaults | 1 epoch, max 3 reflection rounds, curator every step |
| Grader | exact float equality | same for the reproduction; robust/tolerant only for the modification |

Results are not directly comparable to the paper because the served DeepSeek model
version and the training subset size differ.

## The modification

`eval/finance/data_processor.py` marks a Formula answer correct only if
`float(pred) == float(label)`. Answers such as `$40.00`, `15%`, `\boxed{7.5}` or an
unrounded `12.344` (label `12.34`) are scored wrong. The modification adds:

* `robust`: strip `$ , %`, LaTeX wrappers and unit words, take the number, round both sides to 2 dp;
* `tolerant`: same parsing, accept `|pred - label| <= 0.01`.

It is applied in two ways:

1. **Re-scoring** (no extra API cost): `scripts/summarize.py` re-grades every saved
   prediction with all three graders and reports the accuracy change, the answers that
   flip, and an error taxonomy.
2. **As training feedback** (optional `robust_train` stage): the Reflector is told an
   answer is correct or wrong using the robust grader, which changes what ACE learns.

## Output

`results/summary.md` contains: per-run accuracies under each grader, mean ± sample std
per condition, dropped samples, error taxonomy, example flipped answers, token usage and
estimated cost, and the validation curve plus playbook size of the training run.
