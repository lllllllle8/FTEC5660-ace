# Reproduction summary (Formula test split)

## Per run

| cond | run file | requested | scored | dropped | strict acc (orig.) | robust acc | tolerant acc | strict / requested | flips strict->robust | served model |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | results/baseline/t1/ace_run_20261113_062045_formula_eval_only/test_test_results.json | 200 | 200 | 0 | 68.5 | 68.5 | 72.0 | 68.5 | 0 | deepseek-flash |
| baseline | results/baseline/t2/ace_run_20261113_062126_formula_eval_only/test_test_results.json | 200 | 200 | 0 | 67.0 | 67.5 | 72.0 | 67.0 | 1 | deepseek-flash |
| baseline | results/baseline/t3/ace_run_20261113_062205_formula_eval_only/test_test_results.json | 200 | 200 | 0 | 69.5 | 69.5 | 74.0 | 69.5 | 0 | deepseek-flash |
| baseline_in_train | results/ace_train/ace_run_20261113_062044_formula_offline/initial_test_results.json | 200 | 200 | 0 | 70.0 | 71.5 | 75.0 | 70.0 | 3 | deepseek-flash |
| ace | results/ace_train/ace_run_20261113_062044_formula_offline/final_test_results.json | 200 | 200 | 0 | 83.0 | 83.0 | 86.0 | 83.0 | 0 | deepseek-flash |
| ace | results/ace_eval/t2/ace_run_20261113_064042_formula_eval_only/test_test_results.json | 200 | 200 | 0 | 84.5 | 84.5 | 87.5 | 84.5 | 0 | deepseek-flash |
| ace | results/ace_eval/t3/ace_run_20261113_064135_formula_eval_only/test_test_results.json | 200 | 200 | 0 | 84.0 | 84.0 | 87.5 | 84.0 | 0 | deepseek-flash |
| ace_robust_fb | results/ace_robust_train/ace_run_20261113_064030_formula_offline/final_test_results.json | 200 | 200 | 0 | 81.0 | 81.0 | 84.0 | 81.0 | 0 | deepseek-flash |

## Per condition (mean ± sample std over trials, %)

| cond | trials | strict (original) | robust (modified) | tolerant | strict / requested |
|---|---|---|---|---|---|
| baseline | 3 | 68.3 ± 1.3 | 68.5 ± 1.0 | 72.7 ± 1.2 | 68.3 ± 1.3 |
| baseline_in_train | 1 | 70.0 ± 0.0 | 71.5 ± 0.0 | 75.0 ± 0.0 | 70.0 ± 0.0 |
| ace | 3 | 83.8 ± 0.8 | 83.8 ± 0.8 | 87.0 ± 0.9 | 83.8 ± 0.8 |
| ace_robust_fb | 1 | 81.0 ± 0.0 | 81.0 ± 0.0 | 84.0 ± 0.0 | 81.0 ± 0.0 |

## Error taxonomy (summed over trials)

| cond | correct | format_or_precision | near_miss_1pct | no_parsable_number | percent_scale | rounding_0.01 | wrong_value |
|---|---|---|---|---|---|---|---|
| baseline | 410 | 1 | 14 | 5 | 49 | 25 | 96 |
| baseline_in_train | 140 | 3 | 4 | 0 | 14 | 7 | 32 |
| ace | 503 | 0 | 14 | 20 | 0 | 19 | 44 |
| ace_robust_fb | 162 | 0 | 5 | 4 | 4 | 6 | 19 |

## Example answers whose verdict flips (strict wrong -> robust right)

- [baseline] prediction `0.1045` vs label `0.1`
- [baseline_in_train] prediction `Insufficient information to calculate adjusted market capitalization; value of new shares = 170000000.0` vs label `170000000.0`
- [baseline_in_train] prediction `0.1045` vs label `0.1`
- [baseline_in_train] prediction `0.030225` vs label `0.03`

## Cost (from detailed_llm_logs)

| cond | run | calls | prompt tokens | completion tokens | sum call time (s) | est. USD |
|---|---|---|---|---|---|---|
| baseline | results/baseline/t1/ace_run_20261113_062045_formula_eval_only | 200 | 88127 | 48237 | 390 | 0.026 |
| baseline | results/baseline/t2/ace_run_20261113_062126_formula_eval_only | 200 | 88127 | 44214 | 381 | 0.025 |
| baseline | results/baseline/t3/ace_run_20261113_062205_formula_eval_only | 200 | 88127 | 50197 | 416 | 0.026 |
| ace | results/ace_eval/t2/ace_run_20261113_064042_formula_eval_only | 200 | 1072727 | 79270 | 535 | 0.172 |
| ace | results/ace_eval/t3/ace_run_20261113_064135_formula_eval_only | 200 | 1072727 | 70537 | 506 | 0.170 |

## Offline training run

Folder: `results/ace_train/ace_run_20261113_062044_formula_offline`

- Best validation accuracy: 93.0
- Best playbook: 52 bullets, 20359 chars
- All calls in this folder (train + val + initial/final test): 962 calls, 3099203 prompt tok, 299324 completion tok, est. $0.518
- Calls by role: generator=838, reflector=64, curator=60

| step | val acc | train pre-acc | train post-acc | playbook tokens |
|---|---|---|---|---|
| 20 | 85.0 | 55.0 | 75.0 | 2433 |
| 40 | 88.0 | 72.5 | 85.0 | 3522 |
| 60 | 93.0 | 76.7 | 85.0 | 5043 |
