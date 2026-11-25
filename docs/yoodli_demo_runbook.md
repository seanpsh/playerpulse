# PlayerPulse: Yoodli AI role-play demo runbook

**Goal:** a 10-minute, audience-focused demo that scores on **demo setup**, **tell-show-tell**, **value communication** and **professional delivery**, and closes with a concrete next step.
**Audience (AI customer):** the business stakeholder (VP LiveOps / GM of the title) and the technical stakeholder (Head of Data / Platform). Speak to the business first; give the technical person proof points when asked.

---

## 0. Before you start (5 minutes of prep)

Open these tabs **in this order** and log in to each one, so the demo has no login screens:

| Tab | URL | Pre-set state |
|---|---|---|
| 1. App: PlayerPulse | https://playerpulse-7474659338788077.aws.databricksapps.com | "Retention command center" tab open |
| 2. Genie space | https://fevm-aws-demo.cloud.databricks.com/genie/rooms/01f1e8deefe41e469de20a4ea139c622 | empty conversation |
| 3. Job run (end to end) | https://fevm-aws-demo.cloud.databricks.com/jobs/656922230388324/runs/931556335206949 | graph view, all 7 tasks green |
| 4. Lakeflow pipeline | https://fevm-aws-demo.cloud.databricks.com/pipelines/ec794c3e-8ec2-415e-8b4e-6fe6d1f20611 | pipeline graph |
| 5. Catalog: retention queue | Catalog Explorer → `aws_demo_catalog` → `playerpulse_serving` → `player_retention_queue` | **Lineage** tab |
| 6. Deck PDF | `deck/PlayerPulse_deck.pdf` | slides 1, 6, 9 are the ones you'll use |

