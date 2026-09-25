"""The figures in article.md, drawn once and rendered twice: SVG for GitHub, vector for the PDF.

    python figures.py          # writes figures/*.svg

Conceptual figures use the illustrative parameters from cost_model.py. Experiment figures read
experiment/results/summary.json and are skipped if it doesn't exist yet.
"""
import json
import os
import re

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Line, Polygon, PolyLine, Rect, String, Circle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from cost_model import Config

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures")
SUMMARY = os.path.join(os.environ.get("EVAL_RESULTS", os.path.join(HERE, "experiment", "results")), "summary.json")

for _name, _file in (("Sans", "segoeui"), ("Sans-B", "segoeuib"), ("Sans-SB", "seguisb")):
    try:
        pdfmetrics.registerFont(TTFont(_name, f"C:/Windows/Fonts/{_file}.ttf"))
    except Exception:          # not on Windows: fall back to the built-in Helvetica
        pdfmetrics.registerFont(pdfmetrics.getFont("Helvetica-Bold" if "B" in _name else "Helvetica"))

C = colors.HexColor
INK, MUTED, FAINT, GRID, PANEL = C("#1f2328"), C("#656d76"), C("#9aa1a9"), C("#e3e6ea"), C("#f6f8fa")
BIG, SMALL = C("#1f5fa8"), C("#d4731c")            # capable model, cheaper model
BIG_BG, SMALL_BG = C("#e7f0fb"), C("#fcefe3")
GOOD, BAD = C("#2e7d4f"), C("#b3261e")
PURPLE, TEAL, SLATE = C("#6f42c1"), C("#0f766e"), C("#475569")
BASE_GREY = C("#c9ced4")
CANVAS_BG, BOX_WHITE, ON_COLOUR = colors.white, colors.white, colors.white
W = 680

# Names whose colour is swapped for a CSS variable when rendering for the website, so the
# figures follow its light/dark theme instead of sitting on a white box. See theme_svg().
THEMED = ["INK", "MUTED", "FAINT", "GRID", "PANEL", "BOX_WHITE", "ON_COLOUR", "BASE_GREY",
          "BIG", "SMALL", "BIG_BG", "SMALL_BG", "GOOD", "BAD", "PURPLE", "TEAL", "SLATE",
          "CANVAS_BG"]
CSS_VAR = {
    "INK": "--color-ink", "MUTED": "--color-muted", "FAINT": "--color-faint",
    "GRID": "--color-line", "PANEL": "--color-surface", "BOX_WHITE": "--color-surface",
    "ON_COLOUR": "--fig-on-colour", "BASE_GREY": "--fig-grey", "BIG": "--fig-blue",
    "SMALL": "--fig-orange", "BIG_BG": "--fig-blue-bg", "SMALL_BG": "--fig-orange-bg",
    "GOOD": "--color-ok", "BAD": "--fig-red", "PURPLE": "--fig-purple", "TEAL": "--fig-teal",
    "SLATE": "--fig-slate", "CANVAS_BG": "transparent",
}


# ---- primitives ---------------------------------------------------------------------------
def canvas(h):
    d = Drawing(W, h)
    d.add(Rect(0, 0, W, h, fillColor=CANVAS_BG, strokeColor=None))
    return d


def text(d, x, y, s, size=11, font="Sans", color=None, anchor="start"):
    # Colour defaults are resolved here, not in the signature: theme_svg() swaps the module
    # globals, and a default bound at import time would keep the original colour.
    color = INK if color is None else color
    d.add(String(x, y, s, fontName=font, fontSize=size, fillColor=color, textAnchor=anchor))


def title(d, h, t, sub=None):
    text(d, 20, h - 30, t, 15, "Sans-B")
    if sub:
        text(d, 20, h - 48, sub, 10.5, color=MUTED)


