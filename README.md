# Decisions in AI Systems

Write-ups on how to choose, configure and evaluate LLMs in production systems. Each one takes a
single real decision and works through the reasoning, and where the argument is quantitative it
includes the code to reproduce it.

I build AI agents and the evaluation systems that decide how they're configured.

---

## 1. [Cheaper per token, more expensive per task](cheaper-per-token/article.md)

**Why downgrading the model in an agentic system often raises your LLM bill.**

In an agentic loop you pay per *completed task*, not per token, and those two can move in opposite
directions. A cheaper model at the orchestrator takes more turns. Each extra turn re-sends the whole
conversation, so tokens grow faster than turns, and a lower success rate compounds it. In the worked
example, a model 4× cheaper per token comes out **16% more expensive per successful task**, while
the same model on a well-scoped leaf node is **75% cheaper**.

The conclusion: evaluate every node that calls a model on accuracy, latency and cost *per completed
task*, and let the measurements assign the models.

| | |
|---|---|
| 📄 Article | [`article.md`](cheaper-per-token/article.md) · [PDF](cheaper-per-token/article.pdf) |
| 🧮 Cost model | [`cost_model.py`](cheaper-per-token/cost_model.py): reproduces every number, and you can plug in your own agent's parameters |
| 💬 Short version | [`linkedin-post.md`](cheaper-per-token/linkedin-post.md) |

```bash
python cheaper-per-token/cost_model.py
```

No dependencies beyond the Python standard library.

---

## 2. [The cheaper model won on price. We didn't switch.](quality-before-cost/case-study.md)

**Setting the bar for a model change on an internal knowledge product, and why cost came last.**

A product decision on a meeting-notes system: accuracy *gates* before cost is considered, rather
than the two being weighed together. Weighing them sounds balanced, but it's how teams talk
themselves into a worse product: the cost figure is precise, the quality figure is noisy, and the
precise number wins the argument regardless of which one matters more.

| | |
|---|---|
| 📄 Case study | [`case-study.md`](quality-before-cost/case-study.md) · [PDF](quality-before-cost/case-study.pdf) |
| 💬 Short version | [`linkedin-post.md`](quality-before-cost/linkedin-post.md) |

---

## The thread between them

Both pieces make one argument from two directions. **The price per token is the easiest number to
read and the least useful one to decide on.** The first shows it quantitatively for agents, and the
second shows it as a product decision. In both, the thing that settles the question is an
evaluation you ran on your own system.

---

## About these write-ups

They describe how decisions were made, not the systems behind them: no proprietary architecture, no
client details, no internal specifics. Worked examples use illustrative parameters and say so, and
the code that produces them is included so every figure can be checked.

**Contact:** [@MohanVishe](https://github.com/MohanVishe)
