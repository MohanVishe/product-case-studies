# Re-grading the saved traces

Run 2 was graded by graders frozen before it started ([`tasks.py`](../tasks.py) and [`router.py`](../router.py), sha256 pinned in `tests/test_graders_frozen.py`). `analyze.py` grades every saved conversation again with the current graders; this file lists every conversation whose grade changed, so it stays empty unless the graders change after the run.

0 grades changed: 0 pass → fail, 0 fail → pass.

| Model | Task | Seed | Was | Now | Why, under the current graders | Replies (first 160 characters of each) |
|---|---|---:|---|---|---|---|

Known limit: the graders check the facts each task asks for, not every statement in a reply. A reply can pass with a correct answer and a wrong incidental detail (for example, the right arrival date for an order it calls "being processed" when it has shipped). A hand-labelled pass over all 240 conversations, with grader agreement, is listed under Next in the experiment README.