def wrap(s, width, size, font="Sans"):
    lines, cur = [], ""
    for word in s.split():
        trial = (cur + " " + word).strip()
        if pdfmetrics.stringWidth(trial, font, size) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def box(d, x, y, w, h, head, body=None, fill=None, edge=None, head_color=None, size=10.5, radius=6):
    """A rounded box with a bold heading and optional wrapped body text, top-aligned."""
    fill = PANEL if fill is None else fill
    edge = GRID if edge is None else edge
    head_color = INK if head_color is None else head_color
    d.add(Rect(x, y, w, h, rx=radius, ry=radius, fillColor=fill, strokeColor=edge, strokeWidth=1))
    ty = y + h - 18
    for ln in wrap(head, w - 20, size + 0.5, "Sans-B"):
        text(d, x + w / 2, ty, ln, size + 0.5, "Sans-B", head_color, "middle")
        ty -= size + 4
    if body:
        ty -= 2
        for ln in wrap(body, w - 20, size - 1):
            text(d, x + w / 2, ty, ln, size - 1, color=MUTED, anchor="middle")
            ty -= size + 2


def arrow(d, x1, y1, x2, y2, color=None, width=1.4, dash=None, head=7):
    color = FAINT if color is None else color
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=width, strokeDashArray=dash))
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    p1 = (x2 - head * math.cos(a - 0.4), y2 - head * math.sin(a - 0.4))
    p2 = (x2 - head * math.cos(a + 0.4), y2 - head * math.sin(a + 0.4))
    d.add(Polygon([x2, y2, *p1, *p2], fillColor=color, strokeColor=color, strokeWidth=0.5))


def legend(d, x, y, items, size=10):
    for color, label in items:
        d.add(Rect(x, y - 1, 10, 10, fillColor=color, strokeColor=None))
        text(d, x + 15, y, label, size, color=INK)
        x += 25 + pdfmetrics.stringWidth(label, "Sans", size)


def hbar_panel(d, x, y, w, label, vals, fmt, better="high", note=None):
    """A small panel: one metric, one horizontal bar per model, the better value marked with a dot."""
    text(d, x, y, label, 10.5, "Sans-SB")
    if note:
        text(d, x + w, y, note, 9, color=MUTED, anchor="end")
    top = max(v for _, v, _ in vals) or 1
    best = None if not better else (max if better == "high" else min)(v for _, v, _ in vals)
    by = y - 22
    for name, v, color in vals:
        text(d, x, by + 3, name, 9.5, color=MUTED)
        bw = (w - 110) * v / top
        d.add(Rect(x + 34, by, max(bw, 1.5), 13, fillColor=color, strokeColor=None))
        label_v = fmt(v)
        win = best is not None and v == best
        text(d, x + 40 + bw, by + 3, label_v, 9.5, "Sans-B" if win else "Sans", INK)
        if win:
            lw = pdfmetrics.stringWidth(label_v, "Sans-B", 9.5)
            d.add(Circle(x + 40 + bw + lw + 8, by + 6.5, 3.5, fillColor=GOOD, strokeColor=None))
        by -= 20


# ---- conceptual figures ---------------------------------------------------------------------
def fig_context_growth():
    strong = Config("capable", 2.0, 3, 0.9)
    cheap = Config("cheaper", 0.5, 7, 0.6)
    h = 350
    d = canvas(h)
    title(d, h, "Every turn re-sends everything before it",
          "Input tokens per turn of one attempt. Illustrative parameters from cost_model.py.")
    x0, y0, ch = 60, 60, 190
    top = cheap.base + cheap.increment * (cheap.turns - 1)
    scale = ch / 10000
    for v in range(0, 10001, 2500):
        yy = y0 + v * scale
        d.add(Line(x0, yy, W - 20, yy, strokeColor=GRID, strokeWidth=0.6))
        text(d, x0 - 6, yy - 3, f"{v:,}", 9, color=MUTED, anchor="end")
    bw, gap = 30, 8
    groups = [(strong, BIG, x0 + 20), (cheap, SMALL, x0 + 20 + 3 * (bw + gap) + 70)]
    for cfg, color, gx in groups:
        for t in range(cfg.turns):
            bx = gx + t * (bw + gap)
            hist = cfg.increment * t
            d.add(Rect(bx, y0, bw, cfg.base * scale, fillColor=BASE_GREY, strokeColor=None))
            if hist:
                d.add(Rect(bx, y0 + cfg.base * scale, bw, hist * scale, fillColor=color, strokeColor=None))
            text(d, bx + bw / 2, y0 - 14, str(t + 1), 9.5, color=MUTED, anchor="middle")
        mid = gx + (cfg.turns * (bw + gap) - gap) / 2
        text(d, mid, y0 - 30, f"{cfg.name} model: {cfg.turns} turns", 10.5, "Sans-SB", anchor="middle")
        text(d, mid, y0 + (cfg.base + cfg.increment * (cfg.turns - 1)) * scale + 10,
             f"{cfg.input_tokens():,} input tokens", 10, "Sans-B", color, "middle")
    legend(d, 20, h - 74, [(BASE_GREY, "system prompt + tools + request"), (SMALL, "earlier turns, re-sent")])
    text(d, W - 20, 96, "2.3x the turns,", 10.5, "Sans-B", INK, "end")
    text(d, W - 20, 81, "3.1x the tokens", 10.5, "Sans-B", SMALL, "end")
    return d


