### Orchestrator

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Success rate (pass^1) | 40.8% (49/120) | 68.3% (82/120) |
|   95% CI, bootstrap over tasks | 27%–55% | 52%–83% |
| All 5 runs succeed (pass^5) | 12% (3/24 tasks) | 54% (13/24 tasks) |
| Model calls per conversation | 3.54 | 4.45 |
| Tool errors per conversation | 1.43 | 0.04 |
| Identified customer first | 89% | 97% |
| Tokens per conversation | 5,384 | 6,150 |
| **Tokens per successful task** | **13,185** | **9,000** |
| Tokens per successful task, re-sent prefix at 10% | 5,892 | 3,382 |
| Latency per call (includes the fixed overhead below) | 0.40 s | 0.44 s |
| Latency per conversation, p50 / p95 | 1.1 / 3.4 s | 1.7 / 4.0 s |
| **Time per successful task** | **3.4 s** | **2.9 s** |

By category:

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| lookup | 83% | 97% |
| multi-hop | 7% | 43% |
| write | 37% | 80% |
| multi-turn | 37% | 53% |

Latency fit, per model call (latency = fixed + output tokens / decode speed + input term):

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Fixed time per call | 0.04 s | 0.04 s |
| Decode speed | 137 tokens/s | 79 tokens/s |
| Calls in the fit | 425 | 534 |

Context growth: mean input tokens on the first and the 8th model call, over the conversations that reached that call:

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Call 1 | 1,077 (n=120) | 1,077 (n=120) |
| Call 8 | 2,032 (n=11) | 1,728 (n=10) |

### Router (leaf node)

48 labelled messages × 3 runs = 144 calls per model.

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Accuracy | 90% (129/144) | 98% (141/144) |
|   95% CI, bootstrap over messages | 81%–98% | 94%–100% |
| Tokens per correct call | 144 | 132 |
| Latency per call | 0.05 s | 0.07 s |
| Fastest call | 0.03 s for 2 output tokens | 0.04 s for 2 output tokens |

- **orchestrator**: the small model must be at least **1.47x** cheaper per token to cost the same per success (95% CI 1.01–2.16x); with each call's re-sent prefix billed at 10%, **1.74x** (95% CI 1.26–2.51x).
- **router**: the small model must be at least **1.09x** cheaper per token to cost the same per success (95% CI 1.02–1.21x).
- **Output weight**: orchestrator break-even at output tokens weighted 1x: 1.42x, 2x: 1.43x, 4x: 1.47x, 8x: 1.52x.
- **Success-rate gap** (large minus small): 95% CI +13 to +42 percentage points.
- **Re-graded** with the current graders: 0 grades changed (0 pass -> fail, 0 fail -> pass); see `regrade.md`.
Orchestrator time per call, from Ollama's own durations:

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Model time (prompt eval + eval) | 0.37 s | 0.41 s |
| Request overhead (latency minus model time), mean / p50 | 0.029 / 0.028 s | 0.033 / 0.030 s |
| Decode speed (output tokens / eval time) | 138 tokens/s | 77 tokens/s |
| Prefill speed (input tokens / prompt eval time) | 37,830 tokens/s | 26,091 tokens/s |

Pipeline (router at temperature 0 in front of the orchestrator, same model at both nodes):

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Router calls per conversation | 1.31 | 1.33 |
| Router tokens per conversation | 179 | 182 |
| Router share of pipeline tokens | 3.2% | 2.9% |
| Router latency per call | 0.08 s | 0.10 s |
| **Pipeline tokens per successful task** | **13,623** | **9,266** |
| **Pipeline time per successful task** | **3.7 s** | **3.1 s** |

Standalone router time per call, from Ollama's own durations:

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Model time | 0.037 s | 0.052 s |
| Request overhead, mean / p50 | 0.016 / 0.018 s | 0.017 / 0.019 s |

- **pipeline** (router + orchestrator): the small model must be at least **1.47x** cheaper per token to cost the same per success (95% CI 1.02–2.16x).
