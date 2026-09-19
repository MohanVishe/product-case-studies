"""
Cost per successful task for an agentic loop.

Companion to article.md. Every number in the article's worked example is produced
by this file -- run it to reproduce them, or change the parameters to model your
own agent.

The model:

  * Each turn re-sends the whole conversation: a fixed base (system prompt + tool
    definitions + the user request) plus everything added by earlier turns.
  * Each turn adds a roughly constant increment (the tool call and its result).
  * So input tokens over T turns are  T*base + inc * T*(T-1)/2  -- they grow
    faster than the number of turns.
  * A failed run is retried until it succeeds, so the expected cost of one
    successful task is  cost_per_attempt / success_rate.

  * Prompt caching (optional): most APIs can bill the part of the prompt they have
    already seen at a steep discount. With cache_discount=0.1, everything a turn
    re-sends from the previous turn is billed at 10% of the normal price. It damps
    the growth term, and it can flip the answer -- which is Case 3.

Assumptions worth stating: turns are counted per attempt; retries are independent;
with caching, the first turn of each attempt is billed in full (conservative).
Prices are illustrative, in dollars per million tokens, blended across input and
output for simplicity.

    python cost_model.py
"""

from dataclasses import dataclass


@dataclass
class Config:
    name: str
    price_per_m: float   # blended $ per 1M tokens
    turns: int           # turns per attempt
    success_rate: float  # fraction of attempts that complete the task correctly
    base: int = 4_000    # system prompt + tool definitions + request, tokens
    increment: int = 800 # tokens each turn adds to the context
    output: int = 200    # output tokens per turn
    cache_discount: float = 1.0  # price multiplier on re-sent context; 1.0 = no caching

    def input_tokens(self) -> int:
        t = self.turns
        return t * self.base + self.increment * t * (t - 1) // 2

    def billed_input_tokens(self) -> float:
        """Input tokens weighted by price: re-sent context at cache_discount, new tokens in full."""
        prompts = [self.base + self.increment * i for i in range(self.turns)]
        return prompts[0] + sum(self.cache_discount * prev + self.increment for prev in prompts[:-1])

    def output_tokens(self) -> int:
        return self.turns * self.output

    def tokens_per_attempt(self) -> int:
        return self.input_tokens() + self.output_tokens()

    def billed_tokens_per_attempt(self) -> float:
        return self.billed_input_tokens() + self.output_tokens()

    def cost_per_attempt(self) -> float:
        return self.billed_tokens_per_attempt() * self.price_per_m / 1_000_000

    def cost_per_success(self) -> float:
        return self.cost_per_attempt() / self.success_rate


def break_even_price_ratio(strong: Config, cheap: Config) -> float:
    """The price ratio the cheap model must beat to actually be cheaper per task.

    cheap is cheaper per successful task only if

        price_strong / price_cheap  >  (tokens_cheap / tokens_strong)
                                       * (success_strong / success_cheap)
    """
    token_ratio = cheap.billed_tokens_per_attempt() / strong.billed_tokens_per_attempt()
    success_ratio = strong.success_rate / cheap.success_rate
    return token_ratio * success_ratio


def report(strong: Config, cheap: Config, title: str) -> None:
    print(f"\n{title}\n" + "-" * len(title))
    print(f"{'':28}{strong.name:>14}{cheap.name:>14}")
    rows = [
        ("price, $ / 1M tokens", strong.price_per_m, cheap.price_per_m, "{:>14.2f}"),
        ("turns per attempt", strong.turns, cheap.turns, "{:>14d}"),
        ("tokens per attempt", strong.tokens_per_attempt(), cheap.tokens_per_attempt(), "{:>14,d}"),
        ("  billed, after caching", strong.billed_tokens_per_attempt(), cheap.billed_tokens_per_attempt(), "{:>14,.0f}"),
        ("cost per attempt, $", strong.cost_per_attempt(), cheap.cost_per_attempt(), "{:>14.4f}"),
        ("success rate", strong.success_rate, cheap.success_rate, "{:>14.0%}"),
        ("cost per SUCCESS, $", strong.cost_per_success(), cheap.cost_per_success(), "{:>14.4f}"),
    ]
    for label, a, b, fmt in rows:
        print(f"{label:28}" + fmt.format(a) + fmt.format(b))

    price_ratio = strong.price_per_m / cheap.price_per_m
    needed = break_even_price_ratio(strong, cheap)
    delta = cheap.cost_per_success() / strong.cost_per_success() - 1
    print(f"\n  turns ratio        {cheap.turns / strong.turns:.2f}x")
    print(f"  token ratio        {cheap.billed_tokens_per_attempt() / strong.billed_tokens_per_attempt():.2f}x"
          "   <- billed tokens; without caching this grows faster than turns")
    print(f"  price ratio        {price_ratio:.2f}x   (cheap model's advantage)")
    print(f"  break-even ratio   {needed:.2f}x   (advantage it needs)")
    verdict = "CHEAPER" if delta < 0 else "MORE EXPENSIVE"
    print(f"  => cheap model is {abs(delta):.0%} {verdict} per successful task")


if __name__ == "__main__":
    # Case 1 -- the orchestrator: plans, picks tools, reads results, decides again.
    # A weaker model takes more turns (wrong tool, bad arguments, re-planning)
    # and fails more often.
    report(
        Config("capable", price_per_m=2.00, turns=3, success_rate=0.90),
        Config("cheaper", price_per_m=0.50, turns=7, success_rate=0.60),
        "Case 1: the orchestrator (decision-making node)",
    )

    # Case 2 -- a well-scoped leaf node: one call, e.g. reformatting a tool result
    # into a fixed schema. Same turns, near-identical success. The price gap passes
    # straight through.
    report(
        Config("capable", price_per_m=2.00, turns=1, success_rate=0.98),
        Config("cheaper", price_per_m=0.50, turns=1, success_rate=0.97),
        "Case 2: a well-scoped leaf node",
    )

    # Case 3 -- the orchestrator again, with prompt caching: re-sent context billed at
    # 10% of the normal price. The growth term shrinks, and the cheap model now wins
    # on cost -- while still failing 40% of tasks against 10%. Cost stopped being the
    # reason to reject it; quality didn't.
    report(
        Config("capable", price_per_m=2.00, turns=3, success_rate=0.90, cache_discount=0.1),
        Config("cheaper", price_per_m=0.50, turns=7, success_rate=0.60, cache_discount=0.1),
        "Case 3: the orchestrator, with prompt caching",
    )
