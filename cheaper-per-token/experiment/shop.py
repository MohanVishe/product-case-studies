"""A small, deterministic online-store backend: the environment the agent works in.

Everything is in memory and resets per episode, so every run starts from the same state and
the grader can compare the final state against what the task expected.
"""
import copy
import re
from datetime import date, timedelta

TODAY = date(2026, 9, 19)
RETURN_WINDOW_DAYS = 30

CUSTOMERS = {
    "C01": {"name": "Maya Rao", "email": "maya.rao@example.com"},
    "C02": {"name": "Daniel Okafor", "email": "dan.okafor@example.com"},
    "C03": {"name": "Priya Shah", "email": "priya.shah@example.com"},
    "C04": {"name": "Lena Fischer", "email": "lena.f@example.com"},
    "C05": {"name": "Tom Becker", "email": "tom.becker@example.com"},
    "C06": {"name": "Aisha Khan", "email": "aisha.khan@example.com"},
    "C07": {"name": "Arjun Mehta", "email": "arjun.m@example.com"},
    "C08": {"name": "Maya Rodrigues", "email": "maya.rod@example.com"},
}

PRODUCTS = {
    "P100": {"name": "Linen Table Runner", "price": 24.00, "stock": 12},
    "P101": {"name": "Ceramic Mug Set (4)", "price": 32.00, "stock": 0},
    "P102": {"name": "Cast Iron Skillet", "price": 45.00, "stock": 7},
    "P103": {"name": "Bamboo Cutting Board", "price": 18.50, "stock": 25},
    "P104": {"name": "Wool Throw Blanket", "price": 59.00, "stock": 3},
    "P105": {"name": "Glass Storage Jars (6)", "price": 27.00, "stock": 0},
    "P106": {"name": "Copper Kettle", "price": 72.00, "stock": 5},
    "P107": {"name": "Cotton Napkins (8)", "price": 16.00, "stock": 40},
}

# status: processing -> shipped -> delivered, or cancelled
ORDERS = {
    "1040": {"customer_id": "C05", "items": {"P103": 1}, "status": "delivered", "created": "2026-07-24", "date": "2026-07-30", "address": "5 Elm Court, Berlin"},
    "1041": {"customer_id": "C01", "items": {"P102": 1}, "status": "delivered", "created": "2026-08-28", "date": "2026-09-02", "address": "14 Hill Street, Pune"},
    "1043": {"customer_id": "C02", "items": {"P106": 1}, "status": "delivered", "created": "2026-08-30", "date": "2026-09-04", "address": "3 Marina Road, Lagos"},
    "1044": {"customer_id": "C04", "items": {"P107": 3}, "status": "cancelled", "created": "2026-09-01", "date": None, "address": "9 Linden Weg, Hamburg"},
    "1046": {"customer_id": "C03", "items": {"P101": 1}, "status": "shipped", "created": "2026-09-08", "date": "2026-09-20", "address": "21 Park Lane, Mumbai"},
    "1047": {"customer_id": "C05", "items": {"P104": 2}, "status": "processing", "created": "2026-09-11", "date": "2026-09-23", "address": "5 Elm Court, Berlin"},
    "1048": {"customer_id": "C08", "items": {"P107": 1}, "status": "delivered", "created": "2026-09-09", "date": "2026-09-13", "address": "40 Rua Nova, Lisbon"},
    "1049": {"customer_id": "C01", "items": {"P104": 1, "P107": 2}, "status": "shipped", "created": "2026-09-12", "date": "2026-09-22", "address": "14 Hill Street, Pune"},
    "1050": {"customer_id": "C04", "items": {"P106": 1, "P100": 1}, "status": "delivered", "created": "2026-09-10", "date": "2026-09-15", "address": "9 Linden Weg, Hamburg"},
    "1052": {"customer_id": "C02", "items": {"P103": 2}, "status": "processing", "created": "2026-09-15", "date": "2026-09-24", "address": "3 Marina Road, Lagos"},
    "1053": {"customer_id": "C06", "items": {"P102": 1, "P103": 1}, "status": "shipped", "created": "2026-09-14", "date": "2026-09-21", "address": "8 Canal Street, Leeds"},
    "1055": {"customer_id": "C01", "items": {"P100": 2}, "status": "processing", "created": "2026-09-17", "date": "2026-09-26", "address": "14 Hill Street, Pune"},
    "1056": {"customer_id": "C07", "items": {"P101": 2}, "status": "processing", "created": "2026-09-17", "date": "2026-09-29", "address": "2 Ring Road, Delhi"},
    "1057": {"customer_id": "C07", "items": {"P100": 1}, "status": "delivered", "created": "2026-09-02", "date": "2026-09-08", "address": "2 Ring Road, Delhi"},
    "1058": {"customer_id": "C03", "items": {"P105": 1, "P103": 1}, "status": "processing", "created": "2026-09-18", "date": "2026-09-27", "address": "21 Park Lane, Mumbai"},
    "1059": {"customer_id": "C08", "items": {"P106": 1}, "status": "processing", "created": "2026-09-18", "date": "2026-09-28", "address": "40 Rua Nova, Lisbon"},
}


