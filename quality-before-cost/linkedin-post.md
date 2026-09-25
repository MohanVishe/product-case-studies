# LinkedIn version

*Post as a LinkedIn article or a long-form post. ~450 words. Link to the full case study at the end.*

---

A cheaper model came up for one of our AI features. Same capability class, materially lower cost per
call, drop-in swap.

I said not yet — and that we wouldn't look at the price until it had proved itself on accuracy first.

Here's the reasoning, because I think the ordering is the part most teams get wrong.

**The product was a continuity problem, not a summarizer.**

I owned an internal product that turned meeting transcripts into notes and tasks. We'd had meeting
notes before. They were accurate and completely useless — each one arrived with no memory of what
came before. "The team discussed the ingestion issue" is a fair summary and worthless when that
issue has come up in four previous meetings and is already assigned.

Once you see the job as continuity, the thing you must never get wrong becomes obvious: **who owes
what to whom.** An awkwardly worded note is an irritation. A task assigned to the wrong person, or
silently dropped, breaks the reason the product exists.

**Why "does the output look fine?" is a trap.**

Notes from a slightly worse model still read fine. Fluency is the easiest thing for a model to keep
and the last thing it loses. What degrades first is the unglamorous structural work — noticing an
action item was assigned, catching that two mentions are the same task, not inventing an owner for
something nobody claimed.

You don't see that by reading a sample and nodding. You find out later, from someone who never got
told about a thing they were supposed to do.

**So we set two rules.**

A fixed benchmark of past meetings, built once and reused, so results were comparable across months.
And accuracy **gates** before cost is considered — not "weigh accuracy against cost." Gate.

That ordering is the whole decision.

Weighing them sounds more balanced. In practice it's how you talk yourself into a worse product,
because the cost number is precise and immediate while the quality number is noisy and contested —
and the precise number wins arguments against the fuzzy one every time, regardless of which one
actually matters. Sequencing removes that failure mode structurally instead of relying on everyone
to be disciplined in the moment.

We scored four things, each mapped to a specific way a real person gets let down: missed actions,
duplicates, coverage, and ownership accuracy.

The failure it was built to catch is a model that's good at readable notes and worse at the
structural work — exactly what eyeballing outputs would miss.

**The part that lasted:** the benchmark outlived the decision. It became the precondition for every
prompt or model change on the product: run the set, show the four numbers, then talk.

The durable artifact from an AI product decision usually isn't the decision. It's the apparatus that
let you make it — because you'll face the same question again in three months with different models.

Full write-up, including what I'd build first next time: https://github.com/MohanVishe/product-case-studies/tree/main/quality-before-cost

---

## Posting notes

- **Best opening line alternative** if the first doesn't land: *"We refused to look at the price
  until the model had earned it."*
- Keep the bold subheads — they carry the skim.
- No hashtag block. One or two at most, if any.
- Post mid-week, morning IST.
- Reply to comments with specifics from the full piece rather than repeating the post.
