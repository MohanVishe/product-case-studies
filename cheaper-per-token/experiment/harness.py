"""Run the evaluation: every model on every task, k times, at each node.

    python harness.py                       # both nodes, both models, k=5
    python harness.py --node router --k 3
    python harness.py --models qwen2.5-coder:3b --tasks L1 W3

Results append to results/<node>.jsonl and the run resumes where it left off, so an interrupted
run loses nothing. Analyse with analyze.py.
"""
import argparse
import json
import os
import sys

from agent import chat, run_episode
from router import EXAMPLES, run_router
from tasks import TASKS, grade

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.environ.get("EVAL_RESULTS", os.path.join(HERE, "results"))
MODELS = ["qwen2.5-coder:3b", "qwen2.5-coder:7b"]


def done_keys(path, key):
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {key(json.loads(line)) for line in f if line.strip()}


def warm(model):
    chat(model, [{"role": "user", "content": "hi"}], num_predict=1)


def run_orchestrator(models, k, task_ids):
    path = os.path.join(RESULTS, "orchestrator.jsonl")
    seen = done_keys(path, lambda r: (r["model"], r["task"], r["seed"]))
    tasks = [t for t in TASKS if not task_ids or t["id"] in task_ids]
    for model in models:
        warm(model)
        for seed in range(k):
            for task in tasks:
                if (model, task["id"], seed) in seen:
                    continue
                tr = run_episode(model, task, seed)
                tr["passed"], tr["reasons"] = grade(task, tr["snapshot"], tr["replies"])
                if tr["status"] != "ok":
                    tr["passed"] = False
                    tr["reasons"].append(tr["status"])
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(tr) + "\n")
                n_calls = len(tr["spans"])
                print(f"{model:18} {task['id']} k={seed} {'PASS' if tr['passed'] else 'fail'} "
                      f"calls={n_calls} {tr['wall_s']:.1f}s {'; '.join(tr['reasons'])[:90]}", flush=True)


def run_router_eval(models, k):
    path = os.path.join(RESULTS, "router.jsonl")
    seen = done_keys(path, lambda r: (r["model"], r["i"], r["seed"]))
    for model in models:
        warm(model)
        for seed in range(k):
            for i, (text, label) in enumerate(EXAMPLES):
                if (model, i, seed) in seen:
                    continue
                span = run_router(model, text, seed)
                span.update(i=i, seed=seed, label=label, correct=span["predicted"] == label)
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(span) + "\n")
        print(f"router {model} done", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", choices=["orchestrator", "router", "all"], default="all")
    ap.add_argument("--models", nargs="+", default=MODELS)
    ap.add_argument("--k", type=int, default=5, help="trials per task")
    ap.add_argument("--tasks", nargs="*", help="subset of task ids")
    a = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)
    if a.node in ("router", "all"):
        run_router_eval(a.models, a.k)
    if a.node in ("orchestrator", "all"):
        run_orchestrator(a.models, a.k, a.tasks)
    sys.exit(0)
