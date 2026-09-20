# LinkedIn version

*Long-form post, ~450 words. Link to the article, the cost model and the experiment at the end.*

---

We switched an AI agent to a cheaper model to cut costs.

It got more expensive.

Then I checked my own explanation, and found it was only half right. Here's the whole thing.

**Why the cheap model lost.** In an agent you don't pay per token, you pay per completed task. A weaker orchestrator picks the wrong tool, passes arguments that get rejected, and re-plans. Every one of those turns re-sends the entire conversation, so tokens grow faster than turns, and a lower success rate divides the bill by a smaller number.

Worked example: a model 4× cheaper per token, 16% MORE expensive per successful task.

**Then I added prompt caching to the model, and the answer flipped.** Re-sent context billed at a tenth of the normal price, and the same cheap model came out 27% cheaper. Same two models, opposite conclusion.

What didn't flip: it still failed 40% of tasks against 10%, and it still made seven round trips against three.

So "use the cheap model" isn't a rule. Neither is "use the big model". The rule is: measure, per node, per completed task.

**So I built a small agent and did it.** A support agent for a made-up shop: 8 tools, 4 policy rules, 24 graded conversations including multi-turn ones, each run 5 times, on a 3B and a 7B model, running locally on one GPU. 56 minutes, no API keys, zero cost.

At the orchestrator:

→ Model calls per conversation: 4.3 vs 4.3. Identical.
→ Average time per conversation: ~11s vs ~11s. Identical.
→ Success rate: 22% vs 63%.
→ Same conversation working 5 times out of 5: 4% vs 50%.
→ Tokens per SUCCESSFUL task: 27,946 vs 7,285.
→ Time per successful task: 51.7s vs 17.6s.

On every metric a cost dashboard shows, the downgrade looked free. On outcomes it wasn't close. The 3B would have to be 3.84× cheaper per token just to break even.

Then I ran the same two models on a leaf node in the same system, an intent classifier: one call, fixed output, no loop.

→ Break-even ratio: 1.13×. The price gap passes almost straight through.

Same two models. Same system. Opposite answers, two nodes apart.

**What that means in practice:** evaluate every node that calls a model, on three things measured per completed task, not per call:

✅ Accuracy (and how often it's right 5 times out of 5, not once)
✅ Latency (p95, not the median — the median hid the problem here)
✅ Cost per successful task, including the failures

Then decide with gates, in order: quality, latency, cost. A config that fails the quality gate is out, however cheap it is.

Full write-up, the cost model, the test agent and every trace: [link]

---

## Posting notes

- **Alternate openers:** *"Cheaper per token. More expensive per task."* / *"I was wrong about why the cheap model cost more. The correction is more interesting than the original claim."*
- The three-line opener is doing the work. Keep the blank lines so it survives the "see more" fold.
- The caching flip is the most credible part of the post: it shows you checked your own argument. Don't cut it for length.
- Link to the **repo**, not the PDF, so readers can run `cost_model.py` and the experiment themselves.
- If someone replies "just use routing": agree, and point at the leaf-node numbers. It's the same argument.
- If someone asks why Qwen 3B/7B: they were on the machine, same family and adjacent sizes is what the comparison needs, and the method is the point, not a leaderboard.
