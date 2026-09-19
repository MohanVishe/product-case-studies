"""Turn the raw traces into the numbers in the article.

    python analyze.py            # reads results/*.jsonl, writes results/summary.json and results/summary.md

Everything is computed per node and per completed task, not per call:

  pass^k        probability that k independent runs of the same task *all* succeed
                (unbiased estimator, from tau-bench). pass^1 is the plain success rate.
  tokens/task   input and output tokens per *successful* task, i.e. all tokens spent,
                failures included, divided by the number of successes
  break-even    how many times cheaper per token the small model must be to cost the same
                per successful task: its tokens per success over the large model's
  latency       per call, per conversation (p50/p95), and expected time to a correct result
"""
import json
import os
import statistics as stats
from collections import defaultdict
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.environ.get("EVAL_RESULTS", os.path.join(HERE, "results"))
OUTPUT_WEIGHT = 4        # output tokens usually cost ~4x input tokens; used for the blended count
ORDER_TOOLS = {"list_orders", "get_order", "cancel_order", "update_address", "request_return"}


def load(name):
    path = os.path.join(RESULTS, f"{name}.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return 0.0
    i = (len(xs) - 1) * p / 100
    lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def pass_hat_k(n, c, k):
    return comb(c, k) / comb(n, k) if n >= k else float("nan")


def blended(inp, out):
    return inp + OUTPUT_WEIGHT * out


def orchestrator(rows):
    out = {}
    for model in sorted({r["model"] for r in rows}):
        rs = [r for r in rows if r["model"] == model]
        by_task = defaultdict(list)
        for r in rs:
            by_task[r["task"]].append(r["passed"])
        n_min = min(len(v) for v in by_task.values())
        succ = sum(r["passed"] for r in rs)
        calls = [len(r["spans"]) for r in rs]
        inp = [sum(s["input_tokens"] for s in r["spans"]) for r in rs]
        outp = [sum(s["output_tokens"] for s in r["spans"]) for r in rs]
        lat = [sum(s["latency_s"] for s in r["spans"]) for r in rs]
        call_lat = [s["latency_s"] for r in rs for s in r["spans"]]
        tool_calls = [len(r["tool_events"]) for r in rs]
        tool_err = [sum(not e["ok"] for e in r["tool_events"]) for r in rs]
        malformed = sum(e["tool"].startswith("__malformed__") for r in rs for e in r["tool_events"])

        # policy 1: find the customer before touching their orders (tasks that give an email)
        ident = []
        for r in rs:
            names = [e["tool"] for e in r["tool_events"] if e["ok"]]
            touched = [i for i, n in enumerate(names) if n in ORDER_TOOLS]
            if touched:
                ident.append("find_customer" in names[:touched[0]])

        # input tokens by position of the call in the conversation: shows context growth
        growth = defaultdict(list)
        for r in rs:
            for i, s in enumerate(r["spans"]):
                growth[i].append(s["input_tokens"])

        cats = defaultdict(list)
        for r in rs:
            cats[r["cat"]].append(r["passed"])

        fails = defaultdict(int)
        for r in rs:
            if not r["passed"]:
                fails[classify_failure(r)] += 1

        out[model] = {
            "episodes": len(rs), "tasks": len(by_task), "trials_per_task": n_min,
            "success_rate": succ / len(rs),
            "pass_hat_k": {k: stats.mean(pass_hat_k(len(v), sum(v), k) for v in by_task.values())
                           for k in range(1, n_min + 1)},
            "by_category": {c: sum(v) / len(v) for c, v in cats.items()},
            "calls_per_episode": stats.mean(calls),
            "tool_calls_per_episode": stats.mean(tool_calls),
            "tool_errors_per_episode": stats.mean(tool_err),
            "malformed_calls": malformed,
            "loop_caps": sum(r["status"] == "loop_cap" for r in rs),
            "identify_first_rate": sum(ident) / len(ident) if ident else None,
            "input_tokens_per_episode": stats.mean(inp),
            "output_tokens_per_episode": stats.mean(outp),
            "blended_tokens_per_episode": stats.mean(blended(i, o) for i, o in zip(inp, outp)),
            "blended_tokens_per_success": sum(blended(i, o) for i, o in zip(inp, outp)) / max(succ, 1),
            "latency_per_call_s": stats.mean(call_lat),
            "latency_p50_s": pct(lat, 50), "latency_p95_s": pct(lat, 95),
            "latency_mean_s": stats.mean(lat),
            "time_per_success_s": sum(lat) / max(succ, 1),
            "input_tokens_by_call": {i: stats.mean(v) for i, v in sorted(growth.items()) if len(v) >= 5},
            "failure_modes": dict(fails),
        }
    return out


def classify_failure(r):
    """One coarse label per failed episode, for the failure-mode breakdown."""
    if r["status"] == "loop_cap":
        return "looped without answering"
    reasons = " ".join(r["reasons"])
    if any(e["tool"].startswith("__malformed__") for e in r["tool_events"]) and not any(
            e["ok"] for e in r["tool_events"]):
        return "never produced a usable tool call"
    if "status" in reasons or "address" in reasons or "returns" in reasons:
        return "wrong or missing action"
    if "ticket" in reasons:
        return "missed escalation"
    return "wrong or incomplete answer"


def router(rows):
    out = {}
    for model in sorted({r["model"] for r in rows}):
        rs = [r for r in rows if r["model"] == model]
        correct = sum(r["correct"] for r in rs)
        tok = [blended(r["input_tokens"], r["output_tokens"]) for r in rs]
        out[model] = {
            "calls": len(rs), "accuracy": correct / len(rs),
            "unparseable": sum(r["predicted"] is None for r in rs) / len(rs),
            "input_tokens_per_call": stats.mean(r["input_tokens"] for r in rs),
            "output_tokens_per_call": stats.mean(r["output_tokens"] for r in rs),
            "blended_tokens_per_success": sum(tok) / max(correct, 1),
            "latency_per_call_s": stats.mean(r["latency_s"] for r in rs),
            "latency_p95_s": pct([r["latency_s"] for r in rs], 95),
        }
    return out


def compare(node, small, large):
    if not (small and large):
        return None
    return {"node": node,
            "break_even_price_ratio": small["blended_tokens_per_success"] / large["blended_tokens_per_success"]}


def table(rows, cols):
    head = "| | " + " | ".join(c for c in cols) + " |\n|---|" + "---:|" * len(cols) + "\n"
    return head + "".join(f"| {name} | " + " | ".join(vals) + " |\n" for name, vals in rows)


def main():
    orch, rout = orchestrator(load("orchestrator")), router(load("router"))
    models = sorted(set(orch) | set(rout), key=lambda m: ("7b" in m, m))
    small, large = (models + [None, None])[:2]
    summary = {"orchestrator": orch, "router": rout, "output_weight": OUTPUT_WEIGHT,
               "comparisons": [c for c in (
                   compare("orchestrator", orch.get(small), orch.get(large)),
                   compare("router", rout.get(small), rout.get(large))) if c]}
    with open(os.path.join(RESULTS, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)

    md = []
    if orch:
        cols = [m for m in models if m in orch]
        g = lambda key, fmt: [fmt.format(orch[m][key]) for m in cols]
        k = min(o["trials_per_task"] for o in orch.values())
        md.append("### Orchestrator\n\n" + table([
            ("Success rate (pass^1)", g("success_rate", "{:.0%}")),
            (f"All {k} runs succeed (pass^{k})", [f"{orch[m]['pass_hat_k'][k]:.0%}" for m in cols]),
            ("Model calls per conversation", g("calls_per_episode", "{:.1f}")),
            ("Tool errors per conversation", g("tool_errors_per_episode", "{:.2f}")),
            ("Identified customer first", g("identify_first_rate", "{:.0%}")),
            ("Tokens per conversation", g("blended_tokens_per_episode", "{:,.0f}")),
            ("**Tokens per successful task**", g("blended_tokens_per_success", "**{:,.0f}**")),
            ("Latency per call", g("latency_per_call_s", "{:.2f} s")),
            ("Latency per conversation, p50 / p95",
             [f"{orch[m]['latency_p50_s']:.1f} / {orch[m]['latency_p95_s']:.1f} s" for m in cols]),
            ("**Time per successful task**", g("time_per_success_s", "**{:.1f} s**")),
        ], cols))
        md.append("By category:\n\n" + table(
            [(c, [f"{orch[m]['by_category'].get(c, 0):.0%}" for m in cols])
             for c in ["lookup", "multi-hop", "write", "multi-turn"]], cols))
    if rout:
        cols = [m for m in models if m in rout]
        md.append("### Router (leaf node)\n\n" + table([
            ("Accuracy", [f"{rout[m]['accuracy']:.0%}" for m in cols]),
            ("Tokens per correct call", [f"{rout[m]['blended_tokens_per_success']:,.0f}" for m in cols]),
            ("Latency per call", [f"{rout[m]['latency_per_call_s']:.2f} s" for m in cols]),
        ], cols))
    for c in summary["comparisons"]:
        md.append(f"- **{c['node']}**: the small model must be at least "
                  f"**{c['break_even_price_ratio']:.2f}x** cheaper per token to cost the same per success.")
    text = "\n".join(md)
    with open(os.path.join(RESULTS, "summary.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
