# Reproduction results (Formula test split, 200 questions)

| Condition | Paper | Mine (strict grader, mean ± std) |
|---|---|---|
| Base LLM, empty playbook | 67.5 | 68.3 ± 1.3 (n=3) |
| ACE offline, GT feedback | 85.5 (500 train) | 83.8 ± 0.8 (n=3, 60 train) |
| ACE offline, robust-grader feedback | n/a | 81.0 (n=1) |

Model: `deepseek-chat` (served id `deepseek-flash`), temperature 0. Full tables: [summary.md](summary.md).
Learned playbook: `ace_train/ace_run_*/best_playbook.txt`.
