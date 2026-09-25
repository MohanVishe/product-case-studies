"""Smoke test: the committed results are exactly what analyze.py computes from the saved traces,
and the worked example in the article is exactly what cost_model.py computes."""
import json
import math
import shutil
from pathlib import Path

import pytest

import analyze
from cost_model import Config, break_even_price_ratio

RESULTS = Path(__file__).resolve().parents[1] / "cheaper-per-token" / "experiment" / "results"


@pytest.fixture(scope="module")
def recomputed(tmp_path_factory):
    out = tmp_path_factory.mktemp("results")
    for name in ("orchestrator.jsonl", "router.jsonl"):
        shutil.copy(RESULTS / name, out / name)
    old = analyze.RESULTS
    analyze.RESULTS = str(out)
    try:
        analyze.main()
    finally:
        analyze.RESULTS = old
    return out


def same(a, b):
    """Equal, except floats may differ in the last bits: Python 3.12 changed how sum() adds floats."""
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def test_committed_summary_json_matches_a_fresh_recompute(recomputed):
    fresh = json.loads((recomputed / "summary.json").read_text(encoding="utf-8"))
    committed = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    assert same(fresh, committed), "summary.json is stale: run `python analyze.py` and commit the result"


@pytest.mark.parametrize("name", ["summary.md", "regrade.md"])
def test_committed_results_match_a_fresh_recompute(recomputed, name):
    fresh = (recomputed / name).read_text(encoding="utf-8")
    committed = (RESULTS / name).read_text(encoding="utf-8").replace("\r\n", "\n")
    assert fresh == committed, f"{name} is stale: run `python analyze.py` and commit the result"


def test_headline_numbers(recomputed):
    s = json.loads((recomputed / "summary.json").read_text(encoding="utf-8"))
    small, large = s["orchestrator"]["qwen2.5-coder:3b"], s["orchestrator"]["qwen2.5-coder:7b"]
    assert (small["successes"], small["episodes"]) == (24, 120)
    assert (large["successes"], large["episodes"]) == (75, 120)
    orch, rout = s["comparisons"]
    assert round(orch["break_even_price_ratio"], 2) == 4.10
    assert round(orch["break_even_price_ratio_cached"], 2) == 4.24
    assert round(rout["break_even_price_ratio"], 2) == 1.13
    lo, hi = s["ci95_orchestrator"]["break_even_price_ratio"]
    assert 1.13 < lo < 4.10 < hi                      # the orchestrator gap is not noise
    assert s["router"]["qwen2.5-coder:3b"]["calls"] == 144 == 48 * 3


def test_worked_example():
    strong, cheap = Config("capable", 2.0, 3, 0.9), Config("cheaper", 0.5, 7, 0.6)
    assert round(cheap.cost_per_success() / strong.cost_per_success() - 1, 2) == 0.16
    assert round(break_even_price_ratio(strong, cheap), 2) == 4.62
    s3, c3 = (Config(n, p, t, r, cache_discount=0.1) for n, p, t, r in
              (("capable", 2.0, 3, 0.9), ("cheaper", 0.5, 7, 0.6)))
    assert round(c3.cost_per_success() / s3.cost_per_success() - 1, 2) == -0.27
    assert round(break_even_price_ratio(s3, c3), 2) == 2.92
    leaf_s, leaf_c = Config("capable", 2.0, 1, 0.98), Config("cheaper", 0.5, 1, 0.97)
    assert round(leaf_c.cost_per_success() / leaf_s.cost_per_success() - 1, 2) == -0.75


def test_every_figure_builds():
    import figures

    for name in list(figures.CONCEPT) + list(figures.EXPERIMENT):
        assert "<svg" in figures.to_svg(figures.build(name))
