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
| [`router.py`](router.py) | A separate leaf-node task: a single-call intent router with its own 48 labelled messages across 6 intents. The agent does not call it; it is a second measurement on the same two models, in the same domain |
| [`harness.py`](harness.py) | Runs every model on every case k times. Resumable |
| [`analyze.py`](analyze.py) | Turns traces into metrics: pass^k, tokens and time per successful task, trajectory metrics, the break-even price ratio, bootstrap confidence intervals, a caching re-pricing and a latency fit. Re-grades the saved traces with the current graders |
| [`results-run2/`](results-run2/) | Run 2 (2026-09-26): its traces and computed results, see [Run 2](#run-2-2026-09-26) |
| [`results/`](results/) | Run 1: raw traces (`*.jsonl`, one line per conversation or call), the computed [`summary.md`](results/summary.md) / `summary.json`, and [`regrade.md`](results/regrade.md), every grade the current graders changed |

## Recompute the results

From the repository root, with [uv](https://docs.astral.sh/uv/):

```bash
uv sync                                                  # Python 3.11+, reportlab pinned in uv.lock
uv run python cheaper-per-token/experiment/analyze.py    # traces -> results/summary.* and regrade.md
uv run python cheaper-per-token/figures.py               # redraw the SVG figures
uv run pytest                                            # graders, and a check that results/ matches a fresh recompute
```

`analyze.py` itself needs only the standard library (`python analyze.py` from this folder works too).

## Re-run the experiment

```bash
ollama pull qwen2.5-coder:3b
ollama pull qwen2.5-coder:7b
python harness.py --run 1 --node router --k 3          # run 1's configuration, into results/
python harness.py --run 1 --node orchestrator --k 5
python analyze.py
# run 2: see "Run 2" below
```

To try other models, pass `--models`, for example `--models llama3.2:3b qwen2.5:7b`.

## Setup of the published run

| | |
|---|---|
| Run date | 2026-09-20, GPU otherwise idle |
| Models | `qwen2.5-coder:3b` (Ollama ID `f72c60cabf62`, 3.1B parameters) and `qwen2.5-coder:7b` (ID `dae161e27b0e`, 7.6B), both Q4_K_M |
| Model licences | Qwen2.5-Coder 3B: Qwen Research License; Qwen2.5-Coder 7B: Apache 2.0 (as shipped with the Ollama models) |
| Runtime | Ollama 0.34 (0.34.2 installed when this was written up; the traces don't record the patch version), `OLLAMA_HOST` default `http://localhost:11434` |
| Hardware | NVIDIA GeForce RTX 3070, 8 GB, Windows 11 |
| Python | 3.14 |
| Sampling | Temperature 0.7 at both nodes; seeds paired across models (same seed per task, turn and step); `num_ctx` 16384; `num_predict` 512 (orchestrator), 24 (router) |
| Repeats | Orchestrator: 24 tasks × 5 runs = 120 conversations per model. Router: 48 messages × 3 runs = 144 calls per model |

The model IDs are the short digests from `ollama list`. Both models were last modified on
2026-09-16/17, before the run, so they are the models that produced the traces.

## How it's graded

A conversation passes only if **all** of these hold:

- **End state.** The orders the task expects to change end in exactly the expected state, *and no other order changes*. Returns must match exactly. Where policy requires an escalation, a ticket must exist for that customer; where the policy doesn't block the request, no ticket may be opened.
- **Required facts.** Each group of acceptable strings (a date in any common format, an order number, a price) must appear in the agent's replies. Stock answers are checked sentence by sentence and are negation-aware: "we don't have any in stock" counts as out of stock, and "not in stock" doesn't count as in stock.
- **The reply matches what happened.** On write tasks the reply must confirm the change it made (the order number and the action). On W6, the refusal must give the actual reason (the order belongs to someone else) and must not claim a status the order doesn't have.
- **No runaway loop.** A turn that hasn't produced a reply after 10 model calls fails.

The graders are deterministic, so the same trace always gets the same grade. They check facts and
state, not tone.

**The graders were revised after the run** (2026-09-25), to fix errors in both directions found on
review: 3 correct answers failed on "don't have any … in stock" phrasing, and 6 wrong replies passed
on state alone (for example, the 7B telling the customer that order 1056 had been "delivered" when it
is processing and belongs to someone else). `analyze.py` re-grades the saved traces, so nothing was
re-run; [`results/regrade.md`](results/regrade.md) lists all 9 changed grades with the replies that
decided them. The effect on the headline numbers:

| | Original graders | Revised graders |
|---|---:|---:|
| 3B success | 22% (26/120) | 20% (24/120) |
| 7B success | 63% (76/120) | 62.5% (75/120) |
| Tokens per successful task, 3B / 7B | 27,946 / 7,285 | 30,274 / 7,382 |
| Time per successful task, 3B / 7B | 51.7 s / 17.6 s | 56.0 s / 17.8 s |
| Break-even price ratio, orchestrator | 3.84× | 4.10× |
| pass^5, 3B / 7B | 4% / 50% | 4% / 50% |

The router's grades are exact label matches and didn't change.

## Uncertainty

24 tasks is a small set, so every headline number comes with a 95% interval: a percentile bootstrap
with 10,000 resamples, over tasks for the orchestrator (each resampled task brings all 5 of its
runs) and over messages for the router. Both models get the same resampled tasks, since they ran
the same tasks on the same seeds, which keeps the comparison paired.

| | Estimate | 95% CI |
|---|---:|---:|
| 3B success rate | 20% | 10–32% |
| 7B success rate | 62.5% | 45–79% |
| Gap, 7B minus 3B | +42.5 points | +27 to +59 points |
| Break-even price ratio, orchestrator | 4.10× | 2.41–7.52× |
| Break-even price ratio, router | 1.13× | 1.04–1.24× |
| Router accuracy, 3B / 7B | 87% / 98% | 80–93% / 94–100% |

The intervals are wide, and the conclusion survives them: the orchestrator's lower bound (2.41×) is
still twice the router's upper bound (1.24×).

## Design choices worth knowing

- **Tool calls as text.** Neither model used Ollama's structured tool-call field: all 374 (3B) and 359 (7B) tool-calling replies wrote the call as JSON in the text. The agent accepts both, is lenient about the tool name, and is strict about arguments. A call it can't parse, or one with arguments of the wrong type, goes back to the model as an error, and the model can retry. Both models get the same parser. The result is sent back as a `tool` message after an assistant message with no `tool_calls`, which is how it was run.
- **Sparse tool docs.** Only 1 of the 13 tool parameters has a description (`find_customer.query`). The 3B's most common errors trace back to that: 117 of its 377 rejected calls copied the parameter schema into the argument (`argument 'query' must be a string`), and many passed an email where `list_orders` wanted a customer ID. So the measured gap is a gap *under this tool interface*: small models look more sensitive to it.
- **Output cap.** `num_predict` was 512; 9 of the 3B's calls hit it, none of the 7B's.
- **Tokens, not dollars.** Local models have no price. Cost is reported as tokens per successful task, with output tokens weighted 4× (a typical output-to-input price ratio), and as the break-even price ratio: how many times cheaper per token the small model would have to be to cost the same per success. You can compare that number to any price sheet. It barely depends on the weight: 3.96× at 1× and 4.26× at 8× (in `summary.md`).
- **Token counts are uncached**, which is what an API bills without prompt caching: Ollama reports the full prompt length on every call. `analyze.py` also re-prices the traces as if each call's re-sent prefix (the previous call's prompt in the same conversation) were billed at 10%. The break-even ratio goes from 4.10× to **4.24×** (95% CI 2.63–7.61×), slightly *wider*. Caching flips the article's worked example, but not this measured result, because here the gap comes from the success rate rather than from context growth.
- **Latency includes a fixed overhead per request.** A regression of per-call latency on tokens gives an intercept of 1.94 s (3B) and 2.18 s (7B), and the fastest call in the whole run, a router call with 3 output tokens, took 2.06 s (the fastest orchestrator call took 2.19 s). The implied decode speed is about 163 tokens/s for the 3B against 76 for the 7B, so the 3B is roughly twice as fast per token, yet per-call latency comes out at 2.63 s against 2.58 s. **Per-call latency parity is an artifact of the harness**, and so is most of the run's 56 minutes (about 1,318 calls × ~2 s). Per-conversation and per-success times are still comparable between models, since both pay the same overhead per call; they track call count and success rate, not model speed. The likely cause is the `localhost` default on Windows trying IPv6 first; that is unconfirmed, because Ollama's own timings weren't saved.
- **Scripted users.** Multi-turn conversations use fixed follow-up messages rather than a simulated user. That's deterministic and cheap, and easier than real users.
- **Context growth by call number** is averaged over the conversations that reached that call, so late calls are a selected sample: by the 8th call, 21 of the 3B's conversations (every one of them a conversation that hit the loop cap) against 9 of the 7B's.

## Limitations

- Two models from one family, at one size gap, on one small domain, with text-mode tool calls and sparse parameter docs. The method transfers; the numbers don't.
- The orchestrator and the router are separate measurements. The agent does not route through the router, so the two break-even ratios describe two kinds of node, not one pipeline.
- The graders were revised after seeing the traces. Every changed grade is published, but the grader has not been checked against human labels.
- The router ran at temperature 0.7, like the agent, and its sample is 48 distinct messages, repeated 3 times.

## Run 2 (2026-09-26)

A second run with the setup changes listed under Next in run 1. Run 1's traces, results and
write-ups above are unchanged; run 2 lives in [`results-run2/`](results-run2/)
([`summary.md`](results-run2/summary.md), `summary.json`, [`regrade.md`](results-run2/regrade.md)).

**What changed from run 1** (Next items 1, 3, 4 and 5):

| | Run 1 | Run 2 |
|---|---|---|
| Tool parameter docs | 1 of 13 described | all 13 described, each with an example value (`shop.TOOLS_DOCUMENTED`); the examples (customer `C09`, order `1234`, sku `P999`) are not in the store, so they show the format without hinting at an answer |
| Router | standalone, temperature 0.7 | temperature 0, standalone (48 × 3) **and** in front of the agent: each customer message is classified first, and the label goes to the orchestrator as a system note; both nodes' spans are in the same trace |
| Ollama endpoint | `http://localhost:11434` | `http://127.0.0.1:11434` |
| Per-span timings | wall clock only | plus Ollama's `prompt_eval_duration`, `eval_duration`, `load_duration`, `total_duration` |
| `num_predict` (orchestrator) | 512 | 1024 |
| Provenance in every trace | none | Ollama version (0.34.2), full model digest, quantisation, GPU (RTX 3070, 8 GB, driver 610.88) |
| Graders | revised after the run | frozen before it: `tests/test_graders_frozen.py` pins `tasks.py` and `router.py` by hash, committed (`ab40705`) before the first run-2 trace; 0 grades changed on re-grading |

Unchanged: the same two models with the same digests (`f72c60cabf62…`, `dae161e27b0e…`), the
same 24 tasks, 5 seeds, the same seeds per call, temperature 0.7 at the orchestrator, the same
graders and the same analysis. Not done from run 1's Next: item 2 (a current model pair with
native tool calling) needs models that are not installed locally, and this run downloads
nothing; item 6 (hand-labelling all conversations) needs a human labeller.

Commands (from this folder):

```bash
python harness.py --run 2 --node router --k 3
python harness.py --run 2 --node orchestrator --k 5
EVAL_RESULTS=results-run2 python analyze.py
```

**Results**, with 95% intervals computed exactly as in run 1 (percentile bootstrap, 10,000
resamples, over tasks for the orchestrator and messages for the router, paired across models):

| | Run 1 | Run 2 | Run 2, 95% CI |
|---|---:|---:|---:|
| 3B success rate | 20% (24/120) | **40.8%** (49/120) | 27–55% |
| 7B success rate | 62.5% (75/120) | **68.3%** (82/120) | 52–83% |
| Gap, 7B minus 3B | +42.5 points | +27.5 points | +13 to +42 points |
| pass^5, 3B / 7B | 4% / 50% | 12% / 54% | |
| Tool errors per conversation, 3B | 3.14 | 1.43 | |
| 3B calls rejected for copying the schema into the argument | 117 | 0 | |
| Tokens per successful task, 3B / 7B | 30,274 / 7,382 | 13,185 / 9,000 | |
| **Break-even price ratio, orchestrator** | 4.10× | **1.47×** | 1.01–2.16× |
| Break-even, re-sent prefix at 10% | 4.24× | 1.74× | 1.26–2.51× |
| **Break-even, whole pipeline (router + orchestrator)** | – | **1.47×** | 1.02–2.16× |
| Router accuracy at T=0, 3B / 7B (standalone) | 87% / 98% at T=0.7 | 90% / 98% | 81–98% / 94–100% |
| Break-even price ratio, router | 1.13× | 1.09× | 1.02–1.21× |
| Request overhead per call (latency minus Ollama's model time) | ~2 s (regression intercept) | 0.03 s (measured) | |

What run 2 shows:

- **The small model's gap narrowed a lot, and the ordering held.** The 3B doubled its success
  rate, and break-even at the orchestrator fell from 4.10× to 1.47×. The interval still excludes
  1 (barely: 1.01), and the orchestrator is still further from parity than the router (1.09×).
  The 7B's tokens per success rose (7,382 → 9,000), mostly because the documented tool schema
  makes every prompt longer (first call 764 → 1,077 input tokens).
- **Several things changed at once**, so run 2 does not say how much each contributed. The
  parameter docs are the most likely driver for the 3B (its schema-copying errors went from 117
  to 0), but the router's label in the context changed too. `num_predict` did not matter here:
  no call in run 2 came near 512 output tokens (longest 224).
- **The router costs little inside the pipeline**: 1.3 router calls per conversation, about 3%
  of the pipeline's tokens, and the pipeline break-even equals the orchestrator's (1.47×).
- **The ~2 s per-request overhead was the harness.** With `127.0.0.1` and Ollama's own timings,
  latency minus model time is 0.03 s per call, and per-call latency is 0.40 s (3B) and 0.44 s
  (7B). The 3B decodes at 138 tokens/s against 77 for the 7B. Run 1's per-call latency parity
  was therefore an artifact, as its write-up suspected; since run 2 also changed other things,
  the endpoint is the likely cause but not isolated by a controlled test. Prefill speeds (about
  26,000–38,000 tokens/s) are high because Ollama reuses the cached prefix of the conversation.
- **Graders frozen, 0 re-grades.** Every run-2 grade was produced by graders committed before
  the run.

Limitations of run 2: the same two models from one family and one small domain; several
setup changes in one run; the router label as a system note is one wiring choice; the graders
are still not checked against human labels. Next: separate the effects (docs without the router
note, and the reverse), add a current model pair with native tool calling, hand-label the
conversations.

## Next

Run 1's list. Items 1, 3, 4 and 5 were done in [Run 2](#run-2-2026-09-26); items 2 and 6 remain.

1. Describe all 13 tool parameters, with an example value each (for instance, that `customer_id` looks like `C01`).
2. Add a current model pair with native tool calling, and send text-mode tool results back as a user message.
3. Run the router at temperature 0, and wire it in front of the agent, so both nodes are measured in one pipeline.
4. Point the harness at `http://127.0.0.1:11434` and save Ollama's own `prompt_eval_duration` and `eval_duration` in every span, so model time and request overhead are reported separately.
5. Raise `num_predict` to 1024, and write the Ollama version, model digests and GPU into every trace.
6. Freeze the graders before the run, hand-label all 240 conversations, and publish grader–human agreement.