def _obj(props, required):
    return {"type": "object", "properties": props, "required": required}


def _fn(name, description, props, required):
    return {"type": "function", "function": {"name": name, "description": description,
                                             "parameters": _obj(props, required)}}


S = {"type": "string"}
TOOLS = [
    _fn("find_customer", "Find a customer by email address or name. Returns matching customer ids.",
        {"query": {**S, "description": "Email address or name"}}, ["query"]),
    _fn("list_orders", "List a customer's orders, newest first, with their status.",
        {"customer_id": S}, ["customer_id"]),
    _fn("get_order", "Get full details of one order: owner, items, total, status, dates and delivery address.",
        {"order_id": S}, ["order_id"]),
    _fn("search_products", "Search the catalogue by product name. Returns sku, price and units in stock.",
        {"query": S}, ["query"]),
    _fn("cancel_order", "Cancel an order. Only possible while the order is still processing.",
        {"order_id": S, "reason": S}, ["order_id", "reason"]),
    _fn("update_address", "Change the delivery address of an order. Only possible while it is still processing.",
        {"order_id": S, "address": S}, ["order_id", "address"]),
    _fn("request_return", "Open a return for one item of a delivered order.",
        {"order_id": S, "sku": S, "reason": S}, ["order_id", "sku", "reason"]),
    _fn("create_ticket", "Escalate to a human support agent when a request can't be completed under policy.",
        {"customer_id": S, "summary": S}, ["customer_id", "summary"]),
]
TOOL_NAMES = {t["function"]["name"] for t in TOOLS}

# Run 2: the same 8 tools with all 13 parameters described, each with an example value. Run 1
# described only find_customer.query, and the 3B's most common error was copying the parameter
# schema into the argument. The example values are deliberately not in the store (no
# customer C09, order 1234 or sku P999), so they show the format without hinting at any task's
# answer. Names, types and required fields are unchanged, so Shop.call
# validates both lists identically.
def _p(description, example):
    return {**S, "description": f"{description} Example: {example!r}."}


