# Re-grading the saved traces

The graders in [`tasks.py`](../tasks.py) were revised on 2026-09-25, after the run, to fix errors found in both directions (see its docstring). `analyze.py` grades every saved conversation again with the current graders; this file lists every conversation whose grade changed. Nothing was re-run: the traces are the ones recorded on 2026-09-20.

9 grades changed: 6 pass → fail, 3 fail → pass.

| Model | Task | Seed | Was | Now | Why, under the current graders | Replies (first 160 characters of each) |
|---|---|---:|---|---|---|---|
| qwen2.5-coder:3b | L3 | 4 | fail | pass | all checks pass | We're sorry, but we currently do not have any glass storage jars available right now. |
| qwen2.5-coder:3b | T2 | 4 | fail | pass | all checks pass | Hello arjun.m@example.com,  I'm sorry, but we do not have the ceramic mug sets in stock at this time. We can place an order for them, but it will take some time / Hello arjun.m@example.com,  Thank you for letting us know. We have cancelled your order 1056.  If you have any other questions or concerns, please do not hesita |
| qwen2.5-coder:3b | T4 | 2 | pass | fail | answer missing IN_STOCK; ticket opened when none was needed | Hello Daniel Okafor,  It looks like you have placed the following orders recently:  1. **Order ID**: 1052    - **Status**: Processing    - **Created**: 2026-09- / Hello Daniel Okafor,  Thank you for your order cancellation request for Order ID 1052. Your request has been processed and will be escalated to a human support  / Hello Daniel Okafor,  Thank you for your message. I'm sorry, but I can't provide real-time stock information. However, you can check our product page or use our |
| qwen2.5-coder:3b | W1 | 0 | pass | fail | answer missing one of ['1052']; answer missing one of ['cancel'] | Customer 1 does not exist. Please verify the email address or name you used to place your order. |
| qwen2.5-coder:3b | W1 | 3 | pass | fail | answer missing one of ['1052']; answer missing one of ['cancel'] | It seems there was an error in the previous response. I'll recheck the order status for customer 43. Please provide me with the order number again. |
| qwen2.5-coder:3b | W2 | 3 | pass | fail | answer missing one of ['1058']; answer missing one of ['palm grove'] | Please provide your email address or name to find your customer. |
| qwen2.5-coder:7b | T2 | 1 | fail | pass | all checks pass | I'm sorry, but we don't have any ceramic mug sets in stock at the moment. How about something else? / Order 1056 has been cancelled. If you need anything else, feel free to ask. |
| qwen2.5-coder:7b | W6 | 0 | pass | fail | answer missing one of ['belong', 'associated', 'linked']; reply says 'delivered', which is false | I'm sorry, but I can't cancel order 1056. It has already been delivered, and we can only accept returns within 30 days of delivery. I've escalated your request  |
| qwen2.5-coder:7b | W6 | 1 | pass | fail | answer missing one of ['belong', 'associated', 'linked']; reply says 'delivered', which is false | I'm sorry, but order 1056 is already delivered and cannot be cancelled. I've created a ticket for you with the support team to assist further. Please provide yo |

Known limit: the graders check the facts each task asks for, not every statement in a reply. A reply can pass with a correct answer and a wrong incidental detail (for example, the right arrival date for an order it calls "being processed" when it has shipped). A hand-labelled pass over all 240 conversations, with grader agreement, is listed under Next in the experiment README.
