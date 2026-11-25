# PlayerPulse: word-for-word demo script (Yoodli AI role-play)

**How to use:** read the plain text aloud. Lines in **[brackets]** are actions or pauses; don't read them. `/` means a short breath pause; `//` means a full pause (about 2 seconds).
Target: about 10 minutes at a calm pace (~140 words per minute). The 5-minute version is at the end.
Prep and URLs are in `docs/yoodli_demo_runbook.md`, section 0.

---

## PART 1: Opening and demo setup (about 1 min 45 s)

**[Camera on. No screen share yet. Smile. Speak slowly.]**

Hi, and thank you for making the time today. / I know you're in the middle of a busy season, so I'll keep this focused on what matters to you.

Before I show you anything, / I'd like to check that I understand your situation correctly. //

Here's what I've heard so far. / Since Season 7 launched with the energy rework, / the share of your active players who stop playing within two weeks has more than doubled. / It went from about one percent to about two and a half percent. / Your whales, your most valuable players, are leaving about sixty-six percent faster than in Season 6. / And then client version 7.2 introduced a crash on low-end Android phones, / which made things worse for a big part of your audience. //

Today, your LiveOps team runs a win-back rule. / Payers who haven't logged in for three days get a discount, / highest spenders first. / The problem is that by day three, most of those players are already gone. / And a discount doesn't fix a double charge, / or a crash, / or an energy wall. //

So let me ask you: / is that a fair picture of where you are today? //

**[Stop. Let the customer answer fully. Nod.]**

**[If they agree:]** Thank you, that's really helpful.
**[If they add something:]** That's a great point. / I'll make sure we come back to that.

And if we got this right, / what would a good outcome look like for you this quarter? //

**[Stop. Listen carefully. Write down their exact words, e.g. "protect whale revenue", "get churn back to Season 6 levels".]**

That makes sense. / So the priority is **[repeat their words exactly]**. / I'll keep that front and center.

Here's how I'd like to use the next ten minutes. / First, I'll show you the daily queue your LiveOps team would work from. / Second, I'll take one at-risk whale end to end, / from why they're leaving, / to the right fix, / to the message they receive. / Third, I'll show you how anyone on your team can ask questions in plain English. / And then I'll share the numbers, / and suggest a concrete next step. //

Does that work for you? / And do we still have about ten minutes? //

**[Wait for "yes".]**

---

## PART 2: TELL: what you're about to see (about 30 s)

Great. / Let me tell you what I'd like you to take away from this demo, / and then I'll show you. //

With the same five hundred interventions a week that your team already runs, / PlayerPulse finds your at-risk paying players while they're still playing, / up to two weeks before they leave. / It tells you *why* each one is at risk. / And it gives your team the right fix, / ready to approve in one click. //

When we tested it against your current rule, / it kept seventy-eight percent more revenue, / for the same effort. //

Let me show you how.

---

## PART 3: SHOW: the live demo (about 5 min 30 s)

### 3a. The command center (about 1 min)

**[Share your screen. Tab 1: the PlayerPulse app, "Retention command center" tab.]**

This is the PlayerPulse console. / It's what your LiveOps manager would open every morning. //

**[Point at the first KPI tile.]**

Today, we're scoring about forty-four thousand active players. //

**[Point at the second tile.]**

The model expects around five hundred of them to stop playing in the next two weeks. //

**[Point at the revenue-at-risk tile.]**

And this is the revenue at stake if we do nothing. //

**[Point at the bar chart on the left: "Revenue at risk by root-cause action".]**

Now, this is the part I want you to notice. / This chart groups that revenue by the *fix* each player needs. / And the biggest bar is not "send a discount". / It's "support escalation": / players with an unresolved payment problem. / Your current rule would send every one of them a coupon. //

**[Point at the priority queue table on the right.]**

Here's the queue itself. / It's ranked by revenue at risk, / not just by probability. / Because a whale with a forty percent chance of leaving / matters more to your business / than a brand-new player with a ninety percent chance on day two. //

Quick question for you: / is ranking by revenue the right priority for your team, / or would you also want to protect new players? //

**[Pause. Listen.]**

**[If they want new players too:]** That's easy to do. / The ranking is a setting, / so we can blend in a weight for new players, / and the free actions, like guild invites, already cover them.
**[If they agree with revenue:]** Good. / That's how we've set it up.

### 3b. One whale, end to end (about 2 min). This is the key moment

Let me show you one real example. //

**[Click the "Player detail & AI message" tab. In the dropdown, select "#3 P0031051 · whale · SUPPORT_ESCALATION".]**

This is player three in today's queue. //

**[Point at the 74% risk number.]**

They're a whale. / They've spent about fourteen hundred dollars in the last ninety days. / And the model gives them a seventy-four percent chance of leaving within two weeks. //

**[Point at "Why at risk".]**

Why? / The model shows two reasons. / They've stopped logging in, / and they have an unresolved payment issue. //

**[Point at the blue "Latest ticket" box. Read it slowly.]**

