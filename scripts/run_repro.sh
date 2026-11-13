#!/usr/bin/env bash
# FTEC5660 reproducibility runs: ACE on the Formula (XBRL numerical reasoning) task.
#
# Usage:  bash scripts/run_repro.sh <stage>
# Stages (run in this order):
#   smoke        5 test questions, checks the API key / endpoint (cost ~0)
#   baseline     R1: empty playbook, eval_only on the 200-question test split, TRIALS times
#   train        R2: ACE offline adaptation (with ground truth) on a train subset;
#                also runs an initial test (empty playbook) and a final test (best playbook)
#   ace_eval     R2: re-evaluate the learned best_playbook TRIALS-1 more times
#   summary      re-score all saved outputs with strict/robust/tolerant graders (modification)
#   robust_train OPTIONAL: repeat `train` with --grader robust as the Reflector's feedback signal
#   all          smoke + baseline + train + ace_eval + summary
#
# Environment overrides (defaults in brackets):
#   PY ["uv run python"]  MODEL [deepseek-chat]  TRIALS [3]  MAX_TRAIN [60]
#   MAX_VAL [100]  EVAL_STEPS [20]  WORKERS [10]  PRICE_IN / PRICE_OUT (USD per 1M tokens, optional)
set -euo pipefail

PY=${PY:-"uv run python"}
MODEL=${MODEL:-deepseek-chat}
PROVIDER=${PROVIDER:-deepseek}
TRIALS=${TRIALS:-3}
MAX_TRAIN=${MAX_TRAIN:-60}
MAX_VAL=${MAX_VAL:-100}
EVAL_STEPS=${EVAL_STEPS:-20}
WORKERS=${WORKERS:-10}
R=results

COMMON="--task_name formula --api_provider $PROVIDER --generator_model $MODEL \
 --reflector_model $MODEL --curator_model $MODEL --max_tokens 4096 --test_workers $WORKERS"

stage_smoke() {
  $PY -m eval.finance.run $COMMON --mode eval_only --max_test 5 --save_path $R/smoke
}

stage_baseline() {
  for t in $(seq 1 "$TRIALS"); do
    echo "=== baseline trial $t/$TRIALS ==="
    $PY -m eval.finance.run $COMMON --mode eval_only --save_path $R/baseline/t$t
  done
}

stage_train() {
  $PY -m eval.finance.run $COMMON --mode offline \
    --max_train "$MAX_TRAIN" --max_val "$MAX_VAL" \
    --eval_steps "$EVAL_STEPS" --save_steps "$EVAL_STEPS" \
    --num_epochs 1 --max_num_rounds 3 --curator_frequency 1 \
    --save_path $R/ace_train
}

latest_train_dir() {
  ls -d "$1"/ace_run_*_formula_offline 2>/dev/null | sort | tail -1
}

stage_ace_eval() {
  local td; td=$(latest_train_dir $R/ace_train)
  [ -n "$td" ] || { echo "No training run found in $R/ace_train"; exit 1; }
  echo "Using playbook: $td/best_playbook.txt"
  # trial 1 is the final test already run inside the training run
  for t in $(seq 2 "$TRIALS"); do
    echo "=== ACE eval trial $t/$TRIALS ==="
    $PY -m eval.finance.run $COMMON --mode eval_only \
      --initial_playbook_path "$td/best_playbook.txt" --save_path $R/ace_eval/t$t
  done
}

stage_robust_train() {
  $PY -m eval.finance.run $COMMON --mode offline --grader robust \
    --max_train "$MAX_TRAIN" --max_val "$MAX_VAL" \
    --eval_steps "$EVAL_STEPS" --save_steps "$EVAL_STEPS" \
    --num_epochs 1 --max_num_rounds 3 --curator_frequency 1 \
    --save_path $R/ace_robust_train
}

stage_summary() {
  local price=()
  [ -n "${PRICE_IN:-}" ] && price+=(--price_in "$PRICE_IN")
  [ -n "${PRICE_OUT:-}" ] && price+=(--price_out "$PRICE_OUT")
  local extra=()
  if ls -d $R/ace_robust_train/ace_run_* >/dev/null 2>&1; then
    extra+=(--cond ace_robust_fb "$R/ace_robust_train/ace_run_*/final_test_results.json")
  fi
  $PY scripts/summarize.py \
    --cond baseline "$R/baseline/t*/ace_run_*/test_test_results.json" \
    --cond baseline_in_train "$R/ace_train/ace_run_*/initial_test_results.json" \
    --cond ace "$R/ace_train/ace_run_*/final_test_results.json" \
    --cond ace "$R/ace_eval/t*/ace_run_*/test_test_results.json" \
    "${extra[@]}" \
    --train_dir "$R/ace_train/ace_run_*" "${price[@]}" \
    --out $R/summary
}

case "${1:-}" in
  smoke) stage_smoke ;;
  baseline) stage_baseline ;;
  train) stage_train ;;
  ace_eval) stage_ace_eval ;;
  robust_train) stage_robust_train ;;
  summary) stage_summary ;;
  all) stage_smoke; stage_baseline; stage_train; stage_ace_eval; stage_summary ;;
  *) sed -n 2,20p "$0"; exit 1 ;;
esac