TOOLS_DOCUMENTED = [
    _fn("find_customer", "Find a customer by email address or name. Returns matching customer ids.",
        {"query": _p("The customer's full email address, or part of their name.", "sam.lee@example.com")},
        ["query"]),
    _fn("list_orders", "List a customer's orders, newest first, with their status.",
        {"customer_id": _p("A customer id as returned by find_customer: the letter C and two digits. "
                           "Not an email address.", "C09")}, ["customer_id"]),
    _fn("get_order", "Get full details of one order: owner, items, total, status, dates and delivery address.",
        {"order_id": _p("The order number, digits only.", "1234")}, ["order_id"]),
    _fn("search_products", "Search the catalogue by product name. Returns sku, price and units in stock.",
        {"query": _p("One or more words from the product name.", "teapot")}, ["query"]),
    _fn("cancel_order", "Cancel an order. Only possible while the order is still processing.",
        {"order_id": _p("The order number to cancel, digits only.", "1234"),
         "reason": _p("A short reason in the customer's words.", "no longer needed")},
        ["order_id", "reason"]),
    _fn("update_address", "Change the delivery address of an order. Only possible while it is still processing.",
        {"order_id": _p("The order number, digits only.", "1234"),
         "address": _p("The complete new delivery address as one string.", "12 Example Road, Springfield")},
        ["order_id", "address"]),
    _fn("request_return", "Open a return for one item of a delivered order.",
        {"order_id": _p("The delivered order's number, digits only.", "1234"),
         "sku": _p("The item's sku as shown by get_order: the letter P and three digits.", "P999"),
         "reason": _p("A short reason in the customer's words.", "arrived damaged")},
        ["order_id", "sku", "reason"]),
    _fn("create_ticket", "Escalate to a human support agent when a request can't be completed under policy.",
        {"customer_id": _p("The customer id from find_customer: the letter C and two digits.", "C09"),
         "summary": _p("One sentence on what the customer wants and why it could not be done.",
                       "wants order 1234 cancelled but it has already shipped")},
        ["customer_id", "summary"]),
]
assert [t["function"]["parameters"]["properties"].keys() for t in TOOLS_DOCUMENTED] ==        [t["function"]["parameters"]["properties"].keys() for t in TOOLS]


class ToolError(Exception):
    pass


def _order_id(v):
    m = re.search(r"\d+", str(v))
    if not m:
        raise ToolError(f"invalid order_id {v!r}")
    return m.group(0)