And here's what they actually wrote to your support team: / "Purchase failed, / but money taken from my card. / Not spending another cent." //

**[Pause for two seconds. Let it land.]**

Think about what happens today. / Your current rule would send this player a discount. / That's exactly the wrong move. / They don't want a coupon. / They want their money back. //

**[Point at "Next-best-action: SUPPORT_ESCALATION".]**

So PlayerPulse recommends a support escalation instead. //

**[Point at the message text box.]**

And the AI has already drafted the in-game message. / Let me read you the start: / **[Read the first sentence of the message aloud, e.g. "Greetings, Rift Commander! Our Support team has escalated your recent purchase issue."]** / It apologizes, / it confirms their items will be restored, / and there's no upsell. //

Your team stays in control. / They can edit the message, / or change the action, / before anything is sent. //

**[Leave Action and Channel as they are. Click "Approve intervention". Point at the green success message.]**

One click. / That approval is now stored in Lakebase, our operational database, / and your game server picks it up the next time this player logs in. / That lookup takes about three milliseconds, / so the player never notices any delay. //

### 3c. The guardrail: responsible monetization (about 45 s)

Now let me show you the safety net, / because I know player trust matters to you. //

**[In the dropdown, select "#6 P0049967".]**

This is another whale. / But this player has not consented to marketing. //

**[Point at the yellow banner.]**

You can see the warning here: / paid offers are blocked for this player. //

**[Change the Action dropdown to PERSONALISED_OFFER. Click "Approve intervention". Point at the red "Blocked by policy" error.]**

And if someone tries to send them an offer anyway, / the system refuses. //

The same rule applies to every player under eighteen. / Across all forty-four thousand players, / zero paid offers went to minors / or to players without consent. / And that's checked automatically, every single day. //

**[Change the Action back to the recommended one, so nothing is left in an error state.]**

### 3d. Ask anything with Genie (about 1 min)

So far, we've looked at individual players. / But your product team has bigger questions, / like: "Was it the patch?" //

**[Click the "Ask PlayerPulse (Genie)" tab, or switch to Tab 2. Type exactly:]**
`What was the crash rate by device tier before and after client v7.2?`

**[Press Enter. While it runs, say:]**

Normally that's a data request, / and an answer a few days later. / Here, anyone can just ask, in plain English. //

**[When the table appears, point at the low-tier row.]**

And there's the answer. / On low-end devices, / crashes went from about four and a half percent of sessions / to about twenty-six percent / after version 7.2. / Mid and high-end devices stayed flat. / So yes, / it was the patch, / and it hit a specific part of your audience. //

**[Click "Show SQL" for two seconds.]**

And for your data team, / the exact query is right here, / running on governed data / with no personal information exposed. //

**[If Genie takes more than 20 seconds, say: "While that's running, let me show you what's under the hood," do 3e, then come back.]**

### 3e. Under the hood (optional, about 45 s; only if the technical person asks, or if you're under 8 minutes)

**[Switch to Tab 3, the job run graph with 7 green tasks.]**

Very briefly, here's what runs behind the scenes. / It's one daily Databricks job. / Lakeflow brings in your game telemetry, store receipts and support tickets, / with quality checks that remove bad records. / The AI reads every ticket. / The model is retrained and versioned. / And the results are synced to Lakebase for the app and the game. //

**[Switch to Tab 5, the Lineage tab.]**

And Unity Catalog tracks the full lineage, / from the raw file / all the way to this app. / Player emails, device IDs and birth years are masked at the source, / so neither the model, / nor Genie, / nor the app ever sees them. //

---

## PART 4: TELL: reinforce the value (about 1 min 15 s)

**[Open the deck, slide 6, "For the GM / CFO".]**

So let me bring this back to what you told me matters: / **[repeat their words, e.g. "protecting your whale revenue"]**. //

We tested PlayerPulse on ten weeks of player data / that the model had never seen, / using the same five hundred interventions a week / that your team runs today. //

**[Point at the gray bar.]**

Your current rule reached sixty-eight percent of the revenue at risk. //

**[Point at the blue bar.]**

PlayerPulse reached eighty-seven percent. / Which means you're reaching the players who actually leave, / not the ones who would have stayed anyway. //

**[Point at the second pair of bars.]**

After subtracting the cost of every gift and every discount, / that's seventy-eight percent more revenue kept. / For a game of your size, / that's about thirty-seven thousand dollars a year. / And it scales: / roughly one point four million dollars a year / for every million daily players. //

And you get that / without a single paid offer to a minor, / and with your team approving every message. //

I also want to be upfront about one trade-off. / Because we rank by revenue, / PlayerPulse keeps slightly fewer players overall than your current rule, / about two hundred and fifty-six a year versus three hundred. / It keeps the *valuable* ones. / That's why the free actions, / like guild invites and event reminders, / cover the rest of your players at almost no cost. //

---

## PART 5: Close and next steps (about 1 min)

**[Switch to deck slide 9, "30-60-90 days".]**

