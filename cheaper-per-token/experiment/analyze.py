"""Turn the raw traces into the numbers in the article.

    python analyze.py            # reads results/*.jsonl, writes results/summary.json,
                                 # results/summary.md and results/regrade.md

Everything is computed per node and per completed task, not per call:

  pass^k        probability that k independent runs of the same task *all* succeed
                (unbiased estimator, from tau-bench). pass^1 is the plain success rate.
  tokens/task   input and output tokens per *successful* task, i.e. all tokens spent,
                failures included, divided by the number of successes
  break-even    how many times cheaper per token the small model must be to cost the same
                per successful task: its tokens per success over the large model's
  latency       per call, per conversation (p50/p95), and expected time to a correct result

It also reports what the point estimates alone would hide:

  re-grading    every conversation is graded again with the current graders in tasks.py, so a
                grader fix changes the numbers without a re-run. Changed grades are listed in
                results/regrade.md
  95% CIs       percentile bootstrap, 10,000 resamples: over tasks for the orchestrator (all 5
                runs of a resampled task come with it), over messages for the router. Both
                models get the same resampled tasks, because they ran the same tasks with the
                same seeds, so the comparison stays paired
  caching       the orchestrator re-priced as if each call's re-sent prefix (the previous call's
                prompt in the same conversation) were billed at 10% of the input price
  latency fit   per-call latency regressed on output and input tokens: the intercept is the
                fixed cost of one request, the output slope gives the decode speed
"""
import json
import os
import random
import statistics as stats
from collections import defaultdict
from math import comb

from tasks import TASKS, grade

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.environ.get("EVAL_RESULTS", os.path.join(HERE, "results"))
OUTPUT_WEIGHT = 4        # output tokens usually cost ~4x input tokens; used for the blended count
CACHE_DISCOUNT = 0.1     # price multiplier on a cached prefix, for the caching re-pricing
BOOTSTRAP = 10_000
SEED = 0
ORDER_TOOLS = {"list_orders", "get_order", "cancel_order", "update_address", "request_return"}
TASK_BY_ID = {t["id"]: t for t in TASKS}


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


def ci(xs):
    """Central 95% percentile interval."""
    xs = sorted(xs)
    return [xs[int(0.025 * len(xs))], xs[int(0.975 * len(xs)) - 1]]


def ols(y, x1, x2):
    """Least squares y = a + b1*x1 + b2*x2. Returns (a, b1, b2)."""
    m1, m2, my = stats.mean(x1), stats.mean(x2), stats.mean(y)
    s11 = sum((a - m1) ** 2 for a in x1)
    s22 = sum((a - m2) ** 2 for a in x2)
    s12 = sum((a - m1) * (b - m2) for a, b in zip(x1, x2))
    s1y = sum((a - m1) * (c - my) for a, c in zip(x1, y))
    s2y = sum((b - m2) * (c - my) for b, c in zip(x2, y))
    det = s11 * s22 - s12 ** 2
    b1 = (s1y * s22 - s2y * s12) / det
    b2 = (s2y * s11 - s1y * s12) / det
    return my - b1 * m1 - b2 * m2, b1, b2


def regrade(rows):
    """Grade every saved conversation again with the current graders. Returns what changed."""
    changes = []
    for r in rows:
        passed, reasons = grade(TASK_BY_ID[r["task"]], r["snapshot"], r["replies"])
        if r["status"] != "ok":
            passed, reasons = False, reasons + [r["status"]]
        if passed != r["passed"]:
            changes.append({"model": r["model"], "task": r["task"], "seed": r["seed"],
                            "was": r["passed"], "now": passed, "reasons": reasons,
                            "replies": r["replies"]})
        r["passed"], r["reasons"] = passed, reasons
    return changes


