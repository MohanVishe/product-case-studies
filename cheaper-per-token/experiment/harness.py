"""Run the evaluation: every model on every task, k times, at each node.

    python harness.py --run 2 --node router --k 3          # run 2 (the default)
    python harness.py --run 2 --node orchestrator --k 5
    python harness.py --run 1 --node orchestrator --k 5    # run 1's configuration
    python harness.py --models qwen2.5-coder:3b --tasks L1 W3

Run 1 (2026-09-20) wrote to results/; run 2 writes to results-run2/. What differs:

  run 1   sparse tool docs (1 of 13 parameters described), router measured on its own at
          temperature 0.7, num_predict 512, no server metadata in the traces
  run 2   all 13 parameters described with an example each (shop.TOOLS_DOCUMENTED); the router
          at temperature 0, measured on its own *and* wired in front of the agent; num_predict
          1024; Ollama's own timings in every span; Ollama version, model digest and GPU in
          every trace

Results append to <results dir>/<node>.jsonl and the run resumes where it left off, so an
interrupted run loses nothing. A run refuses to resume on a different Ollama version or model
digest. Analyse with `analyze.py` (EVAL_RESULTS=<dir> for run 2).
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

import agent
from agent import chat, run_episode
from router import EXAMPLES, run_router
from shop import TOOLS, TOOLS_DOCUMENTED
from tasks import TASKS, grade

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["qwen2.5-coder:3b", "qwen2.5-coder:7b"]
RUNS = {
    1: {"dir": "results", "tools": TOOLS, "num_predict": 512, "router_temperature": 0.7,
        "router_in_pipeline": False},
    2: {"dir": "results-run2", "tools": TOOLS_DOCUMENTED, "num_predict": 1024,
        "router_temperature": 0.0, "router_in_pipeline": True},
}
RESULTS = None
CFG = None


def _get(path):
    with urllib.request.urlopen(f"{agent.OLLAMA}{path}", timeout=30) as r:
        return json.load(r)


def environment(model):
    """What produced a trace: server version, the model's full digest, and the GPU."""
    tags = {m["name"]: m for m in _get("/api/tags")["models"]}
    if model not in tags:
        raise SystemExit(f"error: {model} is not installed in Ollama; this harness never pulls models")
    try:
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                              "--format=csv,noheader"], capture_output=True, text=True,
                             timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        gpu = "unknown"
    return {"ollama_version": _get("/api/version")["version"], "ollama_host": agent.OLLAMA,
            "model_digest": tags[model]["digest"],
            "quantization": tags[model].get("details", {}).get("quantization_level"),
            "gpu": gpu}


def check_same_env(path, model, env):
    """Refuse to append to a run that was recorded on a different server or model build."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line) if line.strip() else {}
            old = r.get("env")
            if r.get("model") == model and old:
                for key in ("ollama_version", "model_digest"):
                    if old[key] != env[key]:
                        raise SystemExit(f"error: {path} has {model} recorded with {key}={old[key]}, "
                                         f"now {env[key]}; start a new results directory")


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
        env = environment(model) if CFG["run"] >= 2 else None
        if env:
            check_same_env(path, model, env)
        warm(model)
        router = None
        if CFG["router_in_pipeline"]:
            def router(text, seed, _m=model):
                return run_router(_m, text, seed, temperature=CFG["router_temperature"])
        for seed in range(k):
            for task in tasks:
                if (model, task["id"], seed) in seen:
                    continue
                tr = run_episode(model, task, seed, tools=CFG["tools"],
                                 num_predict=CFG["num_predict"], router=router)
                if env:
                    tr["run"], tr["env"] = CFG["run"], env
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
        env = environment(model) if CFG["run"] >= 2 else None
        if env:
            check_same_env(path, model, env)
        warm(model)
        for seed in range(k):
            for i, (text, label) in enumerate(EXAMPLES):
                if (model, i, seed) in seen:
                    continue
                span = run_router(model, text, seed, temperature=CFG["router_temperature"])
                span.update(i=i, seed=seed, label=label, correct=span["predicted"] == label)
                if env:
                    span["run"], span["env"] = CFG["run"], env
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(span) + "\n")
        print(f"router {model} done", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", choices=["orchestrator", "router", "all"], default="all")
    ap.add_argument("--models", nargs="+", default=MODELS)
    ap.add_argument("--k", type=int, default=5, help="trials per task")
    ap.add_argument("--tasks", nargs="*", help="subset of task ids")
    ap.add_argument("--run", type=int, choices=sorted(RUNS), default=2)
    a = ap.parse_args()
    CFG = {"run": a.run, **RUNS[a.run]}
    RESULTS = os.environ.get("EVAL_RESULTS", os.path.join(HERE, CFG["dir"]))
    os.makedirs(RESULTS, exist_ok=True)
    if a.node in ("router", "all"):
        run_router_eval(a.models, a.k)
    if a.node in ("orchestrator", "all"):
        run_orchestrator(a.models, a.k, a.tasks)
    sys.exit(0)