class Shop:
    def __init__(self):
        self.customers = copy.deepcopy(CUSTOMERS)
        self.products = copy.deepcopy(PRODUCTS)
        self.orders = copy.deepcopy(ORDERS)
        self.returns, self.tickets = [], []

    # ---- dispatch -------------------------------------------------------------------------
    def call(self, name, args):
        """Run one tool. Returns (result, ok). Errors go back to the model as a result."""
        if name not in TOOL_NAMES:
            return {"error": f"unknown tool '{name}'"}, False
        if not isinstance(args, dict):
            return {"error": "arguments must be an object"}, False
        spec = next(t for t in TOOLS if t["function"]["name"] == name)["function"]["parameters"]
        missing = [k for k in spec["required"] if args.get(k) in (None, "")]
        if missing:
            return {"error": f"missing argument(s): {', '.join(missing)}"}, False
        kwargs = {}
        for k in spec["properties"]:
            if k in args:
                v = args[k]
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    v = str(v)
                if not isinstance(v, str):
                    return {"error": f"argument '{k}' must be a string"}, False
                kwargs[k] = v
        try:
            return getattr(self, name)(**kwargs), True
        except ToolError as e:
            return {"error": str(e)}, False

    # ---- read tools -----------------------------------------------------------------------
    def find_customer(self, query):
        q = str(query).strip().lower()
        hits = [{"customer_id": cid, **c} for cid, c in self.customers.items()
                if q == c["email"] or (q and q in c["name"].lower())]
        return {"matches": hits}

    def list_orders(self, customer_id):
        if customer_id not in self.customers:
            raise ToolError(f"no customer {customer_id}")
        rows = [{"order_id": oid, "status": o["status"], "created": o["created"]}
                for oid, o in self.orders.items() if o["customer_id"] == customer_id]
        return {"orders": sorted(rows, key=lambda r: r["created"], reverse=True)}

    def get_order(self, order_id):
        oid = _order_id(order_id)
        if oid not in self.orders:
            raise ToolError(f"no order {oid}")
        o = self.orders[oid]
        items = [{"sku": s, "name": self.products[s]["name"], "qty": q,
                  "unit_price": self.products[s]["price"]} for s, q in o["items"].items()]
        out = {"order_id": oid, "customer_id": o["customer_id"], "status": o["status"],
               "created": o["created"], "items": items,
               "total": round(sum(i["qty"] * i["unit_price"] for i in items), 2),
               "delivery_address": o["address"]}
        if o["status"] == "delivered":
            out["delivered_on"] = o["date"]
        elif o["status"] in ("processing", "shipped"):
            out["estimated_delivery"] = o["date"]
        return out

    def search_products(self, query):
        words = [w.rstrip("s") for w in re.findall(r"[a-z]+", str(query).lower()) if len(w) > 2]
        hits = []
        for sku, p in self.products.items():
            name = p["name"].lower()
            score = sum(w in name for w in words)
            if score:
                hits.append((score, {"sku": sku, **p}))
        hits.sort(key=lambda h: -h[0])
        return {"products": [h[1] for h in hits]}

    # ---- write tools ----------------------------------------------------------------------
    def _open_order(self, order_id, action):
        oid = _order_id(order_id)
        if oid not in self.orders:
            raise ToolError(f"no order {oid}")
        st = self.orders[oid]["status"]
        if st != "processing":
            raise ToolError(f"cannot {action}: order {oid} is already {st}")
        return oid

    def cancel_order(self, order_id, reason):
        oid = self._open_order(order_id, "cancel")
        self.orders[oid]["status"] = "cancelled"
        return {"order_id": oid, "status": "cancelled"}

    def update_address(self, order_id, address):
        oid = self._open_order(order_id, "change address")
        self.orders[oid]["address"] = str(address)
        return {"order_id": oid, "delivery_address": str(address)}

    def request_return(self, order_id, sku, reason):
        oid = _order_id(order_id)
        if oid not in self.orders:
            raise ToolError(f"no order {oid}")
        o = self.orders[oid]
        if o["status"] != "delivered":
            raise ToolError(f"order {oid} is {o['status']}, only delivered orders can be returned")
        if sku not in o["items"]:
            raise ToolError(f"sku {sku} is not in order {oid}")
        if TODAY - date.fromisoformat(o["date"]) > timedelta(days=RETURN_WINDOW_DAYS):
            raise ToolError(f"order {oid} was delivered on {o['date']}, outside the "
                            f"{RETURN_WINDOW_DAYS}-day return window")
        rid = f"R{len(self.returns) + 1:03d}"
        self.returns.append({"return_id": rid, "order_id": oid, "sku": sku})
        return {"return_id": rid, "status": "return opened"}

    def create_ticket(self, customer_id, summary):
        if customer_id not in self.customers:
            raise ToolError(f"no customer {customer_id}")
        tid = f"T{len(self.tickets) + 1:03d}"
        self.tickets.append({"ticket_id": tid, "customer_id": customer_id, "summary": str(summary)})
        return {"ticket_id": tid, "status": "escalated to a human agent"}

    def snapshot(self):
        return {"orders": {k: {"status": v["status"], "address": v["address"]}
                           for k, v in self.orders.items()},
                "returns": list(self.returns), "tickets": list(self.tickets)}


SYSTEM_PROMPT = f"""You are the customer-support agent for an online homeware store. Today is {TODAY.isoformat()}.

Use the tools to look things up and to make changes. Never guess order details, prices or stock.

Policy:
1. Identify the customer with find_customer before looking at or changing their orders, and only act on orders that belong to that customer. If an order belongs to someone else, refuse and say so.
2. Orders can be cancelled or have their address changed only while their status is "processing". If an order has already shipped, do not attempt it: open a ticket with create_ticket and tell the customer.
3. Returns are accepted only for delivered orders, within {RETURN_WINDOW_DAYS} days of delivery. Outside that window, explain the policy instead.
4. Act on clear requests straight away, without asking the customer to confirm. Ask a question only when you genuinely lack information you need.

When you are done, reply to the customer in a few sentences with the relevant details: order numbers, status, dates, prices."""