def episode_tokens(r):
    """(blended tokens, blended tokens with each call's re-sent prefix billed at CACHE_DISCOUNT).

    The re-sent prefix of a call is taken to be the previous call's whole prompt in the same
    conversation. That holds here: prompt lengths never shrink within a conversation.
    """
    full = cached = 0.0
    prev = 0
    for s in r["spans"]:
        i, o = s["input_tokens"], s["output_tokens"]
        prefix = min(prev, i)
        full += blended(i, o)
        cached += CACHE_DISCOUNT * prefix + (i - prefix) + OUTPUT_WEIGHT * o
        prev = i
    return full, cached


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
        cached = sum(episode_tokens(r)[1] for r in rs)
        spans = [s for r in rs for s in r["spans"]]
        fixed, s_per_out, s_per_in = ols([s["latency_s"] for s in spans],
                                         [s["output_tokens"] for s in spans],
                                         [s["input_tokens"] for s in spans])

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
            "successes": succ, "success_rate": succ / len(rs),
            "pass_hat_k": {k: stats.mean(pass_hat_k(len(v), sum(v), k) for v in by_task.values())
                           for k in range(1, n_min + 1)},
            "tasks_passing_every_run": sum(all(v) for v in by_task.values()),
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
            "cached_blended_tokens_per_success": cached / max(succ, 1),
            "latency_per_call_s": stats.mean(call_lat),
            "latency_p50_s": pct(lat, 50), "latency_p95_s": pct(lat, 95),
            "latency_mean_s": stats.mean(lat),
            "time_per_success_s": sum(lat) / max(succ, 1),
            "latency_fit": {"calls": len(spans), "fixed_s_per_call": fixed,
                            "decode_tokens_per_s": 1 / s_per_out,
                            "s_per_1k_input_tokens": 1000 * s_per_in},
            "input_tokens_by_call": {i: stats.mean(v) for i, v in sorted(growth.items()) if len(v) >= 5},
            "conversations_reaching_call": {i: len(v) for i, v in sorted(growth.items()) if len(v) >= 5},
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
        fastest = min(rs, key=lambda r: r["latency_s"])
        messages = len({r["i"] for r in rs})
        out[model] = {
            "calls": len(rs), "messages": messages, "runs_per_message": len(rs) // max(messages, 1),
            "correct": correct, "accuracy": correct / len(rs),
            "unparseable": sum(r["predicted"] is None for r in rs) / len(rs),
            "input_tokens_per_call": stats.mean(r["input_tokens"] for r in rs),
            "output_tokens_per_call": stats.mean(r["output_tokens"] for r in rs),
            "blended_tokens_per_success": sum(tok) / max(correct, 1),
            "latency_per_call_s": stats.mean(r["latency_s"] for r in rs),
            "latency_p95_s": pct([r["latency_s"] for r in rs], 95),
            "fastest_call": {"latency_s": fastest["latency_s"], "input_tokens": fastest["input_tokens"],
                             "output_tokens": fastest["output_tokens"]},
        }
    return out


def compare(node, small, large):
    if not (small and large):
        return None
    out = {"node": node,
           "break_even_price_ratio": small["blended_tokens_per_success"] / large["blended_tokens_per_success"]}
    if "cached_blended_tokens_per_success" in small:
        out["break_even_price_ratio_cached"] = (small["cached_blended_tokens_per_success"]
                                                / large["cached_blended_tokens_per_success"])
    return out


def bootstrap_orchestrator(rows, small, large):
    """Paired bootstrap over tasks: resample the tasks, keep every run of each, for both models."""
    agg = defaultdict(lambda: [0, 0, 0.0, 0.0])          # (model, task) -> runs, passes, tokens, cached
    for r in rows:
        a = agg[(r["model"], r["task"])]
        full, cached = episode_tokens(r)
        a[0] += 1
        a[1] += r["passed"]
        a[2] += full
        a[3] += cached
    tasks = sorted({r["task"] for r in rows})
    rng = random.Random(SEED)
    res = defaultdict(list)
    for _ in range(BOOTSTRAP):
        sample = [rng.choice(tasks) for _ in tasks]
        tot = {}
        for m in (small, large):
            tot[m] = [sum(agg[(m, t)][j] for t in sample) for j in range(4)]
            res[f"success_rate:{m}"].append(tot[m][1] / tot[m][0])
        (n1, s1, t1, c1), (n2, s2, t2, c2) = tot[small], tot[large]
        res["success_rate_difference"].append(s2 / n2 - s1 / n1)
        if s1 and s2:                                     # break-even is undefined with 0 successes
            res["break_even_price_ratio"].append((t1 / s1) / (t2 / s2))
            res["break_even_price_ratio_cached"].append((c1 / s1) / (c2 / s2))
    out = {k: ci(v) for k, v in res.items()}
    out["resamples"] = BOOTSTRAP
    out["resamples_with_defined_break_even"] = len(res["break_even_price_ratio"])
    return out


