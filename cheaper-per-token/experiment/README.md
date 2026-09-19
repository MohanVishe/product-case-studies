# The test agent and its evaluation

A small tool-calling agent, used as a test subject for the method in [`../article.md`](../article.md):
evaluate every node that calls a model, per completed task, on accuracy, latency and cost.

Everything runs locally through [Ollama](https://ollama.com). No API keys, no cost.

## What's here

| File | What it is |
|---|---|
| [`shop.py`](shop.py) | The environment: a made-up online homeware store with 8 customers, 8 products and 16 orders, 8 tools, and the agent's policy. In memory, reset for every conversation |
| [`agent.py`](agent.py) | The agent: one orchestrator model in a tool-calling loop. Every model call is recorded as a span with its node, model, tokens and latency |
| [`tasks.py`](tasks.py) | 24 graded conversations: 6 lookups, 6 multi-hop, 6 write actions and policy refusals, 6 multi-turn. Graded on the store's end state and on required facts |
| [`router.py`](router.py) | A leaf node, an intent router, with 48 labelled messages across 6 intents |
| [`harness.py`](harness.py) | Runs every model on every case k times. Resumable |
| [`analyze.py`](analyze.py) | Turns traces into metrics: pass^k, tokens and time per successful task, trajectory metrics, the break-even price ratio |
| [`results/`](results/) | Raw traces (`*.jsonl`, one line per conversation or call) and the computed `summary.json` / `summary.md` |

## Run it

```bash
ollama pull qwen2.5-coder:3b
ollama pull qwen2.5-coder:7b
python harness.py --node router --k 3
python harness.py --node orchestrator --k 5
python analyze.py
```

Then `python ../figures.py` redraws the charts. Standard library only, apart from `reportlab` for the figures. To try other models, pass `--models`, for example `--models llama3.2:3b qwen2.5:7b`.

## How it's graded

A conversation passes only if **all** of these hold:

- **End state.** The orders the task expects to change end in exactly the expected state, *and no other order changes*. Returns must match exactly. Where policy requires an escalation, a ticket must exist for that customer.
- **Required facts.** Each group of acceptable strings (a date in any common format, an order number, a price, an out-of-stock phrasing) must appear in the agent's replies.
- **No runaway loop.** A turn that hasn't produced a reply after 10 model calls fails.

The graders are deterministic, so the same trace always gets the same grade. They check facts and state, not tone.

## Design choices worth knowing

- **Tool calls as text.** These models often write tool calls as JSON in the reply instead of the structured field. The agent accepts both, is lenient about the tool name, and is strict about arguments. A call it can't parse, or one with arguments of the wrong type, goes back to the model as an error, and the model can retry. That's how production agent frameworks behave, and both models get the same parser.
- **Tokens, not dollars.** Local models have no price. Cost is reported as tokens per successful task, with output tokens weighted 4× (a typical output-to-input price ratio), and as the break-even price ratio: how many times cheaper per token the small model would have to be to cost the same per success. You can compare that number to any price sheet.
- **Token counts are uncached.** Ollama reports the full prompt length on every call, which is what an API bills without prompt caching. With caching, the context-growth part of the cost shrinks (see the article).
- **Latency is local.** Measured on one consumer GPU, with nothing else running on it. Absolute times won't match a hosted API. The comparison between the two models, per call against per task, is the point.
- **Scripted users.** Multi-turn conversations use fixed follow-up messages rather than a simulated user. That's deterministic and cheap, and easier than real users.
