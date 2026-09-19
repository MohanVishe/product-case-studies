"""The evaluation set for the orchestrator: 24 tasks with deterministic graders.

Each task is one conversation. `user` holds the customer's messages; multi-turn tasks feed the
next message after the agent has replied to the previous one. A task passes only if every check
holds:

  answer   every group must be matched by at least one of its alternatives, somewhere in the
           agent's replies (case-insensitive)
  orders   the listed orders must end in exactly this state, and *no other order may change*
  returns  the exact set of (order, sku) returns that must exist at the end
  tickets  customers that must have a ticket; "none" means no ticket may be opened

Grading on end state rather than on wording is what makes the checks deterministic: it doesn't
matter how the agent phrases things, only whether the store ends up where it should.
"""
from datetime import date

from shop import ORDERS


def when(iso):
    """Common ways a model might write a date."""
    d = date.fromisoformat(iso)
    m, mm = d.strftime("%B").lower(), d.strftime("%b").lower()
    n = str(d.day)
    return [iso, f"{m} {n}", f"{n} {m}", f"{mm} {n}", f"{n} {mm}", f"{mm}. {n}",
            d.strftime("%d/%m/%Y"), d.strftime("%m/%d/%Y"), f"{m} {n}th", f"{n}th {m}"]


OUT_OF_STOCK = ["out of stock", "not in stock", "not available", "unavailable", "sold out",
                "0 in stock", "0 units", "no stock", "zero", "currently not", "none in stock",
                "no units", "none available", "stock: 0", "stock of 0"]
IN_STOCK = ["in stock", "available", "units", "stock: 7", "stock of 7", "7 left", "7 in"]

