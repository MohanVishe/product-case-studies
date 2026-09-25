### Orchestrator

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Success rate (pass^1) | 20.0% (24/120) | 62.5% (75/120) |
|   95% CI, bootstrap over tasks | 10%–32% | 45%–79% |
| All 5 runs succeed (pass^5) | 4% (1/24 tasks) | 50% (12/24 tasks) |
| Model calls per conversation | 4.26 | 4.33 |
| Tool errors per conversation | 3.14 | 0.04 |
| Identified customer first | 67% | 98% |
| Tokens per conversation | 6,055 | 4,614 |
| **Tokens per successful task** | **30,274** | **7,382** |
| Tokens per successful task, re-sent prefix at 10% | 12,633 | 2,980 |
| Latency per call (includes the fixed overhead below) | 2.63 s | 2.58 s |
| Latency per conversation, p50 / p95 | 7.4 / 25.0 s | 10.1 / 20.8 s |
| **Time per successful task** | **56.0 s** | **17.8 s** |

By category:

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| lookup | 57% | 87% |
| multi-hop | 0% | 47% |
| write | 17% | 73% |
| multi-turn | 7% | 43% |

Latency fit, per model call (latency = fixed + output tokens / decode speed + input term):

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Fixed time per call | 1.94 s | 2.18 s |
| Decode speed | 163 tokens/s | 76 tokens/s |
| Calls in the fit | 511 | 519 |

Context growth: mean input tokens on the first and the 8th model call, over the conversations that reached that call:

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Call 1 | 764 (n=120) | 764 (n=120) |
| Call 8 | 2,142 (n=21) | 1,424 (n=9) |

### Router (leaf node)

48 labelled messages × 3 runs = 144 calls per model.

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Accuracy | 87% (125/144) | 98% (141/144) |
|   95% CI, bootstrap over messages | 80%–93% | 94%–100% |
| Tokens per correct call | 149 | 132 |
| Latency per call | 2.25 s | 2.37 s |
| Fastest call | 2.06 s for 3 output tokens | 2.12 s for 2 output tokens |

- **orchestrator**: the small model must be at least **4.10x** cheaper per token to cost the same per success (95% CI 2.41–7.52x); with each call's re-sent prefix billed at 10%, **4.24x** (95% CI 2.63–7.61x).
- **router**: the small model must be at least **1.13x** cheaper per token to cost the same per success (95% CI 1.04–1.24x).
- **Output weight**: orchestrator break-even at output tokens weighted 1x: 3.96x, 2x: 4.01x, 4x: 4.10x, 8x: 4.26x.
- **Success-rate gap** (large minus small): 95% CI +27 to +59 percentage points.
- **Re-graded** with the current graders: 9 grades changed (6 pass -> fail, 3 fail -> pass); see `regrade.md`.
