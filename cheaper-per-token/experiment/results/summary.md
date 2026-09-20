### Orchestrator

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Success rate (pass^1) | 22% | 63% |
| All 5 runs succeed (pass^5) | 4% | 50% |
| Model calls per conversation | 4.3 | 4.3 |
| Tool errors per conversation | 3.14 | 0.04 |
| Identified customer first | 67% | 98% |
| Tokens per conversation | 6,055 | 4,614 |
| **Tokens per successful task** | **27,946** | **7,285** |
| Latency per call | 2.63 s | 2.58 s |
| Latency per conversation, p50 / p95 | 7.4 / 25.0 s | 10.1 / 20.8 s |
| **Time per successful task** | **51.7 s** | **17.6 s** |

By category:

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| lookup | 53% | 87% |
| multi-hop | 0% | 47% |
| write | 27% | 80% |
| multi-turn | 7% | 40% |

### Router (leaf node)

| | qwen2.5-coder:3b | qwen2.5-coder:7b |
|---|---:|---:|
| Accuracy | 87% | 98% |
| Tokens per correct call | 149 | 132 |
| Latency per call | 2.25 s | 2.37 s |

- **orchestrator**: the small model must be at least **3.84x** cheaper per token to cost the same per success.
- **router**: the small model must be at least **1.13x** cheaper per token to cost the same per success.