TASKS = [
    # ---- lookup: one customer, one known order or product ------------------------------------
    dict(id="L1", cat="lookup", user=["Hi, this is priya.shah@example.com. When will order 1046 arrive?"],
         answer=[when("2026-09-20")]),
    dict(id="L2", cat="lookup", user=["Is the copper kettle in stock, and how much is it?"],
         answer=[["72"], IN_STOCK]),
    dict(id="L3", cat="lookup", user=["Do you have the glass storage jars available right now?"],
         answer=[OUT_OF_STOCK]),
    dict(id="L4", cat="lookup", user=["dan.okafor@example.com here. What's the status of my order 1052?"],
         answer=[["processing", "being processed", "not yet shipped", "not shipped", "being prepared"]]),
    dict(id="L5", cat="lookup", user=["What was in my order 1050? My email is lena.f@example.com."],
         answer=[["kettle"], ["runner"]]),
    dict(id="L6", cat="lookup", user=["How much did order 1049 come to in total? I'm maya.rao@example.com."],
         answer=[["91"]]),

    # ---- multi-hop: the agent has to find the customer and work out which order ---------------
    dict(id="M1", cat="multi-hop", user=["I'm aisha.khan@example.com. Where is my order and when will it get here?"],
         answer=[["shipped", "on its way", "in transit"], when("2026-09-21")]),
    dict(id="M2", cat="multi-hop", user=["Hi, arjun.m@example.com. Which of my orders haven't been delivered yet?"],
         answer=[["1056"]]),
    dict(id="M3", cat="multi-hop", user=["This is maya.rod@example.com. What's the total of my most recent order?"],
         answer=[["72"]]),
    dict(id="M4", cat="multi-hop", user=["maya.rao@example.com: please list all my orders and their status."],
         answer=[["1041"], ["1049"], ["1055"]]),
    dict(id="M5", cat="multi-hop", user=["Tom Becker here, tom.becker@example.com. Do I have an order that hasn't arrived yet, and what's in it?"],
         answer=[["1047"], ["throw", "blanket"]]),
    dict(id="M6", cat="multi-hop", user=["Hi, it's priya.shah@example.com. Is anything in my latest order out of stock?"],
         answer=[["jar"], OUT_OF_STOCK]),

    # ---- write + policy: the right change, or the right refusal ------------------------------
    dict(id="W1", cat="write", user=["Please cancel order 1052, I ordered it by mistake. dan.okafor@example.com"],
         orders={"1052": {"status": "cancelled"}}),
    dict(id="W2", cat="write", user=["Change the delivery address for order 1058 to 7 Palm Grove, Goa. My email is priya.shah@example.com."],
         orders={"1058": {"address": "7 palm grove"}}),
    dict(id="W3", cat="write", user=["Cancel order 1053 please. aisha.khan@example.com"],
         tickets=["C06"], answer=[["shipped"]]),
    dict(id="W4", cat="write", user=["I'd like to return the copper kettle from order 1043, it arrived dented. dan.okafor@example.com"],
         returns=[("1043", "P106")]),
    dict(id="W5", cat="write", user=["I want to return the cutting board from order 1040. tom.becker@example.com"],
         answer=[["30"]]),
    dict(id="W6", cat="write", user=["Cancel order 1056. My email is lena.f@example.com."],
         answer=[["belong", "associated", "linked", "your account", "another customer", "not yours",
                  "different customer", "not registered", "not under", "not match", "unable", "can't", "cannot"]]),

    # ---- multi-turn: the customer's follow-ups depend on what came before ---------------------
    dict(id="T1", cat="multi-turn",
         user=["Hi, I'm maya.rao@example.com. What's the status of my latest order?",
               "Can you change its delivery address to 22 River View, Pune?",
               "Thanks. And when will order 1049 arrive?"],
         orders={"1055": {"address": "22 river view"}}, answer=[when("2026-09-22")]),
    dict(id="T2", cat="multi-turn",
         user=["Hello, arjun.m@example.com here. Do you have the ceramic mug sets in stock?",
               "Hmm. In that case please cancel my order 1056."],
         orders={"1056": {"status": "cancelled"}}, answer=[OUT_OF_STOCK]),
    dict(id="T3", cat="multi-turn",
         user=["priya.shah@example.com. I need to cancel an order.",
               "The one with the mug set."],
         tickets=["C03"], answer=[["shipped"]]),
    dict(id="T4", cat="multi-turn",
         user=["Hi, dan.okafor@example.com. What have I ordered recently?",
               "Please cancel the cutting boards order.",
               "Also, is the cast iron skillet in stock?"],
         orders={"1052": {"status": "cancelled"}}, answer=[IN_STOCK]),
    dict(id="T5", cat="multi-turn",
         user=["I want to return something. I'm lena.f@example.com.",
               "The table runner from my last delivered order. It's the wrong colour."],
         returns=[("1050", "P100")]),
    dict(id="T6", cat="multi-turn",
         user=["tom.becker@example.com: please change the address on my open order to 18 Torstrasse, Munich.",
               "Actually, cancel that order instead."],
         orders={"1047": {"status": "cancelled", "address": None}}),
]


def grade(task, snapshot, replies):
    """Return (passed, reasons). `snapshot` is Shop.snapshot() at the end of the episode."""
    reasons = []
    text = " ".join(r or "" for r in replies).lower().replace("*", "")

    for group in task.get("answer", []):
        if not any(alt in text for alt in group):
            reasons.append(f"answer missing one of {group[:3]}")

    want = task.get("orders", {})
    for oid, end in snapshot["orders"].items():
        start = ORDERS[oid]
        exp = want.get(oid, {})
        if exp.get("status", start["status"]) != end["status"]:
            reasons.append(f"order {oid} status {end['status']}")
        if "address" in exp:
            if exp["address"] is None:
                pass
            elif exp["address"] not in end["address"].lower():
                reasons.append(f"order {oid} address not updated")
        elif end["address"] != start["address"]:
            reasons.append(f"order {oid} address changed unexpectedly")

    got_returns = sorted((r["order_id"], r["sku"]) for r in snapshot["returns"])
    if got_returns != sorted(task.get("returns", [])):
        reasons.append(f"returns {got_returns}")

    tickets = {t["customer_id"] for t in snapshot["tickets"]}
    want_t = task.get("tickets")
    if want_t == "none" and tickets:
        reasons.append("ticket opened when none was needed")
    elif isinstance(want_t, list) and not set(want_t) <= tickets:
        reasons.append(f"no ticket for {want_t}")

    return not reasons, reasons