def fig_three_answers():
    s1, c1 = Config("capable", 2.0, 3, 0.9), Config("cheaper", 0.5, 7, 0.6)
    s3, c3 = Config("capable", 2.0, 3, 0.9, cache_discount=0.1), Config("cheaper", 0.5, 7, 0.6, cache_discount=0.1)
    groups = [("Cost per attempt", "what a cost dashboard shows", s1.cost_per_attempt(), c1.cost_per_attempt()),
              ("Cost per successful task", "what you actually pay for", s1.cost_per_success(), c1.cost_per_success()),
              ("Per successful task,", "with prompt caching", s3.cost_per_success(), c3.cost_per_success())]
    h = 370
    d = canvas(h)
    title(d, h, "Same two models, three different answers",
          "Orchestrator node, illustrative parameters. The cheaper model is 4x cheaper per token in every column.")
    x0, y0, ch = 60, 78, 180
    scale = ch / 0.04
    for v in (0, 0.01, 0.02, 0.03, 0.04):
        yy = y0 + v * scale
        d.add(Line(x0, yy, W - 20, yy, strokeColor=GRID, strokeWidth=0.6))
        text(d, x0 - 6, yy - 3, f"${v:.2f}", 9, color=MUTED, anchor="end")
    gw = (W - x0 - 40) / 3
    for i, (lab, sub, a, b) in enumerate(groups):
        gx = x0 + 20 + i * gw
        for j, (v, col) in enumerate(((a, BIG), (b, SMALL))):
            bx = gx + 30 + j * 62
            d.add(Rect(bx, y0, 52, v * scale, fillColor=col, strokeColor=None))
            text(d, bx + 26, y0 + v * scale + 5, f"${v:.4f}", 9.5, anchor="middle")
        delta = b / a - 1
        text(d, gx + 86, y0 + max(a, b) * scale + 24, f"cheaper model {delta:+.0%}", 10.5, "Sans-B",
             GOOD if delta < 0 else BAD, "middle")
        text(d, gx + 86, y0 - 18, lab, 10.5, "Sans-SB", anchor="middle")
        text(d, gx + 86, y0 - 32, sub, 9.5, color=MUTED, anchor="middle")
    legend(d, 20, h - 74, [(BIG, "capable model"), (SMALL, "cheaper model")])
    return d


