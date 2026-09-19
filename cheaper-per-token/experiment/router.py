"""A leaf node: classify a customer message into one of six intents, in a single call.

This is the kind of node the article says a small model can usually take: one call, a narrow
job, a fixed output. It gets its own labelled evaluation set, separate from the agent's.
"""
from agent import chat

LABELS = ["order_status", "cancel_order", "change_address", "return_item", "product_info", "other"]

PROMPT = """Classify the customer's message into exactly one intent:

order_status    where an order is, when it arrives, what's in it, what it cost
cancel_order    wants to cancel an order
change_address  wants to change where an order is delivered
return_item     wants to return or send back something they received
product_info    asks about a product: price, stock, availability, details
other           anything else

Reply with the intent label only."""

EXAMPLES = [
    ("Where is my order 1046?", "order_status"),
    ("Has my parcel shipped yet?", "order_status"),
    ("When should I expect the kettle I ordered last week?", "order_status"),
    ("What did I pay for order 1050?", "order_status"),
    ("Can you tell me what was in my last order?", "order_status"),
    ("My tracking hasn't updated in days, is it still coming?", "order_status"),
    ("Is order 1055 delivered or not?", "order_status"),
    ("I placed an order on Monday, what's happening with it?", "order_status"),

    ("Please cancel order 1052.", "cancel_order"),
    ("I don't want the napkins anymore, stop the order.", "cancel_order"),
    ("I ordered the wrong thing by mistake, can you cancel it before it ships?", "cancel_order"),
    ("Cancel everything I bought today.", "cancel_order"),
    ("Is it too late to call off my order?", "cancel_order"),
    ("Scrap order 1047 please.", "cancel_order"),
    ("I changed my mind about the skillet, please don't send it.", "cancel_order"),
    ("How do I cancel? I found it cheaper elsewhere.", "cancel_order"),

    ("I've moved, please send order 1058 to 7 Palm Grove, Goa.", "change_address"),
    ("Can you update the delivery address on my order?", "change_address"),
    ("Wrong postcode on my order, it should be 400050.", "change_address"),
    ("Deliver it to my office instead of home please.", "change_address"),
    ("Ship my open order to my mum's place at 3 Rose Lane.", "change_address"),
    ("I typed my street name wrong when I ordered.", "change_address"),
    ("Can the parcel go to a different city? I'm travelling.", "change_address"),
    ("Please redirect order 1055 to 22 River View.", "change_address"),

    ("I want to return the table runner, wrong colour.", "return_item"),
    ("The kettle arrived dented. How do I send it back?", "return_item"),
    ("Can I get a refund for the mugs I received?", "return_item"),
    ("The blanket is smaller than I expected, I'd like to return it.", "return_item"),
    ("One of the jars came broken.", "return_item"),
    ("How long do I have to return something?", "return_item"),
    ("I received two cutting boards but only wanted one, sending one back.", "return_item"),
    ("This isn't what I ordered, I want my money back.", "return_item"),

    ("Is the copper kettle in stock?", "product_info"),
    ("How much is the wool throw?", "product_info"),
    ("Do you sell cast iron pans?", "product_info"),
    ("When will the ceramic mugs be back in stock?", "product_info"),
    ("Are the napkins cotton or polyester?", "product_info"),
    ("What sizes does the cutting board come in?", "product_info"),
    ("Do you have glass jars with lids?", "product_info"),
    ("Is the linen runner machine washable?", "product_info"),

    ("Do you have a physical shop I can visit?", "other"),
    ("I'd like to speak to a manager.", "other"),
    ("Can I change the email on my account?", "other"),
    ("Do you offer gift wrapping?", "other"),
    ("Thanks, that's all for today!", "other"),
    ("Are you hiring?", "other"),
    ("How do I unsubscribe from your newsletter?", "other"),
    ("Can I pay with a bank transfer?", "other"),
]


def parse(text):
    """Accept the label if exactly one label appears in the reply."""
    t = (text or "").lower()
    found = [lab for lab in LABELS if lab in t]
    return found[0] if len(found) == 1 else None


def run_router(model, message, seed, temperature=0.7):
    msgs = [{"role": "system", "content": PROMPT}, {"role": "user", "content": message}]
    msg, span = chat(model, msgs, None, temperature, seed, num_predict=24)
    span.update(node="router", predicted=parse(msg.get("content")), raw=(msg.get("content") or "")[:80])
    return span