Checklist:
- [ ] The app loads, and the command center shows KPI tiles (if it's cold, refresh once, 10–20 s).
- [ ] Ask Genie one warm-up question, then **start a new conversation** so the demo question runs on a warm warehouse.
- [ ] Do a quiet-room mic check. Close notifications. Share only the browser window.
- [ ] Have these numbers in your head (or on a sticky note):
  - Season 7 lapse ×2.4 · whales +66% · low-tier crashes 4.5% → 26.5%
  - 87% vs 68% · +78% · $1.4M per 1M DAU · 0 offers to minors · 3 ms
  - next step: 4-week A/B test, 10% holdout

**Pacing rule:** about 140 words a minute. Pause after every number. Ask a question at least every 2–3 minutes.

---

## 1. Demo setup: set the stage (about 1.5 min)

> **Rubric:** set the stage before showing the solution, personalize, and agree the agenda and time.

**ACTION:** camera on, deck slide 1 (or no screen share yet). Smile and slow down.

**SAY:**
> "Thanks for making the time. Before I show anything, let me check I've got your situation right.
> Since Season 7 launched with the energy rework, your 14-day player churn has more than doubled. Whales are up about 66%. Then the 7.2 client added a crash on low-end Android phones.
> Today, LiveOps sends a discount to payers who've been quiet for three days. By then most of them are gone, and a discount doesn't fix a double charge or a crash.
> Is that a fair picture? *(pause, let them answer)* What would a good outcome look like for you this quarter?"

**LISTEN, then personalize.** Repeat their words back, e.g. "So protecting whale revenue before Season 9 is the priority." Use that phrase again in the close.

**SAY (agenda + time check):**
> "Here's my plan for the next ten minutes. First, the daily queue your LiveOps team would work from. Second, one at-risk whale end to end, from the cause to the fix to the message. Third, how anyone can ask questions in plain English. Then the numbers and a next step. Does that work, and do we still have ten minutes?"

---

## 2. TELL: what you're about to see (about 30 s)

> **Rubric:** say what you'll show before you show it.

**SAY:**
> "What I want you to take away is this: with the same 500 interventions a week you already run, PlayerPulse finds your at-risk paying players about two weeks earlier, tells you why they're leaving, and gives your team the right fix in one click. In the backtest, that kept 78% more revenue. Let me show you."

---

## 3. SHOW: the demo (about 5–6 min)

### 3a. Command center: the daily queue (about 1 min)

**ACTION:** Tab 1, **"📊 Retention command center"**. Point at the KPI tiles from left to right.

**SAY:**
> "This is what your LiveOps manager opens each morning. We're scoring about 44,000 active players today. The model expects around 500 to lapse in the next two weeks, and this tile is the revenue at stake.
> On the left is *why* they're at risk, grouped by the fix: support escalations, crash fixes, energy gifts, offers. Notice that the biggest bar isn't 'send a discount'. It's 'fix the payment problem'."

**ACTION:** In the queue table, leave the filters on whale/dolphin/minnow and High/Medium. Scroll slightly so the top 5 rows show.

**SAY:**
> "The queue is ranked by revenue at risk, not just probability. A 40%-risk whale matters more to you than a 90%-risk tourist on day two."

**ASK:** "Is ranking by revenue the right priority for your team, or would you weight new players too?" *(Answer: "It's a config choice. We can blend in a retention weight.")*

### 3b. One whale, end to end (about 2 min). This is the money moment.

**ACTION:** Click the **"🧑‍🚀 Player detail & AI message"** tab. In the dropdown, pick **#3 P0031051 · whale · SUPPORT_ESCALATION**.

**SAY (point at each element as you name it):**
> "Here's a real example. A whale who spent about $1,400 in the last 90 days, with a 74% chance of leaving in two weeks.
> *Why?* The model says they've stopped logging in, and they have an unresolved payment issue.
> And here's their actual ticket: 'Purchase failed but money taken from my card. Not spending another cent.'
> Today, your rule would send this player a discount. That's exactly wrong. They don't want a coupon, they want their money back.
> So PlayerPulse recommends a support escalation, and Claude has drafted the in-game message: an apology, confirmation that the items will be restored, and no upsell."

**ACTION:** Read the first sentence of the AI message aloud. Leave Action = SUPPORT_ESCALATION and Channel = in_game_mail. Click **"Approve intervention"** and point at the green success banner.

**SAY:**
> "One click. That's written to Lakebase, the operational database, and the game server picks it up when the player next logs in. That lookup takes about three milliseconds, so it's invisible to the player."

### 3c. Guardrail: responsible monetization (about 45 s)

**ACTION:** In the dropdown, pick **#6 P0049967** (whale, no marketing consent). Point at the yellow **"Responsible-monetization policy: paid offers blocked"** banner. Change Action to **PERSONALISED_OFFER** and click **Approve**, then point at the red **"Blocked by policy"** error.

**SAY:**
> "Here's the safety net. This player hasn't consented to marketing, so paid offers are blocked. You can see the app refuse it. The same rule covers every minor: across 44,000 players, zero paid offers went to minors or players without consent, and that's checked automatically every day. The AI draft for this player also offers an event, never a discount."

**ACTION:** Set the Action back to the recommended one. Don't leave a blocked state on screen.

### 3d. Ask anything: Genie (about 1 min)

**ACTION:** Tab 2 (Genie), or the app's **"💬 Ask PlayerPulse (Genie)"** tab. Type exactly:
`What was the crash rate by device tier before and after client v7.2?`

**SAY (while it runs):**
> "Your product team keeps asking 'was it the patch?'. Instead of filing a data request, they just ask."

**ACTION:** When the table appears, point at the low-tier row (about 4.5% → 26.5%). Click "Show SQL" briefly for the technical stakeholder.

**SAY:**
> "There it is. Low-tier devices went from about 4.5% to 26% crashes per session after 7.2, while mid and high tier stayed flat. It's governed data with no PII, and the SQL is right there if your data team wants to check it."

*(If Genie is slow for more than 20 s, say "While that runs…" and move to 3e, then come back.)*

### 3e. Under the hood: only if the technical stakeholder asks, or 45 s if time allows

**ACTION:** Tab 3 (job run graph: 7 green tasks) → Tab 5 (Lineage tab).

**SAY:**
> "Under the hood it's one daily Databricks job. Lakeflow ingests telemetry, receipts and tickets with quality checks. Claude reads every ticket. The model is versioned in Unity Catalog. The queue syncs to Lakebase. And Unity Catalog shows the full lineage from raw file to this app, with player PII masked at the source."

---

## 4. TELL: reinforce the value (about 1 min)

> **Rubric:** tie benefits to the audience's needs, using their words from the setup.

**ACTION:** Deck **slide 6** (value chart).

**SAY:**
> "So, back to what you said matters, *[their words, e.g. protecting whale revenue]*. We backtested this on ten weeks of data the model had never seen, with the same 500 interventions a week you run today.
> Your current rule reached 68% of the revenue at risk. PlayerPulse reached 87%.
> Net of the cost of every gift and discount, that's 78% more revenue kept. For a title this size that's about $37,000 a year, or roughly $1.4 million per million daily players.
> And you get it without discounting to minors, with your team approving every message."

**Be upfront about the trade-off (it builds trust):**
> "One honest trade-off: because we rank by revenue, it keeps slightly fewer total players than today's rule. That's why free actions like guild invites and event pushes cover the long tail."

---

## 5. Close: actionable next steps (about 1 min)

**ACTION:** Deck **slide 9** (30-60-90 plan).

**SAY:**
> "Here's what I'd suggest. A four-week A/B test: 10% of players as a holdout, PlayerPulse running your 500 weekly interventions for the rest, measured on payer retention and net revenue.
> Weeks one to four, we connect your real telemetry, receipts and helpdesk and retrain. Then the test. If it holds up, we roll out to all regions before Season 9.
> To start, I need three things: a LiveOps owner, read access to those three sources, and 30 minutes with your data lead next week.
> Could we book that session now? Does Tuesday or Wednesday work?"

**Stop talking and wait for the answer.**

---

## 6. Objection handling: one-liners

### Business stakeholder (VP LiveOps / GM / CFO)
| They say | You say |
|---|---|
| "We already have a churn dashboard." | "A dashboard tells you who left. This is a daily to-do list of who's *about* to leave, why, and the fix, ready to approve." |
| "Discounts will cheapen our economy." | "Agreed, which is why fixes and gifts come first. Offers are the last resort and only for eligible players. The value math already subtracts every gift's cost." |
| "How do I know the $1.4M is real?" | "You shouldn't take it on faith. It's a backtest on synthetic data, and that's exactly why the next step is a 10% holdout A/B test on your real players." |
| "My team doesn't have time for another tool." | "It replaces the manual win-back list. Same 500 actions a week, one click each, and the drafts are already written." |
| "What about player trust and minors?" | "Minors and players without consent can't receive paid offers. It's enforced in the data and checked daily, with zero violations, and a human approves every message." |
| "What does it cost?" | "Serverless, pay per use. Each ticket is classified once by a small model, and messages are only drafted for the top 200. We'll size it in the pilot." |

### Technical stakeholder (Head of Data / Platform)
| They say | You say |
|---|---|
| "Synthetic data means the AUC is meaningless." | "Absolutely, for the absolute number. What carries over is the method: point-in-time features, an out-of-time test, and a backtest against your current rule. The simulator is in the repo, so you can audit it." |
| "Why Lakebase, not just the warehouse?" | "Two things a warehouse isn't built for: millisecond lookups at game login, and the app writing approvals. Lakebase gives both, synced from one governed table in Unity Catalog." |
| "Does the GenAI actually improve the model?" | "Honestly, not the overall accuracy: 0.886 with or without it. Its value is the *action*. It tells you this whale needs a refund, not a coupon, and it shows product teams why players leave." |
| "How do you handle PII?" | "Masked at the source, in the pipeline definition, so the model, Genie and the app never see email, device ID or birth year." |
| "Can we bring our own model or features?" | "Yes. The model sits behind a Unity Catalog alias, so you can swap it without touching the app or the pipeline." |
| "LLM output errors?" | "27,000 tickets classified with zero parse errors. Messages pass an automatic guardrail plus human approval." |

---

## 7. Delivery tips for the Yoodli score
- **Open strong, close strong:** the first and last 30 seconds are scripted, so say them almost verbatim.
- **Fewer filler words:** pause instead of saying "um". Rehearse 3b twice; it's the moment that matters most.
- **Signpost:** "First…", "Now…", "Here's why that matters…", "To recap…".
- **One number at a time,** each followed by "which means…" (e.g. "87% vs 68%, which means you're reaching the revenue that actually leaves").
- **Use "you / your team / your players",** not "we built".
- **Ask, then pause:** at least three questions (setup, ranking choice, close).
- **Watch the time:** if you're over 8 minutes before section 4, skip 3e.
- **If something breaks:** "Let me show you the captured run instead", then open `evidence/genie_conversations.md` or deck slide 8. Stay calm and keep narrating the value.

## 8. 5-minute version (if the AI customer is short on time)
Setup (45 s: problem + one question) → Tell (15 s) → 3b only (2 min: whale P0031051, approve) → Genie question (45 s) → Value + close (1 min: 87% vs 68%, +78%, A/B test ask).
