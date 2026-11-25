"""Build the PlayerPulse business deck (PPTX) from measured numbers in deck/deck_numbers.json.
Charts are rendered with matplotlib; convert to PDF with LibreOffice:
  soffice --headless --convert-to pdf deck/PlayerPulse_deck.pptx --outdir deck/
usage: python build_deck.py   (run with a venv that has python-pptx + matplotlib)"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
N = json.load(open(os.path.join(HERE, "deck_numbers.json")))

# reference palette (dataviz skill): surface, ink, series-1 blue; baseline = recessive gray
SURF, INK, INK2, MUTED, BLUE, GRAY, ORANGE = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#2a78d6", "#b9b8b2", "#eb6834"
rgb = lambda h: RGBColor.from_string(h.lstrip("#"))

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def text(slide, x, y, w, h, s, size=18, color=INK, bold=False, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(s if isinstance(s, list) else [s]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), bold, rgb(color), "Calibri"
        p.space_after = Pt(size * 0.35)
    return tb


def slide(title, kicker=None):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(SURF)
    if kicker:
        text(s, 0.6, 0.35, 12, 0.4, kicker.upper(), 12, MUTED, True)
    text(s, 0.6, 0.65, 12.2, 1.0, title, 30, INK, True)
    text(s, 0.6, 7.0, 12.2, 0.35, "PlayerPulse · Emberforge Studios (fictional) · synthetic data · numbers from the Databricks backtest (evidence/ in repo)", 10, MUTED)
    return s


def tile(s, x, y, w, value, label, color=INK):
    text(s, x, y, w, 0.8, value, 34, color, True)
    text(s, x, y + 0.85, w, 0.8, label, 13, INK2)


def table(s, x, y, w, rows, col_w=None, size=14):
    shp = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(0.42 * len(rows)))
    t = shp.table
    for j, cw in enumerate(col_w or []):
        t.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i, j)
            c.text = str(v)
            c.fill.solid()
            c.fill.fore_color.rgb = rgb("#eeeeea" if i == 0 else SURF)
            for p in c.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size, r.font.color.rgb, r.font.name = Pt(size), rgb(INK), "Calibri"
                    r.font.bold = i == 0 or (j == len(row) - 1 and i > 0 and "PlayerPulse" in rows[0][-1])


def chart_png(name, fn, w=6.2, h=3.6):
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
    fn(ax)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color("#d8d7d2")
    ax.tick_params(colors=INK2, labelsize=9)
    ax.yaxis.grid(True, color="#ecebe7", linewidth=0.8); ax.set_axisbelow(True)
    fig.tight_layout()
    p = os.path.join(HERE, f"_{name}.png")
    fig.savefig(p, facecolor=SURF); plt.close(fig)
    return p


def fmt_k(v):
    return f"${v / 1e6:.1f}M" if v >= 1e6 else f"${v / 1e3:.0f}K"


# ---------------------------------------------------------------- 1. outcome
s = slide("Same LiveOps budget. +{:.0f}% more paying-player revenue retained.".format(N["net_uplift_pct"]), "The outcome")
tile(s, 0.6, 2.0, 3.9, fmt_k(N["incremental_per_1m_dau"]), "incremental net revenue per year, per 1M DAU (scaled from the 26.6K-DAU backtest)", BLUE)
tile(s, 4.7, 2.0, 3.9, f"{N['revenue_reached_pp_pct']:.0f}% vs {N['revenue_reached_sq_pct']:.0f}%", "of at-risk payer revenue reached each week, PlayerPulse vs. today's win-back rule")
tile(s, 8.8, 2.0, 3.9, "0", "paid offers to minors or players without marketing consent (checked on every daily run)")
text(s, 0.6, 4.4, 12, 2.2, [
    "PlayerPulse predicts which active players will stop playing in the next 14 days, ranks them by revenue at stake, and gives LiveOps the right fix for each one: restore the purchase, apologize for the crash, refill energy, or make an offer (only if eligible).",
    f"For Emberline (26.6K DAU) that is +{fmt_k(N['incremental_annual'])}/year net. The rollout plan proves it with a 4-week A/B holdout."], 16, INK2)

# ---------------------------------------------------------------- 2. the problem
s = slide("Season 7 more than doubled player churn, and paying players followed", "The business challenge")
seasons = N["lapse_by_season"]  # {"S6": {"all":..,"whale":..}, ...}
def lapse_chart(ax):
    xs = list(seasons.keys())
    allv = [seasons[k]["all"] * 100 for k in xs]
    wh = [seasons[k]["whale"] * 100 for k in xs]
    import numpy as np
    x = np.arange(len(xs)); bw = 0.36
    b1 = ax.bar(x - bw / 2 - 0.01, allv, bw, color=GRAY, label="All active players")
    b2 = ax.bar(x + bw / 2 + 0.01, wh, bw, color=BLUE, label="Whales ($100+ / 90 days)")
    for b in list(b1) + list(b2):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.04, f"{b.get_height():.2f}%", ha="center", fontsize=8, color=INK)
    ax.set_xticks(x, ["Season 6\nAshen Crown", "Season 7\nRift Energy", "Season 8\nEmber Tide"])
    ax.set_ylabel("14-day lapse rate of active players (%)", color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
s.shapes.add_picture(chart_png("lapse", lapse_chart), Inches(0.6), Inches(1.7), width=Inches(6.6))
text(s, 7.5, 1.8, 5.4, 5, [
    "• June 2: Season 7 energy rework. Matches cost energy; refills are slow for non-pass holders.",
    "• Aug 12: client v7.2 crash regression on low-tier Android, fixed Sep 24.",
    f"• Crash rate on low-tier devices: {N['crash_low_before']:.1%} → {N['crash_low_v72']:.1%} per session during v7.2.",
    f"• {N['tickets']:,} support tickets this season, e.g. \"charged twice for gem pack… not spending another cent\". Nobody reads them at scale.",
    "• Today's rule, \"payers quiet 3+ days get a discount\", acts too late and treats every cause the same way."], 15, INK2)

# ---------------------------------------------------------------- 3. why status quo fails
s = slide("Why today's win-back program misses", "The business challenge")
table(s, 0.6, 1.8, 12.1, [
    ["Today: \"payers quiet for 3+ days get a discount\"", "What that costs"],
    ["Late: acts on day 3+", "Win-back converts ~2.5x better while the player is still playing (25% vs 10%)"],
    ["One remedy for every cause", "A discount doesn't fix a double charge, a crash, or an energy wall"],
    ["Blind to what players say", f"Players with a payment ticket lapse at {N['lapse_payment']:.1%} and with quit intent at {N['lapse_intent']:.1%}, vs {N['lapse_base']:.1%} overall"],
    ["Ranked by spend only", "Misses big spenders who are still active but already disengaging"],
    ["No policy guardrail", "Risk of sending paid offers to minors or players who opted out"],
], [5.2, 6.9], 15)

# ---------------------------------------------------------------- 4. solution
s = slide("PlayerPulse: from raw game data to the right action in the game", "How Databricks solves it")
steps = [("Lakeflow", "Telemetry, receipts, tickets, LiveOps calendar,\naccounts, ingested daily with 13 quality checks"),
         ("Unity Catalog", "PII masked at source · minors & consent\nenforced · lineage · model registry"),
         ("GenAI", f"Claude reads every ticket: root cause,\nsentiment, quit intent ({N['tickets']:,} classified, 0 errors)"),
         ("ML", f"P(lapse in 14 days) for {N['scored']:,} active players · out-of-time AUC {N['auc']:.3f}"),
         ("Lakebase", f"Retention queue served to app + game\nbackend; approvals written back"),
         ("Genie + App", "LiveOps console with AI-drafted messages;\nquestions in plain English")]
for i, (h, d) in enumerate(steps):
    x = 0.6 + (i % 3) * 4.15; y = 1.9 + (i // 3) * 2.45
    box = s.shapes.add_shape(1, Inches(x), Inches(y), Inches(3.9), Inches(2.15))
    box.fill.solid(); box.fill.fore_color.rgb = rgb("#f1f0ec"); box.line.color.rgb = rgb("#e0dfda")
    text(s, x + 0.2, y + 0.15, 3.6, 0.5, f"{i + 1}. {h}", 18, BLUE, True)
    text(s, x + 0.2, y + 0.75, 3.6, 1.4, d.replace("\n", " "), 14, INK2)

# ---------------------------------------------------------------- 5. VP LiveOps workflow
s = slide("For the VP LiveOps: a daily queue with the cause and the fix", "Domain owner value")
text(s, 0.6, 1.8, 6.3, 5, [
    "• Morning queue ranked by revenue at risk, each row with why (e.g. \"Unresolved payment issue · play frequency dropping\") and what to do.",
    "• Fix-first actions: support escalation → tech fix + apology gift → energy refill → guild invite → personalized offer (only if eligible).",
    "• One click: review the Claude-drafted in-game mail and approve. It's written to Lakebase and delivered at the next login.",
    "• Ask Genie: \"What are high-risk payers complaining about?\", \"Crash rate by device tier after v7.2?\""], 15, INK2)
rows = [["Next-best-action", "Players", "Revenue at risk"]] + [[a, f"{p:,}", f"${v:,.0f}"] for a, p, v in N["nba"]]
table(s, 7.2, 1.8, 5.5, rows, [2.9, 1.1, 1.5], 12)

# ---------------------------------------------------------------- 6. CFO value
s = slide("For the GM / CFO: same budget, more revenue kept", "Business outcomes & impact")
def value_chart(ax):
    labels = ["At-risk payer revenue\nreached (10 wks)", "Revenue retained,\nnet of cost (10 wks)"]
    sq = [N["sq_reached"], N["sq_net"]]; pp = [N["pp_reached"], N["pp_net"]]
    import numpy as np
    x = np.arange(2); bw = 0.36
    b1 = ax.bar(x - bw / 2 - 0.01, sq, bw, color=GRAY, label="Status quo (quiet 3+ days rule)")
    b2 = ax.bar(x + bw / 2 + 0.01, pp, bw, color=BLUE, label="PlayerPulse")
    for b in list(b1) + list(b2):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() * 1.01 + 300, f"${b.get_height() / 1e3:.1f}K", ha="center", fontsize=8, color=INK)
    ax.set_xticks(x, labels); ax.set_ylabel("USD (backtest, 26.6K DAU)", color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8)
s.shapes.add_picture(chart_png("value", value_chart), Inches(0.6), Inches(1.7), width=Inches(6.6))
table(s, 7.4, 1.8, 5.3, [
    ["Out-of-time backtest", "Value"],
    ["Interventions / week (both)", "500"],
    ["Net retained uplift", f"+{N['net_uplift_pct']:.0f}%"],
    ["Incremental / year (Emberline)", fmt_k(N["incremental_annual"])],
    ["Incremental / year per 1M DAU", fmt_k(N["incremental_per_1m_dau"])],
    ["Players retained / year", f"{N['pp_players']:.0f} vs {N['sq_players']:.0f}*"],
], [3.3, 2.0], 13)
text(s, 7.4, 4.75, 5.4, 2.2, [
    "Assumptions (editable in Unity Catalog): save rate 25% while active / 10% after 3+ days quiet; $0.25 per intervention; a retained payer is worth 2× their 90-day spend.",
    "*Ranking by revenue keeps fewer, more valuable players. Near-free actions (guild invite, event push) cover the rest outside the 500 slots."], 11, MUTED)

# ---------------------------------------------------------------- 7. trust
s = slide("Trust, safety and governance built in", "Governance")
text(s, 0.6, 1.8, 12, 5, [
    "• Player PII (email, device ad-id, birth year) is masked at the source. The app, Genie and the model only ever see masked values.",
    "• Minors and players without consent can't get paid offers. Asserted on every daily run: 0 violations.",
    "• AI drafts can't mention prices to ineligible players. A guardrail blocks any that do, and a human approves every message.",
    "• Full lineage from raw file to app row in Unity Catalog. The model is versioned (@champion) with its validation metrics.",
    "• Data-quality expectations drop bad telemetry before it reaches a KPI (e.g. 2,414 negative-minute rows, 245 null player IDs)."], 17, INK2)

# ---------------------------------------------------------------- 8. proof
s = slide("Proof it runs: one daily job, end to end", "Execution")
tile(s, 0.6, 1.9, 3.0, f"{N['telemetry_rows'] / 1e6:.1f}M", "telemetry rows ingested and quality-checked")
tile(s, 3.75, 1.9, 3.0, f"{N['tickets'] / 1e3:.1f}K", "tickets classified by Claude, 0 errors")
tile(s, 6.9, 1.9, 3.0, f"{N['auc']:.3f}", f"out-of-time AUC (vs {N['auc_dsl']:.3f} for days-since-login)")
tile(s, 10.05, 1.9, 3.0, f"{N['lookup_ms']:.0f} ms", "Lakebase lookup per player at login")
text(s, 0.6, 4.2, 12, 2.5, [
    "Lakeflow pipeline → GenAI ticket insights → churn model (UC registry) → retention queue + AI messages → governance → Lakebase sync. One serverless Lakeflow Job.",
    "Every run's notebook output, SQL checks, Genie conversations and Lakebase queries are committed as readable text in the repo (evidence/).",
    f"Honest note: GenAI ticket features add little to fleet-wide accuracy (AUC {N['auc_noai']:.3f} without them). Their value is root cause → the right action, plus insight for product teams."], 14, INK2)

# ---------------------------------------------------------------- 9. plan
s = slide("30-60-90 days to prove it on real players", "The ask")
table(s, 0.6, 1.8, 12.1, [
    ["Days", "Milestone", "Success metric"],
    ["0–30", "Connect real telemetry, store receipts and helpdesk; retrain on Emberline history", "Backtest uplift reproduced on real data"],
    ["31–60", "A/B test: 10% holdout vs. PlayerPulse queue, 500 interventions / week", "Lift in 14-day payer retention and net revenue vs. holdout"],
    ["61–90", "All regions; game-backend lookup at login; weekly Genie readout for the GM", "Payer lapse rate back to Season 6 levels; cost per retained payer"],
], [1.2, 6.1, 4.8], 14)
text(s, 0.6, 4.4, 12, 1.5, ["Ask: sponsor a 4-week A/B test. LiveOps owns it; the data team and Databricks build it."], 20, BLUE, True)

# ---------------------------------------------------------------- 10. objections
s = slide("Questions we expect", "Appendix")
table(s, 0.6, 1.7, 12.1, [
    ["Question", "Answer"],
    ["Isn't this just a churn dashboard?", "A dashboard shows who left. This is a ranked daily action queue with the cause and a ready message."],
    ["Won't discounts cheapen our economy?", "Fixes and gifts come first, and offers are capped by eligibility and capacity. Every intervention's cost is in the math."],
    ["It's synthetic data. Is it real?", "The method carries over unchanged. The A/B holdout proves value on real players before rollout."],
    ["Why Lakebase, not the warehouse?", "Millisecond lookups at login plus OLTP writes for approvals, from one governed copy in Unity Catalog."],
    ["LLM cost at our ticket volume?", "Each ticket is classified once, incrementally, by a small model; messages only for the top 200."],
], [3.6, 8.5], 13)

out = os.path.join(HERE, "PlayerPulse_deck.pptx")
prs.save(out)
for f in os.listdir(HERE):
    if f.startswith("_") and f.endswith(".png"):
        os.remove(os.path.join(HERE, f))
print("wrote", out)
