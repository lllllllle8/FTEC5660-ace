#!/usr/bin/env python3
"""
Summarise reproduction runs for the Formula task.

For every *_test_results.json matched by a condition glob, this script
  * re-scores the saved predictions with the strict (original), robust and
    tolerant graders (eval/finance/grading.py),
  * reports dropped samples and accuracy over *requested* samples,
  * builds an error taxonomy and lists answers whose verdict flips,
  * sums token usage / latency from detailed_llm_logs/,
and aggregates mean and sample std per condition.

Usage (from repo root):
  python scripts/summarize.py \
      --cond baseline "results/baseline/t*/ace_run_*/test_test_results.json" \
      --cond ace      "results/ace_train/ace_run_*/final_test_results.json" \
      --cond ace      "results/ace_eval/t*/ace_run_*/test_test_results.json" \
      --train_dir "results/ace_train/ace_run_*" \
      --out results/summary
Writes <out>.md and <out>.json.
"""
import argparse
import glob
import json
import os
import statistics
import sys
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval.finance.grading import GRADERS, classify_error  # noqa: E402


def load_records(path):
    with open(path) as f:
        d = json.load(f)
    tr = d.get("test_results", {})
    el = d.get("error_log", {}) or {}
    recs = el.get("records")
    if recs is None:
        # Fallback for result files produced by the unpatched upstream code:
        # only wrong answers are saved, correct ones are reconstructed as such.
        errs = el.get("errors", [])
        n_correct = tr.get("correct", 0)
        recs = [{"prediction": e["prediction"], "ground_truth": e["ground_truth"],
                 "is_correct": False} for e in errs]
        recs += [{"prediction": "__CORRECT_UNKNOWN__", "ground_truth": "__CORRECT_UNKNOWN__",
                  "is_correct": True}] * n_correct
    requested = tr.get("requested", len(recs))
    return recs, requested, tr


def score(recs, requested):
    out = {}
    n = len(recs)
    for g, fn in GRADERS.items():
        c = 0
        for r in recs:
            if r["prediction"] == "__CORRECT_UNKNOWN__":
                c += 1
            elif fn(r["prediction"], r["ground_truth"]):
                c += 1
        out[g] = c / n if n else 0.0
        out[g + "_correct"] = c
    out["scored"] = n
    out["requested"] = requested
    out["dropped"] = requested - n
    out["strict_over_requested"] = out["strict_correct"] / requested if requested else 0.0
    out["robust_over_requested"] = out["robust_correct"] / requested if requested else 0.0
    return out


def run_folder(test_file):
    return os.path.dirname(test_file)


def cost_of(folder, only_test_prefix=None):
    logs = glob.glob(os.path.join(folder, "detailed_llm_logs", "*.json"))
    tot = Counter()
    models = set()
    for p in logs:
        try:
            with open(p) as f:
                c = json.load(f)
        except Exception:
            continue
        cid = c.get("call_id", "")
        if only_test_prefix and not cid.startswith(only_test_prefix):
            continue
        tot["calls"] += 1
        tot["prompt_tokens"] += c.get("prompt_num_tokens", 0) or 0
        tot["completion_tokens"] += c.get("response_num_tokens", 0) or 0
        tot["call_seconds"] += c.get("call_time", 0) or 0
        tot["role_" + c.get("role", "?")] += 1
        if c.get("served_model"):
            models.add(c["served_model"])
    d = dict(tot)
    d["served_models"] = sorted(models)
    return d