def bootstrap_router(rows, small, large):
    """Paired bootstrap over the labelled messages, keeping every run of each message."""
    agg = defaultdict(lambda: [0, 0, 0.0])               # (model, message) -> runs, correct, tokens
    for r in rows:
        a = agg[(r["model"], r["i"])]
        a[0] += 1
        a[1] += r["correct"]
        a[2] += blended(r["input_tokens"], r["output_tokens"])
    msgs = sorted({r["i"] for r in rows})
    rng = random.Random(SEED)
    res = defaultdict(list)
    for _ in range(BOOTSTRAP):
        sample = [rng.choice(msgs) for _ in msgs]
        tps = {}
        for m in (small, large):
            n, c, tok = (sum(agg[(m, i)][j] for i in sample) for j in range(3))
            res[f"accuracy:{m}"].append(c / n)
            tps[m] = tok / max(c, 1)
        res["break_even_price_ratio"].append(tps[small] / tps[large])
    out = {k: ci(v) for k, v in res.items()}
    out["resamples"] = BOOTSTRAP
    return out


def weight_sensitivity(rows, small, large, weights=(1, 2, 4, 8)):
    """Orchestrator break-even at other output-token weights: how much the 4x assumption matters."""
    out = {}
    for w in weights:
        tps = {}
        for m in (small, large):
            rs = [r for r in rows if r["model"] == m]
            tok = sum(s["input_tokens"] + w * s["output_tokens"] for r in rs for s in r["spans"])
            tps[m] = tok / max(sum(r["passed"] for r in rs), 1)
        out[w] = tps[small] / tps[large]
    return out


def regrade_md(changes):
    lines = ["# Re-grading the saved traces", "",
             "The graders in [`tasks.py`](../tasks.py) were revised on 2026-09-25, after the run, to fix "
             "errors found in both directions (see its docstring). `analyze.py` grades every saved "
             "conversation again with the current graders; this file lists every conversation whose "
             "grade changed. Nothing was re-run: the traces are the ones recorded on 2026-09-20.", "",
             f"{len(changes)} grades changed: "
             f"{sum(c['was'] and not c['now'] for c in changes)} pass → fail, "
             f"{sum(c['now'] and not c['was'] for c in changes)} fail → pass.", "",
             "| Model | Task | Seed | Was | Now | Why, under the current graders | Replies (first 160 characters of each) |",
             "|---|---|---:|---|---|---|---|"]
    for c in sorted(changes, key=lambda c: (c["model"], c["task"], c["seed"])):
        rep = " / ".join((x or "").replace("\n", " ").replace("|", "\\|")[:160] for x in c["replies"])
        why = "; ".join(c["reasons"]).replace("|", "\\|") or "all checks pass"
        lines.append(f"| {c['model']} | {c['task']} | {c['seed']} | {'pass' if c['was'] else 'fail'} | "
                     f"{'pass' if c['now'] else 'fail'} | {why} | {rep} |")
    lines += ["", "Known limit: the graders check the facts each task asks for, not every statement in a "
              "reply. A reply can pass with a correct answer and a wrong incidental detail (for example, "
              "the right arrival date for an order it calls \"being processed\" when it has shipped). "
              "A hand-labelled pass over all 240 conversations, with grader agreement, is listed under "
              "Next in the experiment README."]
    return "\n".join(lines) + "\n"