def fig_placement():
    h = 320
    d = canvas(h)
    title(d, h, "Where each model tends to belong",
          "Decision nodes compound errors across turns; leaf nodes do one narrow job in one call.")
    y = 170
    box(d, 20, y, 110, 60, "Customer message", fill=BOX_WHITE)
    box(d, 160, y, 130, 60, "Router", "classify the intent, 1 call", SMALL_BG, SMALL)
    box(d, 320, y - 10, 150, 80, "Orchestrator", "plan, pick tools, read results, decide again", BIG_BG, BIG)
    box(d, 330, 50, 130, 50, "Tools", "orders, stock, tickets", fill=BOX_WHITE)
    box(d, 500, y, 150, 60, "Formatter", "tool results to a fixed reply schema", SMALL_BG, SMALL)
    arrow(d, 130, y + 30, 158, y + 30)
    arrow(d, 290, y + 30, 318, y + 30)
    arrow(d, 470, y + 30, 498, y + 30)
    arrow(d, 375, y - 10, 375, 102, BIG)
    arrow(d, 415, 100, 415, y - 12, BIG)
    text(d, 424, 128, "loop: many turns", 9.5, color=BIG)
    legend(d, 20, 110, [(BIG, "decision node: start capable")])
    legend(d, 20, 90, [(SMALL, "leaf node: a small model is often enough")])
    text(d, 20, 60, "\"Tends to\", not \"always\":", 9.5, color=MUTED)
    text(d, 20, 46, "the evaluation decides each one.", 9.5, color=MUTED)
    return d


def fig_trace():
    """Anatomy of one multi-turn conversation, and the level at which each thing is evaluated."""
    h = 450
    d = canvas(h)
    title(d, h, "What to evaluate in one multi-turn conversation",
          "A conversation from the test agent. Each band is a level you can grade, and each needs its own checks.")
    lanes = [("Customer", 350), ("Orchestrator", 292), ("Tools", 234)]
    for name, y in lanes:
        text(d, 20, y + 6, name, 10, "Sans-SB", MUTED)
        d.add(Line(110, y + 10, W - 20, y + 10, strokeColor=GRID, strokeWidth=0.8, strokeDashArray=[2, 3]))
    x = 118

    def ev(xx, lane, label, color, w=66):
        y = dict(lanes)[lane]
        d.add(Rect(xx, y, w, 22, rx=4, ry=4, fillColor=color, strokeColor=None))
        text(d, xx + w / 2, y + 7, label, 8.5, "Sans-SB", ON_COLOUR, "middle")

    seq = [("Customer", "turn 1", SLATE), ("Orchestrator", "call", BIG), ("Tools", "find", FAINT),
           ("Orchestrator", "call", BIG), ("Tools", "orders", FAINT), ("Orchestrator", "reply", BIG),
           ("Customer", "turn 2", SLATE), ("Orchestrator", "call", BIG), ("Tools", "update", FAINT),
           ("Orchestrator", "reply", BIG)]
    xs = []
    for lane, label, color in seq:
        ev(x, lane, label, color, 50)
        xs.append(x)
        x += 55
    # brackets for the levels
    def bracket(x1, x2, y, label, sub, color):
        d.add(Line(x1, y, x2, y, strokeColor=color, strokeWidth=2))
        d.add(Line(x1, y, x1, y + 6, strokeColor=color, strokeWidth=2))
        d.add(Line(x2, y, x2, y + 6, strokeColor=color, strokeWidth=2))
        text(d, (x1 + x2) / 2, y - 14, label, 10, "Sans-B", color, "middle")
        text(d, (x1 + x2) / 2, y - 27, sub, 8.8, color=MUTED, anchor="middle")

    bracket(xs[1], xs[1] + 50, 216, "1 Node", "one call", BIG)
    bracket(xs[1], xs[5] + 50, 170, "2 Trajectory", "tools, arguments, order, retries", PURPLE)
    bracket(xs[0], xs[5] + 50, 124, "3 Turn", "was this reply right?", TEAL)
    bracket(xs[0], xs[9] + 50, 78, "4 Conversation", "end state + every reply, across turns", INK)
    text(d, xs[0], 22, "5 Reliability: run the whole conversation k times and count how often all k succeed.",
         10, "Sans-B", BAD)
    return d


