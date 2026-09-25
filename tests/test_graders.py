"""The orchestrator graders: stock answers, reply checks on write tasks, W6, tickets.

The regression cases at the bottom are the saved conversations whose grade the 2026-09-25
grader revision changed, so a later edit that silently undoes a fix fails here.
"""
import json
from pathlib import Path

import pytest

from shop import ORDERS
from tasks import IN_STOCK, OUT_OF_STOCK, TASKS, grade

RESULTS = Path(__file__).resolve().parents[1] / "cheaper-per-token" / "experiment" / "results"
TASK = {t["id"]: t for t in TASKS}


def untouched():
    return {"orders": {k: {"status": v["status"], "address": v["address"]} for k, v in ORDERS.items()},
            "returns": [], "tickets": []}


def with_order(oid, **change):
    snap = untouched()
    snap["orders"][oid].update(change)
    return snap


@pytest.mark.parametrize("reply", [
    "The glass storage jars are currently out of stock.",
    "We currently do not have any glass storage jars available right now.",
    "I'm sorry, but we do not have the ceramic mug sets in stock at this time.",
    "Sorry, we don't have any ceramic mug sets in stock at the moment.",
    "The Ceramic Mug Set (4) is not currently available.",
    "There are 0 units left.",
])
def test_out_of_stock_phrasings(reply):
    assert OUT_OF_STOCK(reply.lower())


@pytest.mark.parametrize("reply", [
    "The copper kettle is in stock, and it costs $72.00.",
    "No, there is nothing out of stock in your latest order.",
])
def test_not_an_out_of_stock_claim(reply):
    assert not OUT_OF_STOCK(reply.lower())


@pytest.mark.parametrize("reply", [
    "Yes, the cast iron skillet is in stock.",
    "The Cast Iron Skillet (SKU: P102) is in stock with 7 units available.",
    "There are 5 units available.",
])
def test_in_stock_phrasings(reply):
    assert IN_STOCK(reply.lower())


@pytest.mark.parametrize("reply", [
    "The skillet is not in stock.",
    "It is unavailable right now.",
    "There are 0 units available.",
    "I can't provide real-time stock information.",
    "You can check our product page to see if the skillet is currently in stock.",
])
def test_not_an_in_stock_claim(reply):
    assert not IN_STOCK(reply.lower())


def test_write_task_needs_a_reply_that_confirms_the_change():
    snap = with_order("1052", status="cancelled")
    ok, _ = grade(TASK["W1"], snap, ["Order 1052 has been cancelled."])
    assert ok
    ok, reasons = grade(TASK["W1"], snap, ["Customer 1 does not exist. Please verify your email."])
    assert not ok and any("1052" in r for r in reasons)


def test_w6_needs_the_ownership_reason_and_no_false_status():
    snap = untouched()
    assert grade(TASK["W6"], snap, ["Order 1056 isn't associated with your account, so I can't cancel it."])[0]
    ok, reasons = grade(TASK["W6"], snap, ["I can't cancel order 1056. It has already been delivered."])
    assert not ok and any("delivered" in r for r in reasons)


def test_unrequested_ticket_fails_unless_the_policy_blocks_the_request():
    snap = with_order("1052", status="cancelled")
    snap["tickets"] = [{"ticket_id": "T001", "customer_id": "C02", "summary": "x"}]
    ok, reasons = grade(TASK["W1"], snap, ["Order 1052 has been cancelled."])
    assert not ok and "ticket opened when none was needed" in reasons
    # W5 (outside the return window) may escalate: the tool says to, when policy blocks a request
    snap = untouched()
    snap["tickets"] = [{"ticket_id": "T001", "customer_id": "C05", "summary": "x"}]
    assert grade(TASK["W5"], snap, ["Returns are accepted within 30 days of delivery."])[0]


def test_required_ticket_still_required():
    ok, reasons = grade(TASK["W3"], untouched(), ["Order 1053 has already shipped."])
    assert not ok and any("ticket" in r for r in reasons)


# (model, task, seed) -> grade under the current graders, for every conversation it changed
REGRADED = {
    ("qwen2.5-coder:3b", "L3", 4): True,
    ("qwen2.5-coder:3b", "T2", 4): True,
    ("qwen2.5-coder:7b", "T2", 1): True,
    ("qwen2.5-coder:3b", "W1", 0): False,
    ("qwen2.5-coder:3b", "W1", 3): False,
    ("qwen2.5-coder:3b", "W2", 3): False,
    ("qwen2.5-coder:3b", "T4", 2): False,
    ("qwen2.5-coder:7b", "W6", 0): False,
    ("qwen2.5-coder:7b", "W6", 1): False,
}


def test_saved_traces_regrade_as_published():
    rows = [json.loads(line) for line in (RESULTS / "orchestrator.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    changed = {}
    for r in rows:
        passed, _ = grade(TASK[r["task"]], r["snapshot"], r["replies"])
        passed = passed and r["status"] == "ok"
        if passed != r["passed"]:                         # r["passed"] is the grade stored at run time
            changed[(r["model"], r["task"], r["seed"])] = passed
    assert changed == REGRADED