def table(rows, cols):
    head = "| | " + " | ".join(c for c in cols) + " |\n|---|" + "---:|" * len(cols) + "\n"
    return head + "".join(f"| {name} | " + " | ".join(vals) + " |\n" for name, vals in rows)


def span(lo_hi, fmt):
    return f"{fmt.format(lo_hi[0])}–{fmt.format(lo_hi[1])}"


def main():
    orch_rows, rout_rows = load("orchestrator"), load("router")
    changes = regrade(orch_rows)
    orch, rout = orchestrator(orch_rows), router(rout_rows)
    models = sorted(set(orch) | set(rout), key=lambda m: ("7b" in m, m))
    small, large = (models + [None, None])[:2]
    summary = {"orchestrator": orch, "router": rout, "output_weight": OUTPUT_WEIGHT,
               "cache_discount": CACHE_DISCOUNT,
               "regraded": {"changed": len(changes),
                            "pass_to_fail": sum(c["was"] and not c["now"] for c in changes),
                            "fail_to_pass": sum(c["now"] and not c["was"] for c in changes)},
               "comparisons": [c for c in (
                   compare("orchestrator", orch.get(small), orch.get(large)),
                   compare("router", rout.get(small), rout.get(large))) if c]}
    if small in orch and large in orch:
        summary["ci95_orchestrator"] = bootstrap_orchestrator(orch_rows, small, large)
        summary["break_even_by_output_weight"] = weight_sensitivity(orch_rows, small, large)
    if small in rout and large in rout:
        summary["ci95_router"] = bootstrap_router(rout_rows, small, large)
    with open(os.path.join(RESULTS, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    if orch_rows:
        with open(os.path.join(RESULTS, "regrade.md"), "w", encoding="utf-8") as f:
            f.write(regrade_md(changes))

    md = []
    if orch:
        cols = [m for m in models if m in orch]
        g = lambda key, fmt: [fmt.format(orch[m][key]) for m in cols]
        k = min(o["trials_per_task"] for o in orch.values())
        cio = summary.get("ci95_orchestrator", {})
        md.append("### Orchestrator\n\n" + table([
            ("Success rate (pass^1)", [f"{orch[m]['success_rate']:.1%} ({orch[m]['successes']}/{orch[m]['episodes']})"
                                       for m in cols]),
            ("  95% CI, bootstrap over tasks", [span(cio[f"success_rate:{m}"], "{:.0%}") if cio else "" for m in cols]),
            (f"All {k} runs succeed (pass^{k})", [f"{orch[m]['pass_hat_k'][k]:.0%} "
                                                   f"({orch[m]['tasks_passing_every_run']}/{orch[m]['tasks']} tasks)"
                                                   for m in cols]),
            ("Model calls per conversation", g("calls_per_episode", "{:.2f}")),
            ("Tool errors per conversation", g("tool_errors_per_episode", "{:.2f}")),
            ("Identified customer first", g("identify_first_rate", "{:.0%}")),
            ("Tokens per conversation", g("blended_tokens_per_episode", "{:,.0f}")),
            ("**Tokens per successful task**", g("blended_tokens_per_success", "**{:,.0f}**")),
            ("Tokens per successful task, re-sent prefix at 10%", g("cached_blended_tokens_per_success", "{:,.0f}")),
            ("Latency per call (includes the fixed overhead below)", g("latency_per_call_s", "{:.2f} s")),
            ("Latency per conversation, p50 / p95",
             [f"{orch[m]['latency_p50_s']:.1f} / {orch[m]['latency_p95_s']:.1f} s" for m in cols]),
            ("**Time per successful task**", g("time_per_success_s", "**{:.1f} s**")),
        ], cols))
        md.append("By category:\n\n" + table(
            [(c, [f"{orch[m]['by_category'].get(c, 0):.0%}" for m in cols])
             for c in ["lookup", "multi-hop", "write", "multi-turn"]], cols))
        md.append("Latency fit, per model call (latency = fixed + output tokens / decode speed + input term):\n\n" + table([
            ("Fixed time per call", [f"{orch[m]['latency_fit']['fixed_s_per_call']:.2f} s" for m in cols]),
            ("Decode speed", [f"{orch[m]['latency_fit']['decode_tokens_per_s']:.0f} tokens/s" for m in cols]),
            ("Calls in the fit", [f"{orch[m]['latency_fit']['calls']:,}" for m in cols]),
        ], cols))
        at = 7
        md.append(f"Context growth: mean input tokens on the first and the {at + 1}th model call, over the "
                  f"conversations that reached that call:\n\n" + table([
                      ("Call 1", [f"{orch[m]['input_tokens_by_call'][0]:,.0f} (n={orch[m]['conversations_reaching_call'][0]})"
                                  for m in cols]),
                      (f"Call {at + 1}", [f"{orch[m]['input_tokens_by_call'][at]:,.0f} (n={orch[m]['conversations_reaching_call'][at]})"
                                          if at in orch[m]["input_tokens_by_call"] else "–" for m in cols]),
                  ], cols))
    if rout:
        cols = [m for m in models if m in rout]
        cir = summary.get("ci95_router", {})
        r0 = rout[cols[0]]
        md.append(f"### Router (leaf node)\n\n{r0['messages']} labelled messages × {r0['runs_per_message']} runs "
                  f"= {r0['calls']} calls per model.\n\n" + table([
                      ("Accuracy", [f"{rout[m]['accuracy']:.0%} ({rout[m]['correct']}/{rout[m]['calls']})" for m in cols]),
                      ("  95% CI, bootstrap over messages",
                       [span(cir[f"accuracy:{m}"], "{:.0%}") if cir else "" for m in cols]),
                      ("Tokens per correct call", [f"{rout[m]['blended_tokens_per_success']:,.0f}" for m in cols]),
                      ("Latency per call", [f"{rout[m]['latency_per_call_s']:.2f} s" for m in cols]),
                      ("Fastest call", [f"{rout[m]['fastest_call']['latency_s']:.2f} s for "
                                        f"{rout[m]['fastest_call']['output_tokens']} output tokens" for m in cols]),
                  ], cols))
    for c in summary["comparisons"]:
        key = "ci95_orchestrator" if c["node"] == "orchestrator" else "ci95_router"
        cis = summary.get(key, {})
        line = (f"- **{c['node']}**: the small model must be at least **{c['break_even_price_ratio']:.2f}x** "
                f"cheaper per token to cost the same per success")
        if "break_even_price_ratio" in cis:
            line += f" (95% CI {span(cis['break_even_price_ratio'], '{:.2f}')}x)"
        if "break_even_price_ratio_cached" in c:
            line += (f"; with each call's re-sent prefix billed at {CACHE_DISCOUNT:.0%}, "
                     f"**{c['break_even_price_ratio_cached']:.2f}x**")
            if "break_even_price_ratio_cached" in cis:
                line += f" (95% CI {span(cis['break_even_price_ratio_cached'], '{:.2f}')}x)"
        md.append(line + ".")
    if "break_even_by_output_weight" in summary:
        md.append("- **Output weight**: orchestrator break-even at output tokens weighted "
                  + ", ".join(f"{w}x: {v:.2f}x" for w, v in summary["break_even_by_output_weight"].items()) + ".")
    if "ci95_orchestrator" in summary:
        d = summary["ci95_orchestrator"]["success_rate_difference"]
        md.append(f"- **Success-rate gap** (large minus small): 95% CI {d[0] * 100:+.0f} to {d[1] * 100:+.0f} "
                  f"percentage points.")
    if orch_rows:
        rg = summary["regraded"]
        md.append(f"- **Re-graded** with the current graders: {rg['changed']} grades changed "
                  f"({rg['pass_to_fail']} pass -> fail, {rg['fail_to_pass']} fail -> pass); see `regrade.md`.")
    text = "\n".join(md)
    with open(os.path.join(RESULTS, "summary.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