So, here's what I'd suggest as a next step. //

A four-week A/B test. / We hold back ten percent of your players as a control group, / and PlayerPulse runs your five hundred weekly interventions for everyone else. / We measure two things: / payer retention, / and net revenue. //

In the first month, / we connect your real telemetry, / store receipts / and helpdesk data, / and retrain the model on your history. / Then we run the test. / And if the results hold up, / you roll it out to every region before Season 9. //

To get started, / I need three things from you: / a LiveOps owner for the test, / read access to those three data sources, / and thirty minutes with your data lead next week. //

Could we book that session now? / Would Tuesday or Wednesday work better for you? //

**[Stop talking. Wait for the answer. Don't fill the silence.]**

**[If yes:]** Perfect. / I'll send the invite today, with a one-page plan, / so your data lead can come prepared. / Thank you. This was a great conversation.
**[If they hesitate:]** That's completely fair. / What would you need to see / to feel comfortable starting the test? // **[Listen, address it, then ask again for a date.]**

---

## PART 6: Objection answers, read-aloud versions

### From the business stakeholder

**"We already have a churn dashboard."**
That's a great starting point. / But a dashboard tells you who already left. / PlayerPulse gives your team a daily to-do list / of who is *about* to leave, / why, / and the fix, / ready to approve. / It turns insight into action.

**"Won't discounts cheapen our game economy?"**
I completely agree that's a risk, / and that's exactly why discounts come last. / Fixes and free gifts come first. / Offers only go to eligible players, / within your weekly limit. / And the value numbers I showed you already subtract the cost of every gift and discount.

**"How do I know the one point four million is real?"**
You shouldn't take it on faith. / Those numbers come from a backtest on simulated data. / That's exactly why I'm proposing an A/B test with a holdout group on your real players. / You'll see the real number before you commit to a rollout.

**"My team doesn't have time for another tool."**
I hear that a lot. / This actually replaces the manual win-back list. / It's the same five hundred actions a week, / but each one is one click, / and the message is already written.

**"What about player trust, and minors?"**
That's built in, not bolted on. / Minors and players without marketing consent can't receive paid offers. / It's enforced in the data and checked every day, / with zero violations. / And a person on your team approves every single message.

**"What does this cost?"**
It runs on serverless, so you pay for what you use. / The AI reads each ticket only once, with a small, efficient model, / and it only drafts messages for the top two hundred players. / We'll size the exact cost during the pilot.

### From the technical stakeholder

**"It's synthetic data, so the accuracy number is meaningless."**
You're right about the absolute number. / What carries over is the method. / Features are built point-in-time, so there's no leakage. / It's tested on weeks the model never saw. / And it's compared against your current rule at the same budget. / The data simulator is in the repository, / so your team can audit every assumption.

**"Why Lakebase and not just the data warehouse?"**
Because the app needs two things a warehouse isn't designed for. / First, millisecond lookups when a player logs in. / Second, the app writing approvals back. / Lakebase gives us both, / and it's synced from one governed table in Unity Catalog, / so there's a single source of truth.

**"Does the AI actually make the model more accurate?"**
Honestly, / not the overall accuracy. / It's about point eight eight six with or without it. / Where it really matters is the *action*. / It's what tells you this whale needs a refund, not a coupon. / And it gives your product team a live view of why players are leaving.

**"How do you handle personal data?"**
Personal data is masked at the source, / in the pipeline definition itself. / So the model, / Genie, / and the app / never see an email, / a device ID, / or a birth year.

**"Can we use our own model?"**
Yes. / The model sits behind a named version in Unity Catalog. / You can swap in your own / without changing the app or the pipeline.

**"What if the AI makes mistakes?"**
We classified over twenty-seven thousand tickets with zero errors. / And every message passes an automatic policy check, / plus human approval, / before it reaches a player.

---

## PART 7: 5-minute version (if the customer is short on time)

**[Setup, 45 s]**
Thanks for your time. / Since Season 7, the share of your players who stop playing within two weeks has more than doubled, / and your whales are leaving sixty-six percent faster. / Your current win-back rule reaches them on day three, with a discount, / when most are already gone. / Is that fair? // **[Listen.]** / In the next five minutes, I'll show you one at-risk whale end to end, / one plain-English question, / and the business result.

**[Tell, 15 s]**
The takeaway: / same five hundred weekly actions, / earlier, / with the right fix, / and seventy-eight percent more revenue kept.

**[Show, 2 min 45 s]**
Do 3b (whale P0031051, read the ticket, approve) and 3d (Genie crash question), using the same words as above.

**[Value and close, 1 min]**
Your current rule reached sixty-eight percent of the revenue at risk. / PlayerPulse reached eighty-seven percent. / That's seventy-eight percent more revenue kept, / about one point four million dollars a year per million daily players, / with zero offers to minors. / My suggestion is a four-week A/B test with a ten percent holdout. / Could we book thirty minutes with your data lead next week? / Does Tuesday or Wednesday work?
