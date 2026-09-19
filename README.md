# Decisions in AI Systems

Write-ups on how to choose, configure and evaluate LLMs in production systems. Each one takes a
single real decision and works through the reasoning, and where the argument is quantitative it
includes the code to reproduce it.

I build AI agents and the evaluation systems that decide how they're configured.

---

## 1. [Cheaper per token, more expensive per task](cheaper-per-token/article.md)

**Why switching an agent to a cheaper model doesn't reliably cut its bill, why the biggest model isn't the answer either, and how to evaluate every node to find out.**

In an agentic loop you pay per *completed task*, not per token, and the two can move in opposite
directions. A cheaper orchestrator takes more turns, every turn re-sends the whole conversation,
and a lower success rate compounds it: in the worked example, a model 4× cheaper per token comes
out **16% more expensive per successful task**. But the same arithmetic cuts both ways. With
prompt caching it flips to 27% cheaper, and on a leaf node the cheap model is 75% cheaper.

So the answer is an evaluation, and the article lays out which one: five levels (node, trajectory,
turn, multi-turn conversation, reliability over k runs), each measured on accuracy, latency and
cost per completed task, and a loop that decides with gates: quality first, then latency, then
cost. It closes with a small tool-calling agent built as a test subject, evaluated that way on two
local models.

<!--README_EXP-->

![Same two models, three different answers](cheaper-per-token/figures/three-answers.svg)

| | |
|---|---|
| 📄 Article | [`article.md`](cheaper-per-token/article.md) · [PDF](cheaper-per-token/article.pdf) |
| 🧪 Test agent + evaluation | [`experiment/`](cheaper-per-token/experiment/): 8-tool agent, 24 graded multi-turn tasks, a leaf-node router, traces and results |
| 🧮 Cost model | [`cost_model.py`](cheaper-per-token/cost_model.py): reproduces every illustrative number, including the caching case |
| 📊 Figures | [`figures.py`](cheaper-per-token/figures.py): every chart and diagram, from the same data |
| 💬 Short version | [`linkedin-post.md`](cheaper-per-token/linkedin-post.md) |

```bash
python cheaper-per-token/cost_model.py                 # the arithmetic, standard library only
cd cheaper-per-token/experiment && python analyze.py   # recompute results from the saved traces
```

Re-running the experiment itself needs [Ollama](https://ollama.com) and two free local models
(see [`experiment/README.md`](cheaper-per-token/experiment/README.md)). No API keys, no cost.

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
read and the least useful one to decide on.** The first shows it quantitatively for agents, with a
method and an experiment; the second shows it as a product decision, where accuracy gates before
cost is considered. In both, the thing that settles the question is an evaluation you ran on your
own system.

---

## About these write-ups

They describe how decisions were made, not the systems behind them: no proprietary architecture, no
client details, no internal specifics. Worked examples use illustrative parameters and say so. The
experiment uses a made-up store, open models and published traces. The code that produces every
number is included, so every figure can be checked.

**Contact:** [@MohanVishe](https://github.com/MohanVishe)