def fig_eval_loop():
    h = 330
    d = canvas(h)
    title(d, h, "How to run it: the evaluation loop",
          "Every model or prompt change goes around once. The loop is what turns an argument into an afternoon.")
    bw, bh, gap = 145, 78, 22
    col = lambda i: 20 + i * (bw + gap)
    y1, y2 = 168, 50
    steps = [("1 Build the sets", "per node, end to end, multi-turn; from real traffic"),
             ("2 Instrument", "one span per model call: node, model, tokens, latency"),
             ("3 Run k times", "every candidate config, same tasks, same seeds"),
             ("4 Grade", "end state first, rubric judge second, humans spot-check")]
    for i, (hd, body) in enumerate(steps):
        box(d, col(i), y1, bw, bh, hd, body, BOX_WHITE, GRID)
        if i:
            arrow(d, col(i) - gap + 1, y1 + bh / 2, col(i) - 2, y1 + bh / 2)
    lower = [(3, "5a Quality gate", "success rate and pass^k above the bar?", GOOD),
             (2, "5b Latency gate", "p95 per conversation within budget?", TEAL),
             (1, "5c Cost", "cheapest per successful task wins", BIG),
             (0, "6 Ship and monitor", "regression gate in CI; failures become new tasks", INK)]
    for j, (i, hd, body, c) in enumerate(lower):
        box(d, col(i), y2, bw, bh, hd, body, BOX_WHITE, c, head_color=c)
        if j:
            arrow(d, col(i) + bw + gap - 1, y2 + bh / 2, col(i) + bw + 2, y2 + bh / 2, c)
    arrow(d, col(3) + bw / 2, y1, col(3) + bw / 2, y2 + bh + 2)
    arrow(d, col(0) + bw / 2, y2 + bh, col(0) + bw / 2, y1 - 2, FAINT, dash=[3, 3])
    text(d, 20, 22, "A config that fails a gate is out, however cheap it is. Cost only ranks what's left.",
         10, "Sans-B", MUTED)
    return d


# ---- experiment figures ---------------------------------------------------------------------
def short(m):
    return m.split(":")[-1].upper()


def share(v):
    """A percentage, whole unless it sits exactly on a half (62.5% would otherwise print as 62%)."""
    p = round(v * 100, 6)
    return f"{p:.1f}%" if p % 1 == 0.5 else f"{round(p):.0f}%"


def fig_experiment(s):
    orch, rout = s["orchestrator"], s["router"]
    models = sorted(orch, key=lambda m: "7b" in m)
    cols = {models[0]: SMALL, models[1]: BIG}
    any_m = orch[models[0]]
    k = any_m["trials_per_task"]
    pw, ph = 205, 84
    # Per-call latency is mostly a fixed cost per request in this harness (see analyze.py's
    # latency fit), so it gets no "better" dot: the small gap between models is not model speed.
    fixed = [orch[m]["latency_fit"]["fixed_s_per_call"] for m in models if "latency_fit" in orch[m]]
    per_call_label = f"Latency / call (~{sum(fixed) / len(fixed):.0f} s fixed)" if fixed else "Latency / model call"
    h = 150 + 3 * ph + (ph + 40 if rout else 0)
    d = canvas(h)
    title(d, h, "Measured: the same agent on a 3B and a 7B model",
          f"{any_m['tasks']} conversations x {k} runs each, local Qwen2.5-Coder models. "
          "Green dot = better. No dot = neither is better.")
    rows = [
        ("QUALITY", [
            ("Success rate", lambda m: orch[m]["success_rate"], share, "high"),
            (f"All {k} runs succeed (pass^{k})", lambda m: orch[m]["pass_hat_k"][str(k)], lambda v: f"{v:.0%}", "high"),
            ("Identified the customer first", lambda m: orch[m]["identify_first_rate"], lambda v: f"{v:.0%}", "high")]),
        ("TRAJECTORY AND COST", [
            ("Model calls / conversation", lambda m: orch[m]["calls_per_episode"], lambda v: f"{v:.1f}", None),
            ("Rejected tool calls / conv.", lambda m: orch[m]["tool_errors_per_episode"], lambda v: f"{v:.2f}", "low"),
            ("Tokens / successful task", lambda m: orch[m]["blended_tokens_per_success"], lambda v: f"{v:,.0f}", "low")]),
        ("LATENCY", [
            (per_call_label, lambda m: orch[m]["latency_per_call_s"], lambda v: f"{v:.2f} s", None),
            ("Conversation, p95", lambda m: orch[m]["latency_p95_s"], lambda v: f"{v:.1f} s", "low"),
            ("Time / successful task", lambda m: orch[m]["time_per_success_s"], lambda v: f"{v:.1f} s", "low")]),
    ]
    y = h - 80
    text(d, 20, y + 4, "ORCHESTRATOR (decision node)", 10, "Sans-B", BIG)
    for r, (rlabel, panels) in enumerate(rows):
        y -= 22 if r == 0 else ph
        for i, (lab, f, fmt, better) in enumerate(panels):
            hbar_panel(d, 20 + i * (pw + 22), y, pw, lab, [(short(m), f(m), cols[m]) for m in models], fmt, better)
    if rout:
        y -= ph + 6
        text(d, 20, y + 4, "ROUTER (leaf node)", 10, "Sans-B", SMALL)
        y -= 22
        rp = [("Accuracy", lambda m: rout[m]["accuracy"], lambda v: f"{v:.0%}", "high"),
              ("Tokens / correct call", lambda m: rout[m]["blended_tokens_per_success"], lambda v: f"{v:,.0f}", "low"),
              (per_call_label, lambda m: rout[m]["latency_per_call_s"], lambda v: f"{v:.2f} s", None)]
        for i, (lab, f, fmt, better) in enumerate(rp):
            hbar_panel(d, 20 + i * (pw + 22), y, pw, lab, [(short(m), f(m), cols[m]) for m in models], fmt, better)
    return d


