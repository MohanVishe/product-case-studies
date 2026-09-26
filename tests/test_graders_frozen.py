"""The graders were frozen before run 2 started, and this test holds them there.

Run 1's graders were revised after its traces had been seen (see results/regrade.md). Run 2's
were fixed first: tasks.py (the orchestrator graders) and router.py (the router's label parser)
are pinned by content hash, committed before the first run-2 trace was recorded. Changing either
file fails this test; a deliberate change has to update the hash in a commit of its own, and
results-run2/regrade.md then lists every grade it moved.
"""
import hashlib
from pathlib import Path

import pytest

EXPERIMENT = Path(__file__).resolve().parents[1] / "cheaper-per-token" / "experiment"
FROZEN = {
    "tasks.py": "7761d0f7074cc5e0aeb423e5f8f644c0c1f30aac32ac48b5971fdfdba731aaa9",
    "router.py": "850757c4f4ee8b26dfbdab7bb15dbd052e77cfea03c1329dde981bea1a490d16",
}


@pytest.mark.parametrize("name", sorted(FROZEN))
def test_grader_is_frozen(name):
    text = (EXPERIMENT / name).read_bytes().replace(b"\r\n", b"\n")   # same hash on any checkout
    assert hashlib.sha256(text).hexdigest() == FROZEN[name], f"{name} changed after the run-2 freeze"
