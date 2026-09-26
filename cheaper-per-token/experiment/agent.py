"""The test-subject agent: one orchestrator model in a tool-calling loop, fully instrumented.

Every model call is recorded as a span tagged with the node that made it, its model, its input
and output tokens, and its wall-clock latency. That per-node record is the whole point: without
it, the cost of extra turns disappears into one blended number.
"""
import json
import os
import re
import time
import urllib.request

from shop import SYSTEM_PROMPT, TOOLS, Shop

# 127.0.0.1, not localhost: run 1 used the localhost default, and its ~2 s fixed cost per request
# was suspected to be Windows trying IPv6 first. Run 2 uses the IPv4 address directly.
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MAX_CALLS_PER_TURN = 10          # a loop that hasn't answered after 10 model calls has failed
NUM_CTX = 16384
CPU_ONLY = ({"num_gpu": 0, "num_thread": int(os.environ.get("EVAL_THREADS", 4))}
            if os.environ.get("EVAL_CPU_ONLY") else {})   # for smoke tests


def chat(model, messages, tools=None, temperature=0.7, seed=0, num_predict=512, options=None):
    """One call to a local model through Ollama. Returns (message, span)."""
    body = {"model": model, "messages": messages, "stream": False, "keep_alive": "15m",
            "options": {"temperature": temperature, "seed": seed, "num_ctx": NUM_CTX,
                        "num_predict": num_predict, **CPU_ONLY, **(options or {})}}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(f"{OLLAMA}/api/chat", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.load(r)
    wall = time.perf_counter() - t0 - d.get("load_duration", 0) / 1e9
    # Ollama reports the full prompt length even when its prefix cache is hit, which is what an
    # API without prompt caching would bill for.
    span = {"model": model, "input_tokens": d.get("prompt_eval_count", 0),
            "output_tokens": d.get("eval_count", 0), "latency_s": round(wall, 3),
            # Ollama's own timings (run 2 onwards), so model time and request overhead separate
            "prompt_eval_s": round(d.get("prompt_eval_duration", 0) / 1e9, 4),
            "eval_s": round(d.get("eval_duration", 0) / 1e9, 4),
            "load_s": round(d.get("load_duration", 0) / 1e9, 4),
            "total_s": round(d.get("total_duration", 0) / 1e9, 4)}
    return d["message"], span


_HEAD = re.compile(r'\{\s*"name"\s*:\s*"?([A-Za-z_]\w*)"?\s*,\s*"arguments"\s*:\s*')
MALFORMED = "__malformed__"


def _balanced(text, i):
    """The {...} object starting at text[i], or None if the braces never close."""
    depth, in_str, esc = 0, False, False
    for j in range(i, len(text)):
        c = text[j]
        if in_str:
            esc, in_str = (not esc and c == "\\"), (in_str if esc or c != '"' else False)
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    return None


def parse_tool_calls(msg):
    """Native tool calls if the model produced them; otherwise tool calls written as text.

    Many open models (these included) write calls as JSON in the reply instead of using the
    structured field, and smaller ones often get the JSON slightly wrong. The parser is lenient
    about the name (quoted or not) and strict about the arguments: a call whose arguments don't
    parse comes back as MALFORMED, and the loop tells the model so and lets it retry, which is
    what production agent frameworks do. Both models get the same parser.
    """
    if msg.get("tool_calls"):
        return [(c["function"]["name"], c["function"].get("arguments") or {}) for c in msg["tool_calls"]], "native"
    text = msg.get("content") or ""
    calls = []
    for m in _HEAD.finditer(text):
        blob = _balanced(text, m.end()) if text[m.end():m.end() + 1] == "{" else None
        try:
            args = json.loads(blob) if blob else None
        except json.JSONDecodeError:
            args = None
        calls.append((m.group(1), args) if isinstance(args, dict) else (MALFORMED, m.group(1)))
    if not calls and '"arguments"' in text and '"name"' in text:
        calls.append((MALFORMED, None))
    return calls, ("text" if calls else None)


def run_episode(model, task, seed, temperature=0.7, tools=TOOLS, num_predict=512, router=None):
    """Run one conversation. Returns a trace: every span, every tool call, the replies, the end state.

    router: None (run 1), or a callable (message, seed) -> router span. When given, every
    customer message goes through the router first and its label is passed to the orchestrator
    as a system note just before the message: the router sits in front of the agent, and both
    nodes' spans are recorded in the same trace (router spans in `router_spans`).
    """
    shop = Shop()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    spans, tool_events, replies, router_spans = [], [], [], []
    status = "ok"
    t_start = time.perf_counter()

    for turn, user_msg in enumerate(task["user"]):
        if router is not None:
            rspan = router(user_msg, seed * 1000 + turn * 50)
            rspan["turn"] = turn
            router_spans.append(rspan)
            messages.append({"role": "system",
                             "content": f"Intent router: this message is {rspan['predicted'] or 'unclassified'}."})
        messages.append({"role": "user", "content": user_msg})
        reply = None
        for step in range(MAX_CALLS_PER_TURN):
            msg, span = chat(model, messages, tools, temperature, seed * 1000 + turn * 50 + step,
                             num_predict=num_predict)
            calls, fmt = parse_tool_calls(msg)
            span.update(node="orchestrator", turn=turn, step=step, tool_calls=len(calls), call_format=fmt)
            spans.append(span)

            if not calls:
                reply = msg.get("content") or ""
                messages.append({"role": "assistant", "content": reply})
                break

            if fmt == "native":
                messages.append({"role": "assistant", "content": msg.get("content") or "",
                                 "tool_calls": msg["tool_calls"]})
            else:
                messages.append({"role": "assistant", "content": msg.get("content") or ""})
            for name, args in calls:
                if name == MALFORMED:
                    result, ok = {"error": "tool call could not be parsed; reply with valid JSON: "
                                           '{"name": "<tool>", "arguments": {...}}'}, False
                    name, args = f"{MALFORMED}:{args}", None
                else:
                    result, ok = shop.call(name, args)
                tool_events.append({"turn": turn, "step": step, "tool": name, "args": args,
                                    "ok": ok, "error": result.get("error") if not ok else None})
                messages.append({"role": "tool", "content": json.dumps(result), "tool_name": name})
        else:
            status = "loop_cap"
        replies.append(reply)
        if status != "ok":
            break

    trace = {"task": task["id"], "cat": task["cat"], "model": model, "seed": seed,
             "status": status, "spans": spans, "tool_events": tool_events, "replies": replies,
             "snapshot": shop.snapshot(), "wall_s": round(time.perf_counter() - t_start, 3)}
    if router is not None:
        trace["router_spans"] = router_spans
    return trace