def mean_std(xs):
    if not xs:
        return None, None
    m = statistics.mean(xs)
    s = statistics.stdev(xs) if len(xs) > 1 else 0.0
    return m, s


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cond", nargs=2, action="append", metavar=("NAME", "GLOB"), required=True)
    ap.add_argument("--train_dir", default=None, help="glob of the offline training run folder")
    ap.add_argument("--price_in", type=float, default=None, help="USD per 1M input tokens")
    ap.add_argument("--price_out", type=float, default=None, help="USD per 1M output tokens")
    ap.add_argument("--out", default="results/summary")
    a = ap.parse_args()

    runs = []
    for name, pattern in a.cond:
        for f in sorted(glob.glob(pattern)):
            recs, requested, tr = load_records(f)
            s = score(recs, requested)
            s["original_reported_accuracy"] = tr.get("accuracy")
            tax = Counter(classify_error(r["prediction"], r["ground_truth"])
                          for r in recs if r["prediction"] != "__CORRECT_UNKNOWN__")
            flips = [r for r in recs if r["prediction"] != "__CORRECT_UNKNOWN__"
                     and not GRADERS["strict"](r["prediction"], r["ground_truth"])
                     and GRADERS["robust"](r["prediction"], r["ground_truth"])]
            prefix = "test_eval_" if f.endswith("test_test_results.json") else None
            runs.append(OrderedDict(cond=name, file=f, **s, taxonomy=dict(tax),
                                    flips=flips[:10], n_flips=len(flips),
                                    cost=cost_of(run_folder(f), prefix)))

    conds = OrderedDict()
    for r in runs:
        conds.setdefault(r["cond"], []).append(r)

    agg = OrderedDict()
    for c, rs in conds.items():
        agg[c] = {g: mean_std([r[g] for r in rs]) for g in
                  ["strict", "robust", "tolerant", "strict_over_requested", "robust_over_requested"]}
        agg[c]["n_trials"] = len(rs)
        agg[c]["taxonomy"] = dict(sum((Counter(r["taxonomy"]) for r in rs), Counter()))

    train = None
    if a.train_dir:
        tds = sorted(glob.glob(a.train_dir))
        if tds:
            td = tds[-1]
            train = {"folder": td}
            tp = os.path.join(td, "train_results.json")
            if os.path.exists(tp):
                with open(tp) as f:
                    tj = json.load(f)
                train["best_val_accuracy"] = tj.get("best_accuracy")
                train["curve"] = [{"step": x["step"],
                                   "val_acc": (x.get("val_result") or {}).get("accuracy"),
                                   "pre_train_acc": x["train_result"]["pre_train_accuracy"],
                                   "post_train_acc": x["train_result"]["post_train_accuracy"],
                                   "playbook_tokens": x.get("playbook_num_tokens")}
                                  for x in tj.get("results", [])]
            bp = os.path.join(td, "best_playbook.txt")
            if os.path.exists(bp):
                txt = open(bp).read()
                train["best_playbook_chars"] = len(txt)
                train["best_playbook_bullets"] = sum(1 for l in txt.splitlines() if l.strip().startswith("["))
            train["cost_all_calls"] = cost_of(td)

    def usd(c):
        if a.price_in is None or a.price_out is None or not c:
            return None
        return c.get("prompt_tokens", 0) / 1e6 * a.price_in + c.get("completion_tokens", 0) / 1e6 * a.price_out

    L = ["# Reproduction summary (Formula test split)\n"]
    L.append("## Per run\n")
    L.append("| cond | run file | requested | scored | dropped | strict acc (orig.) | robust acc | tolerant acc | strict / requested | flips strict->robust | served model |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in runs:
        L.append(f"| {r['cond']} | {os.path.relpath(r['file'])} | {r['requested']} | {r['scored']} | {r['dropped']} | "
                 f"{pct(r['strict'])} | {pct(r['robust'])} | {pct(r['tolerant'])} | {pct(r['strict_over_requested'])} | "
                 f"{r['n_flips']} | {', '.join(r['cost'].get('served_models', [])) or '-'} |")
    L.append("\n## Per condition (mean ± sample std over trials, %)\n")
    L.append("| cond | trials | strict (original) | robust (modified) | tolerant | strict / requested |")
    L.append("|---|---|---|---|---|---|")
    for c, g in agg.items():
        f = lambda k: f"{pct(g[k][0])} ± {pct(g[k][1])}"
        L.append(f"| {c} | {g['n_trials']} | {f('strict')} | {f('robust')} | {f('tolerant')} | {f('strict_over_requested')} |")
    L.append("\n## Error taxonomy (summed over trials)\n")
    cats = sorted({k for g in agg.values() for k in g["taxonomy"]})
    L.append("| cond | " + " | ".join(cats) + " |")
    L.append("|---|" + "---|" * len(cats))
    for c, g in agg.items():
        L.append(f"| {c} | " + " | ".join(str(g["taxonomy"].get(k, 0)) for k in cats) + " |")
    L.append("\n## Example answers whose verdict flips (strict wrong -> robust right)\n")
    for r in runs:
        for fl in r["flips"][:5]:
            L.append(f"- [{r['cond']}] prediction `{fl['prediction']}` vs label `{fl['ground_truth']}`")
    L.append("\n## Cost (from detailed_llm_logs)\n")
    L.append("| cond | run | calls | prompt tokens | completion tokens | sum call time (s) | est. USD |")
    L.append("|---|---|---|---|---|---|---|")
    for r in runs:
        if not r["file"].endswith("test_test_results.json"):
            continue  # offline-run folders are costed once in the training section below
        c = r["cost"]
        u = usd(c)
        L.append(f"| {r['cond']} | {os.path.relpath(os.path.dirname(r['file']))} | {c.get('calls', 0)} | {c.get('prompt_tokens', 0)} | "
                 f"{c.get('completion_tokens', 0)} | {c.get('call_seconds', 0):.0f} | {'-' if u is None else f'{u:.3f}'} |")
    if train:
        c = train.get("cost_all_calls", {})
        u = usd(c)
        L.append(f"\n## Offline training run\n\nFolder: `{os.path.relpath(train['folder'])}`\n")
        L.append(f"- Best validation accuracy: {pct(train.get('best_val_accuracy'))}")
        L.append(f"- Best playbook: {train.get('best_playbook_bullets')} bullets, {train.get('best_playbook_chars')} chars")
        L.append(f"- All calls in this folder (train + val + initial/final test): {c.get('calls', 0)} calls, "
                 f"{c.get('prompt_tokens', 0)} prompt tok, {c.get('completion_tokens', 0)} completion tok"
                 + ("" if u is None else f", est. ${u:.3f}"))
        L.append(f"- Calls by role: " + ", ".join(f"{k[5:]}={v}" for k, v in c.items() if k.startswith("role_")))
        if train.get("curve"):
            L.append("\n| step | val acc | train pre-acc | train post-acc | playbook tokens |\n|---|---|---|---|---|")
            for x in train["curve"]:
                L.append(f"| {x['step']} | {pct(x['val_acc'])} | {pct(x['pre_train_acc'])} | {pct(x['post_train_acc'])} | {x['playbook_tokens']} |")

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out + ".md", "w") as f:
        f.write("\n".join(L) + "\n")
    with open(a.out + ".json", "w") as f:
        json.dump({"runs": runs, "aggregate": agg, "train": train}, f, indent=2, default=str)
    print("\n".join(L))
    print(f"\nWrote {a.out}.md and {a.out}.json")


if __name__ == "__main__":
    main()