def fig_pass_k(s):
    orch = s["orchestrator"]
    models = sorted(orch, key=lambda m: "7b" in m)
    h = 300
    d = canvas(h)
    title(d, h, "Reliability: how often every one of k runs succeeds (pass^k)",
          "Same tasks, repeated. A model that is right 'most of the time' is wrong for somebody every day.")
    x0, y0, cw, ch = 70, 50, W - 250, 170
    ks = sorted(int(k) for k in orch[models[0]]["pass_hat_k"])
    for v in (0, 0.25, 0.5, 0.75, 1.0):
        yy = y0 + v * ch
        d.add(Line(x0, yy, x0 + cw, yy, strokeColor=GRID, strokeWidth=0.6))
        text(d, x0 - 6, yy - 3, f"{v:.0%}", 9, color=MUTED, anchor="end")
    px = lambda k: x0 + (k - 1) / max(len(ks) - 1, 1) * cw
    for k in ks:
        text(d, px(k), y0 - 16, f"k={k}", 9.5, color=MUTED, anchor="middle")
    for m, col in zip(models, (SMALL, BIG)):
        pts = [(px(k), y0 + orch[m]["pass_hat_k"][str(k)] * ch) for k in ks]
        d.add(PolyLine([c for p in pts for c in p], strokeColor=col, strokeWidth=2.2))
        for p in pts:
            d.add(Circle(p[0], p[1], 3.2, fillColor=col, strokeColor=CANVAS_BG, strokeWidth=1))
        text(d, pts[-1][0] + 10, pts[-1][1] - 3, f"{short(m)}  {orch[m]['pass_hat_k'][str(ks[-1])]:.0%}",
             10.5, "Sans-B", col)
        text(d, pts[0][0] + 6, pts[0][1] + 8, share(orch[m]['pass_hat_k']['1']), 9.5, "Sans-SB", col)
    return d


