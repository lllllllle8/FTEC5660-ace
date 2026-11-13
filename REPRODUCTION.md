# FTEC5660 Reproducibility Work: ACE on the Formula task

This fork of [ace-agent/ace](https://github.com/ace-agent/ace) (upstream commit `82709de`)
reproduces one result of *Agentic Context Engineering: Evolving Contexts for
Self-Improving Language Models* (Zhang et al., arXiv:2510.04618, ICLR 2026):
the **Formula** (XBRL financial numerical reasoning) accuracy of

* **R1** the base LLM with an empty context (paper: 67.5%), and
* **R2** ACE offline adaptation with ground-truth feedback (paper: 85.5%, Table 2, p. 8, Section 4.4;
  the 76.5% shown for ACE in the Formula panel of Figure 1 matches Table 2's *online* ACE row),

and makes one measurable modification (a robust answer grader, see below).

## AI assistance

This reproduction was carried out with Claude (Anthropic) as an AI assistant, which FTEC5660 permits
and encourages. Claude helped read the codebase, write the code changes on this branch, build the run
scripts and the Colab notebook, and draft the report. All experiments were run by me on Google Colab
with my own DeepSeek API key, and every reported number comes from those runs (see `repro_results/`).

## What changed vs upstream (one commit each)

| Commit | Purpose |
|---|---|
| Add DeepSeek as an OpenAI-compatible API provider | `--api_provider deepseek`, logs served model id, fingerprint, temperature per call |
| Add `--max_train/--max_val/--max_test` | deterministic first-N subsets for a budget-limited run |
| Save per-sample test predictions; count dropped samples; fix crash | enables offline re-scoring; exposes samples silently excluded from accuracy; fixes an `UnboundLocalError` |
| Modification: robust/tolerant grader option | `eval/finance/grading.py`, `--grader {strict,robust,tolerant}` (default `strict` = original) |
| tiktoken fallback | no crash when the encoding file cannot be downloaded |
| Reproduction scripts | `scripts/run_repro.sh`, `scripts/summarize.py`, this file |
| Colab notebook (2 commits) | `notebooks/colab_repro.ipynb`: pip install, key from Colab Secrets, Drive backup |
| Reproduction results | `repro_results/`: summary tables, per-question test predictions, learned playbooks |

## Install

```bash
git clone -b repro-ftec5660 https://github.com/lllllllle8/FTEC5660-ace.git
cd FTEC5660-ace
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv is not installed
uv sync                                            # Python 3.12, see .python-version
cp .env.example .env                               # then put your key in .env:
# DEEPSEEK_API_KEY=sk-...
```

Never commit `.env` (it is in `.gitignore`).

## Run on Google Colab

Open `notebooks/colab_repro.ipynb` in Colab (File → Upload notebook, or open it from GitHub).
It installs only `openai tiktoken python-dotenv` with pip, reads `DEEPSEEK_API_KEY` from Colab
Secrets, runs the stages below with `PY=python`, and copies `results/` and `logs/` to Google
Drive after each stage. A CPU runtime is enough.

### How the reported results were produced

The numbers in `repro_results/` come from the notebook above with the same scripts and settings
(`MODEL=deepseek-chat`, `TRIALS=3`, `MAX_TRAIN=60`, `MAX_VAL=100`, `EVAL_STEPS=20`), with four differences
in how it was run: (1) the `baseline` and `train` stages were started at the same time in the background
(`nohup ... &`) instead of one after the other, each writing to its own results folder; (2) `WORKERS=20`
instead of 10, which only changes how many API requests run in parallel, not the answers; (3) the optional
`robust_train` stage was run; (4) `PRICE_IN=0.14` and `PRICE_OUT=0.28` (USD per 1M tokens, DeepSeek list
price) were set for the cost estimate. The code was uploaded to Colab as a zip.

## Run locally

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

## Results

Formula test split (200 questions), `deepseek-chat` (served id `deepseek-flash`), temperature 0.

| Condition | Paper | Mine, strict grader (mean ± std) | Robust grader | Tolerant (±0.01) |
|---|---|---|---|---|
| Base LLM, empty playbook | 67.5 | 68.3 ± 1.3 (n=3) | 68.5 ± 1.0 | 72.7 ± 1.2 |
| ACE offline, GT feedback | 85.5 (500 train) | 83.8 ± 0.8 (n=3, 60 train) | 83.8 ± 0.8 | 87.0 ± 0.9 |
| ACE offline, robust-grader feedback | n/a | 81.0 (n=1) | 81.0 | 84.0 |

ACE improves accuracy by +15.5 points (paper: +18.0). About half of the gain comes from removing
ratio-versus-percent errors (16.3 to 0 per run), the rest from fewer wrong values (32.0 to 14.7).
Total API cost was under $1. Full tables, error taxonomy and cost: [repro_results/summary.md](repro_results/summary.md).

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
