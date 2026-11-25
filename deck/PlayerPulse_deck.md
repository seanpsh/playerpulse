# PlayerPulse: keep your best players before they quit
### Emberforge Studios · Emberline: Rift Tactics · Proposal for the GM, CFO and VP LiveOps
*(Synthetic data. Numbers marked ⏳ come from the backtest in the Databricks workspace.)*

---

## Slide 1: The outcome

**Same LiveOps budget. ⏳% more paying-player revenue retained. Zero paid offers to minors.**

- About **$⏳ per year** of incremental net revenue for Emberline (25K DAU), or about **$⏳ per 1M DAU**
- **⏳ more players retained per year**, reached *before* they go quiet
- **Live within weeks:** a daily, governed action queue in the LiveOps team's hands, plus answers in plain English

---

## Slide 2: What changed in Season 7

- The energy rework (June 2), then the client v7.2 crash on low-tier Android (Aug 12 to Sep 24)
- **14-day lapse rate:** Season 6 ⏳ → Season 7 ⏳; **whales:** ⏳ → ⏳
- Revenue at risk from lapsing payers: **$⏳ per week** at peak
- About 27K support tickets per season, e.g. "charged twice for gem pack… not spending another cent". Nobody reads them at scale.

---

## Slide 3: Why today's win-back program misses

| Today: "payers quiet 3+ days get a discount" | Impact |
|---|---|
| **Late:** acts on day 3 | Win-back works about 2.5x better while players are still playing |
| **Same remedy for every problem** | A discount doesn't fix a double charge or a crash |
| **Can't see what players say** | Quit-intent and billing tickets are 2.7x stronger churn signals, and today they're ignored |
| **No policy guardrail** | Risk of offers to minors or players without consent |

---

## Slide 4: PlayerPulse in one picture

**Raw game data → governed lakehouse → AI that predicts and explains → action in the LiveOps console and the game**

1. Telemetry, store receipts, tickets, LiveOps calendar → **Lakeflow** (daily, quality-checked)
2. **Unity Catalog:** player PII masked, minors and consent enforced, lineage and an audit trail
3. **GenAI** reads every ticket → root cause, sentiment, quit intent
4. **ML** predicts who lapses in the next 14 days and how much revenue is at stake
5. **Fix-first next-best-action** + an AI-drafted, policy-checked message
6. **Lakebase** serves it to the LiveOps app and the game backend (ms at login); approvals are written back
7. **Genie:** "How did whale churn change from Season 6 to 7?", answered in seconds

---

## Slide 5: For the VP LiveOps, the daily workflow

- **Morning queue:** top players by revenue at risk, each with *why* (e.g. "Unresolved payment issue; play frequency dropping") and *what to do*
- **One click:** review the Claude-drafted in-game mail, approve, and it's delivered at the player's next login
- **Fix-first actions:** support escalation → tech fix + apology gift → energy refill → guild invite → personalized offer (only if eligible)
- **Ask anything:** "What are high-risk payers complaining about?" or "Crash rate by device tier after v7.2?"

---

## Slide 6: For the GM / CFO, the value case (backtest on 10 out-of-time weeks)

| | Status quo | PlayerPulse |
|---|---|---|
| Interventions per week | 500 | 500 |
| At-risk payer revenue reached | ⏳ | ⏳ |
| Revenue retained, net of offer cost (10 wks) | $⏳ | $⏳ |
| Annualized incremental net revenue | | **$⏳** |
| Per 1M DAU (scaled) | | **$⏳** |

Assumptions (editable in Unity Catalog):
- save rate: 25% for players contacted while still active, 10% after 3+ days quiet
- cost per intervention: $0.25
- value of a retained payer: 2× their 90-day spend

**Upside not counted:** fewer refunds and chargebacks, faster bug triage, lower paid-UA spend to replace churned players.

---

## Slide 7: Trust, safety and governance

- PII (email, device ad-id, birth year) is **masked at the source**. The app, Genie and the model never see it.
- **Minors and players without consent never get paid offers.** This is checked automatically on every daily run (violations: **0**).
- AI drafts can't mention prices to ineligible players, and a guardrail blocks any that do. **A human approves every message.**
- Full lineage from raw file to app row. The model is versioned in Unity Catalog with its validation metrics.

---

## Slide 8: Proof it runs

- One Lakeflow Job runs the entire flow daily on serverless
- ⏳M telemetry rows, ⏳K tickets classified, ⏳K active players scored
- Lakebase lookup at login: ⏳ ms
- Model accuracy: out-of-time AUC ⏳ (vs. ⏳ for "days since last login")
- Every run's output is committed as readable text in the repo (`evidence/`)

---

## Slide 9: The 30-60-90 day plan

| Days | Milestone | Success metric |
|---|---|---|
| 0–30 | Connect real telemetry, receipts and helpdesk; retrain on Emberline history | Backtest uplift confirmed on real data |
| 31–60 | **A/B test:** 10% holdout vs. PlayerPulse queue, 500/week | Lift in 14-day payer retention and net revenue vs. holdout |
| 61–90 | Roll out to all regions; game-backend offer lookup at login; weekly Genie readout to the GM | ⏳% fewer payer lapses; cost per retained payer |

**Ask:** sponsor a 4-week A/B test, with LiveOps as the owner and the data team plus Databricks as builders.

---

## Appendix: likely questions

- **"Isn't this just a churn dashboard?"** No. A dashboard shows who left. PlayerPulse is a ranked daily action queue with the root cause and a ready message.
- **"Won't discounts cheapen the economy?"** Fixes and gifts come first, and offers are capped by eligibility and capacity. Every intervention's cost is in the math.
- **"Synthetic data?"** Yes, for this prototype. The method carries over unchanged, and the A/B test proves value on real players.
- **"Cost?"** Serverless and incremental. Each ticket is classified once by a small model, and messages are generated only for the top 200.
