"""
Robust grading for the Formula (numerical reasoning) task.

Reproducibility modification (FTEC5660). The original grader in
data_processor.py compares answers with exact float equality:

    float(pred.replace(",", "")) == float(gt.replace(",", ""))

and falls back to raw string equality if parsing fails. That means a
mathematically correct answer is scored wrong when the model writes it
as "$40.00", "15%", "15.0 percent", "\\boxed{15}", "= 15.00." or rounds
the last digit differently (e.g. 12.345 -> 12.34 vs 12.35).

All Formula labels in the released test split have at most 2 decimals and
the prompt asks for "2 decimal places", so we compare after rounding to
2 decimals. A looser variant allows an absolute tolerance of 0.01 to
absorb intermediate-rounding differences.

Graders:
    strict    original behaviour (exact float equality)
    robust    normalise the string, then round both sides to 2 dp and compare
    tolerant  normalise the string, then |pred - gt| <= 0.01 (+1e-9)
"""
import math
import re
from typing import Optional

_NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def strict_is_correct(predicted: str, ground_truth: str) -> bool:
    """Exact copy of DataProcessor._formula_answer_is_correct (original)."""
    try:
        predicted = predicted.replace(",", "")
        ground_truth = ground_truth.replace(",", "")
        return float(predicted) == float(ground_truth)
    except Exception:
        return predicted == ground_truth


def parse_number(text) -> Optional[float]:
    """Extract a single numeric value from a model answer string.

    Removes currency symbols, thousands separators, percent signs, LaTeX
    wrappers and trailing punctuation. If several numbers remain, the
    last one is taken (e.g. "Operating Margin = 15.00" -> 15.0).
    Returns None if no number can be found.
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s or s == "No final answer found":
        return None
    s = re.sub(r"\\boxed\{([^}]*)\}", r"\1", s)
    s = s.replace("\\%", "%").replace("\\$", "$")
    s = s.replace("$", "").replace(",", "").replace("%", "")
    s = re.sub(r"(?i)\b(usd|dollars?|percent|per cent)\b", "", s)
    s = s.strip().rstrip(".").strip()
    try:
        return float(s)
    except ValueError:
        pass
    nums = _NUM_RE.findall(s)
    if not nums:
        return None
    try:
        return float(nums[-1])
    except ValueError:
        return None


def robust_is_correct(predicted: str, ground_truth: str) -> bool:
    p, g = parse_number(predicted), parse_number(ground_truth)
    if p is None or g is None:
        return False
    return math.isclose(round(p, 2), round(g, 2), abs_tol=1e-9)


def tolerant_is_correct(predicted: str, ground_truth: str, tol: float = 0.01) -> bool:
    p, g = parse_number(predicted), parse_number(ground_truth)
    if p is None or g is None:
        return False
    return abs(p - g) <= tol + 1e-9


GRADERS = {
    "strict": strict_is_correct,
    "robust": robust_is_correct,
    "tolerant": tolerant_is_correct,
}


def classify_error(predicted: str, ground_truth: str) -> str:
    """Rough error taxonomy used in the report."""
    p, g = parse_number(predicted), parse_number(ground_truth)
    if p is None:
        return "no_parsable_number"
    if g is None:
        return "bad_label"
    if strict_is_correct(predicted, ground_truth):
        return "correct"
    if robust_is_correct(predicted, ground_truth):
        return "format_or_precision"  # right value, wrong surface form or not rounded to 2 dp
    if tolerant_is_correct(predicted, ground_truth):
        return "rounding_0.01"        # off by one cent
    if g != 0 and (math.isclose(p, g * 100, rel_tol=1e-3) or math.isclose(p, g / 100, rel_tol=1e-3)):
        return "percent_scale"        # 0.15 vs 15
    if g != 0 and abs(p - g) / abs(g) <= 0.01:
        return "near_miss_1pct"       # within 1% relative
    return "wrong_value"