def fig_context_measured(s):
    orch = s["orchestrator"]
    models = sorted(orch, key=lambda m: "7b" in m)
    h = 280
    d = canvas(h)
    title(d, h, "Measured: input tokens by position of the call in the conversation",
          "Mean over all conversations that reached that call. Each call re-sends the conversation so far.")
    x0, y0, cw, ch = 70, 50, W - 130, 160
    series = {m: {int(k): v for k, v in orch[m]["input_tokens_by_call"].items()} for m in models}
    n = max(max(v) for v in series.values()) + 1
    top = max(max(v.values()) for v in series.values())
    top = (int(top / 1000) + 1) * 1000
    for v in range(0, top + 1, max(top // 4, 1)):
        yy = y0 + v / top * ch
        d.add(Line(x0, yy, x0 + cw, yy, strokeColor=GRID, strokeWidth=0.6))
        text(d, x0 - 6, yy - 3, f"{v:,}", 9, color=MUTED, anchor="end")
    px = lambda i: x0 + i / max(n - 1, 1) * cw
    for i in range(n):
        text(d, px(i), y0 - 16, str(i + 1), 9.5, color=MUTED, anchor="middle")
    for m, col in zip(models, (SMALL, BIG)):
        pts = [(px(i), y0 + v / top * ch) for i, v in sorted(series[m].items())]
        d.add(PolyLine([c for p in pts for c in p], strokeColor=col, strokeWidth=2.2))
        text(d, pts[-1][0] + 6, pts[-1][1] + 6, short(m), 10.5, "Sans-B", col)
    text(d, x0 + cw, y0 - 32, "model call number", 9.5, color=MUTED, anchor="end")
    return d


CONCEPT = {"context-growth": fig_context_growth, "three-answers": fig_three_answers,
           "placement": fig_placement, "trace-levels": fig_trace, "eval-loop": fig_eval_loop}
EXPERIMENT = {"experiment-results": fig_experiment, "experiment-pass-k": fig_pass_k}


def build(name):
    if name in CONCEPT:
        return CONCEPT[name]()
    with open(SUMMARY, encoding="utf-8") as f:
        return EXPERIMENT[name](json.load(f))


FONT_STACK = {"Sans-B": ("'Segoe UI', 'Helvetica Neue', Arial, sans-serif", "bold"),
              "Sans-SB": ("'Segoe UI', 'Helvetica Neue', Arial, sans-serif", "600"),
              "Sans": ("'Segoe UI', 'Helvetica Neue', Arial, sans-serif", "normal")}


def _fonts(svg):
    for name, (stack, weight) in FONT_STACK.items():
        svg = re.sub(rf"font-family\s*:\s*{name}\b", f"font-family: {stack}; font-weight: {weight}", svg)
        svg = svg.replace(f'font-family="{name}"', f'font-family="{stack}" font-weight="{weight}"')
    return svg


def to_svg(d):
    return _fonts(renderSVG.drawToString(d))


def _sentinel(i):
    """A colour no figure uses, unique after the renderer rounds it to whole percentages."""
    return colors.Color((i * 15 + 5) / 255, 128 / 255, 200 / 255)


def _hex(c):
    return "#%02x%02x%02x" % (round(c.red * 255), round(c.green * 255), round(c.blue * 255))


def theme_svg(name):
    """Render a figure with CSS variables in place of fixed colours.

    Used for the website, where the figures follow its light/dark theme instead of sitting on a
    white rectangle. Each themed colour is drawn as a unique sentinel, then swapped for
    var(--token, <the original colour>), so the file still renders correctly on its own.
    """
    original = {n: globals()[n] for n in THEMED}
    globals().update({n: _sentinel(i) for i, n in enumerate(THEMED)})
    try:
        svg = renderSVG.drawToString(build(name))
    finally:
        globals().update(original)
    for i, n in enumerate(THEMED):
        c = _sentinel(i)
        rgb = "rgb(%d%%,%d%%,%d%%)" % (c.red * 100, c.green * 100, c.blue * 100)
        var = CSS_VAR[n]
        svg = svg.replace(rgb, "transparent" if var == "transparent" else f"var({var}, {_hex(original[n])})")
    return _fonts(svg)


if __name__ == "__main__":
    import sys

    site = sys.argv[sys.argv.index("--site") + 1] if "--site" in sys.argv else None
    names = list(CONCEPT) + (list(EXPERIMENT) if os.path.exists(SUMMARY) else [])
    out = site or OUT
    os.makedirs(out, exist_ok=True)
    for n in names:
        with open(os.path.join(out, f"{n}.svg"), "w", encoding="utf-8") as f:
            f.write(theme_svg(n) if site else to_svg(build(n)))
        print("wrote", os.path.join(out, f"{n}.svg"))
