# LinkedIn version

*Long-form post, ~430 words. Link to the full article and the cost model at the end.*

---

We switched an AI agent to a cheaper model to cut costs.

It got more expensive.

Here's why, because I think most teams will hit this the first time they try to cut an agent's LLM bill.

**The orchestrator is the obvious target, and the worst one.**

In an agent, the orchestrator reads the request, picks a tool, reads the result and decides what to do next. It runs every turn, so it's the biggest line on the bill. Downgrade it and the dashboard shows an immediate saving.

What the dashboard doesn't show is what happens to the loop.

**Three things multiply between price per token and price per task.**

1️⃣ **Turn inflation.** A weaker model picks a plausible but wrong tool, passes a bad argument, reads the error, re-plans. Every misstep is another turn.

2️⃣ **Context growth.** Every turn re-sends the whole conversation, so turn 7 costs far more than turn 1. In our worked example, 2.3× the turns meant 3.1× the tokens.

3️⃣ **Failure.** Cost per successful task is cost per attempt divided by success rate. A weaker orchestrator fails more, so the division hurts more.

**The numbers:**

A model 4× cheaper per token, at the orchestrator:
→ Per attempt: about 23% cheaper. The dashboard says you won.
→ Per *successful task*: **16% more expensive.**

The same cheap model on a narrow leaf node (one call, a fixed output format):
→ **75% cheaper.**

Same model, opposite answers. It depends entirely on where it sits.

**So the rule isn't "use big models."** It's this:

Put capable models where decisions get made: the orchestrator, the planner, the router. Their errors compound through every turn that follows.

Put cheap models where the work is well specified: extraction, classification, formatting. There the price gap passes straight through.

And evaluate **every node** that calls a model on three things, measured per completed task rather than per call:
✅ Accuracy
✅ Latency (seven fast round trips can lose to three slow ones)
✅ Cost

A cheaper model is only cheaper when its price advantage beats the token inflation times the success-rate gap. The pricing page gives you one of those three numbers. Only an evaluation gives you the other two.

Full write-up, plus a small Python model you can run with your own agent's numbers: [link]

---

## Posting notes

- **Alternate openers:** *"Cheaper per token. More expensive per task."* / *"Your cost dashboard will tell you the cheap model is saving money. It might be lying."*
- The two-line opener is doing the work. Keep it as two lines so it survives the "see more" fold.
- Emoji markers are optional. Drop them if they don't suit your feed.
- Link to the **repo folder**, not the PDF, so readers can find `cost_model.py`. The runnable model is the thing engineers will share.
- If someone replies "just use routing": agree, and point them to the leaf-node case. It's the same argument.
