"""
PlayerPulse - LiveOps retention console (Databricks App)
Emberforge Studios · "Emberline: Rift Tactics" (synthetic data)

Reads the player retention queue from Lakebase Postgres (synced from Unity Catalog), lets a LiveOps
manager review the AI-drafted message and approve an intervention (written back to Lakebase, where
the game backend picks it up at the player's next login), and embeds a Genie space for
natural-language questions over the governed gold tables.
"""
import os
import time

import pandas as pd
import psycopg
import streamlit as st
from databricks.sdk import WorkspaceClient

st.set_page_config(page_title="PlayerPulse · Emberforge LiveOps", page_icon="🎮", layout="wide")

GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID", "")
Q = os.getenv("QUEUE_TABLE", "playerpulse_serving.player_retention_queue_synced")
w = WorkspaceClient()

ACTIONS = ["SUPPORT_ESCALATION", "SAFETY_REVIEW", "TECH_FIX_AND_APOLOGY_GIFT", "ENERGY_REFILL_GIFT",
           "GUILD_MATCH_INVITE", "PERSONALISED_OFFER", "EVENT_REENGAGEMENT_PUSH"]


# ----------------------------------------------------------------------------- Lakebase
class Lakebase:
    """Postgres connection authenticated with the app service principal's OAuth token (refreshed < 1h)."""

    def __init__(self):
        self._conn, self._born = None, 0.0

    def conn(self):
        if self._conn is None or self._conn.closed or time.time() - self._born > 45 * 60:
            if self._conn is not None and not self._conn.closed:
                self._conn.close()
            self._conn = psycopg.connect(
                host=os.environ["PGHOST"], port=int(os.getenv("PGPORT", "5432")), dbname=os.environ["PGDATABASE"],
                user=os.environ["PGUSER"], password=w.config.oauth_token().access_token,
                sslmode=os.getenv("PGSSLMODE", "require"), autocommit=True)
            self._born = time.time()
        return self._conn

    def df(self, sql, params=None):
        with self.conn().cursor() as cur:
            cur.execute(sql, params)
            return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])

    def execute(self, sql, params=None):
        with self.conn().cursor() as cur:
            cur.execute(sql, params)


@st.cache_resource
def lakebase():
    lb = Lakebase()
    lb.execute("CREATE SCHEMA IF NOT EXISTS ops")
    lb.execute("""
        CREATE TABLE IF NOT EXISTS ops.interventions (
          intervention_id  BIGSERIAL PRIMARY KEY,
          player_id        TEXT NOT NULL,
          action           TEXT NOT NULL,
          channel          TEXT NOT NULL,
          message          TEXT,
          churn_prob_14d   DOUBLE PRECISION,
          value_at_risk_usd DOUBLE PRECISION,
          status           TEXT NOT NULL DEFAULT 'APPROVED',
          approved_by      TEXT,
          created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )""")
    lb.execute("CREATE INDEX IF NOT EXISTS interventions_player_idx ON ops.interventions (player_id)")
    return lb


def current_user():
    try:
        return st.context.headers.get("X-Forwarded-Email") or "liveops@emberforge.example"
    except Exception:
        return "liveops@emberforge.example"


@st.cache_data(ttl=120)
def load_queue():
    return lakebase().df(f"""
        SELECT player_id, platform, device_tier, region, age_band, is_minor, marketing_opt_in, tenure_days,
               days_since_last_play, lifecycle_stage, active_days_7d, active_days_28d, minutes_7d, crashes_7d,
               energy_walls_7d, in_guild, level, client_version, lifetime_spend_usd, spend_90d_usd, payer_tier,
               tickets_28d, last_ticket_category, last_ticket_summary, last_ticket_message, last_ticket_churn_intent,
               churn_prob_14d, value_at_risk_usd, risk_tier, top_drivers, next_best_action, paid_offer_eligible,
               priority_rank, ai_message, ai_rationale, model_version, as_of_date, refreshed_at
        FROM {Q}""")


def interventions():
    return lakebase().df("""SELECT intervention_id, player_id, action, channel, status, round(churn_prob_14d::numeric, 3) AS p14,
                                   round(value_at_risk_usd::numeric, 2) AS value_at_risk_usd, message, approved_by, created_at, updated_at
                            FROM ops.interventions ORDER BY intervention_id DESC""")


# ----------------------------------------------------------------------------- Genie
def ask_genie(question, conversation_id=None):
    api, base = w.api_client, f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}"
    if conversation_id:
        r = api.do("POST", f"{base}/conversations/{conversation_id}/messages", body={"content": question})
        msg_id = r["id"]
    else:
        r = api.do("POST", f"{base}/start-conversation", body={"content": question})
        conversation_id, msg_id = r["conversation_id"], r["message_id"]
    for _ in range(90):
        m = api.do("GET", f"{base}/conversations/{conversation_id}/messages/{msg_id}")
        if m["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(2)
    text, sql, table = None, None, None
    for a in m.get("attachments") or []:
        if "text" in a:
            text = a["text"].get("content")
        if "query" in a:
            sql = a["query"].get("query")
            text = text or a["query"].get("description")
            res = api.do("GET", f"{base}/conversations/{conversation_id}/messages/{msg_id}/attachments/{a['attachment_id']}/query-result")
            sr = res.get("statement_response", {})
            cols = [c["name"] for c in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
            rows = sr.get("result", {}).get("data_array", []) or []
            table = pd.DataFrame(rows, columns=cols) if cols else None
    if m["status"] != "COMPLETED" and not text:
        text = f"Genie status: {m['status']} {m.get('error', '')}"
    return conversation_id, text, sql, table


# ----------------------------------------------------------------------------- UI
st.markdown("## 🎮 PlayerPulse — LiveOps Retention Console")
st.caption("Emberforge Studios · Emberline: Rift Tactics · predict lapsing players 14 days ahead, fix the root cause, retain revenue · synthetic data")

try:
    df = load_queue()
except Exception as e:
    st.error(f"Could not read Lakebase: {e}")
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["📊 Retention command center", "🧑‍🚀 Player detail & AI message", "✅ Interventions", "💬 Ask PlayerPulse (Genie)"])

with tab1:
    hi = df[df.risk_tier == "HIGH"]
    payers_hi = hi[hi.spend_90d_usd > 0]
    c = st.columns(5)
    c[0].metric("Active players scored", f"{len(df):,}")
    c[1].metric("Expected lapsers (next 14 d)", f"{df.churn_prob_14d.sum():,.0f}")
    c[2].metric("Revenue at risk (90-d spend × P)", f"${df.value_at_risk_usd.sum():,.0f}")
    c[3].metric("High-risk payers", f"{len(payers_hi):,}", f"{int((payers_hi.payer_tier == 'whale').sum())} whales", delta_color="off")
    c[4].metric("Already quiet 3+ days (status-quo list)", f"{int((df.days_since_last_play >= 3).sum()):,}")
    st.caption(f"Model v{df.model_version.iloc[0]} · scores as of {df.as_of_date.max()} · served from Lakebase (refreshed {df.refreshed_at.max()})")

    l, r = st.columns([2, 3])
    with l:
        st.markdown("**Revenue at risk by root-cause action**")
        st.bar_chart(df.groupby("next_best_action").value_at_risk_usd.sum().sort_values(ascending=False), horizontal=True, height=260)
        st.markdown("**Expected lapsers by platform × device tier**")
        st.bar_chart(df.assign(seg=df.platform + " / " + df.device_tier).groupby("seg").churn_prob_14d.sum().sort_values(ascending=False),
                     horizontal=True, height=220)
    with r:
        f1, f2, f3 = st.columns(3)
        tiers = f1.multiselect("Payer tier", ["whale", "dolphin", "minnow", "non_payer"], default=["whale", "dolphin", "minnow"])
        risks = f2.multiselect("Risk tier", ["HIGH", "MEDIUM", "LOW"], default=["HIGH", "MEDIUM"])
        acts = f3.multiselect("Next-best-action", ACTIONS, default=ACTIONS)
        view = df[df.payer_tier.isin(tiers) & df.risk_tier.isin(risks) & df.next_best_action.isin(acts)].sort_values("priority_rank")
        st.markdown(f"#### Priority queue — {len(view):,} players")
        st.dataframe(
            view[["priority_rank", "player_id", "payer_tier", "risk_tier", "churn_prob_14d", "value_at_risk_usd", "next_best_action",
                  "top_drivers", "last_ticket_summary", "days_since_last_play", "platform", "region", "paid_offer_eligible"]].head(500),
            hide_index=True, use_container_width=True, height=520,
            column_config={"churn_prob_14d": st.column_config.ProgressColumn("P(lapse 14d)", format="%.2f", min_value=0, max_value=1),
                           "value_at_risk_usd": st.column_config.NumberColumn("Revenue at risk", format="$%.2f")})

with tab2:
    top = df.sort_values("priority_rank").set_index("player_id")
    pid = st.selectbox("Player (top 500 by revenue at risk)", top.index[:500].tolist(),
                       format_func=lambda p: f"#{int(top.loc[p, 'priority_rank'])}  {p}  ·  {top.loc[p, 'payer_tier']}  ·  {top.loc[p, 'next_best_action']}")
    r = top.loc[pid]
    a, b = st.columns([2, 3])
    with a:
        st.metric("P(lapse in 14 days)", f"{r.churn_prob_14d:.0%}", f"{r.risk_tier} risk", delta_color="off")
        st.write(f"**{r.payer_tier.title()}** · 90-day spend **${r.spend_90d_usd:,.2f}** · lifetime ${r.lifetime_spend_usd:,.2f}")
        st.write(f"{r.platform} ({r.device_tier}-tier) · {r.region} · client {r.client_version} · level {r.level} · {'in a guild' if r.in_guild else 'no guild'}")
        st.write(f"Played {r.active_days_7d}/7 days this week vs {r.active_days_28d}/28 · last seen {r.days_since_last_play} days ago")
        st.write(f"Crashes 7d: **{r.crashes_7d}** · energy walls 7d: **{r.energy_walls_7d}**")
        st.write("**Why at risk:** " + (r.top_drivers or "—"))
        if isinstance(r.last_ticket_message, str):
            st.info(f"**Latest ticket** ({r.last_ticket_category}{', churn intent' if r.last_ticket_churn_intent else ''}): _{r.last_ticket_message}_")
        if not r.paid_offer_eligible:
            st.warning("Responsible-monetization policy: paid offers blocked (minor or no marketing consent).")
    with b:
        st.markdown(f"##### Next-best-action: `{r.next_best_action}`")
        st.caption("AI draft (Claude) — review before sending. " + (r.ai_rationale or ""))
        with st.form("approve"):
            action = st.selectbox("Action", ACTIONS, index=ACTIONS.index(r.next_best_action))
            channel = st.selectbox("Channel", ["in_game_mail", "push_notification", "support_ticket_reply", "email"])
            msg = st.text_area("Message to player", r.ai_message if isinstance(r.ai_message, str) else "", height=140)
            ok = st.form_submit_button("Approve intervention", type="primary")
            if ok:
                if action == "PERSONALISED_OFFER" and not r.paid_offer_eligible:
                    st.error("Blocked by policy: this player cannot receive paid offers.")
                else:
                    lakebase().execute(
                        """INSERT INTO ops.interventions (player_id, action, channel, message, churn_prob_14d, value_at_risk_usd, approved_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        (pid, action, channel, msg, float(r.churn_prob_14d), float(r.value_at_risk_usd), current_user()))
                    st.success(f"Approved {action} for {pid} — written to Lakebase ops.interventions; delivered at next login.")

with tab3:
    iv = interventions()
    k = st.columns(4)
    k[0].metric("Approved", int((iv.status == "APPROVED").sum()) if len(iv) else 0)
    k[1].metric("Delivered", int((iv.status == "DELIVERED").sum()) if len(iv) else 0)
    k[2].metric("Revenue at risk covered", f"${iv.value_at_risk_usd.astype(float).sum():,.0f}" if len(iv) else "$0")
    hp = set(df[(df.risk_tier == "HIGH") & (df.spend_90d_usd > 0)].player_id)
    k[3].metric("High-risk payers not yet contacted", len(hp - set(iv.player_id)) if len(iv) else len(hp))
    st.dataframe(iv, hide_index=True, use_container_width=True)
    if len(iv):
        with st.form("upd"):
            u1, u2, u3 = st.columns(3)
            iid = u1.selectbox("Intervention", iv.intervention_id.tolist())
            status = u2.selectbox("New status", ["APPROVED", "DELIVERED", "PLAYER_RETURNED", "CANCELLED"])
            if u3.form_submit_button("Update status"):
                lakebase().execute("UPDATE ops.interventions SET status=%s, updated_at=now() WHERE intervention_id=%s", (status, int(iid)))
                st.rerun()

with tab4:
    st.caption("Natural-language questions over governed Unity Catalog tables: DAU, revenue, retention cohorts, weekly churn, ticket root causes, risk queue, backtest value. Powered by a Genie space.")
    if "genie" not in st.session_state:
        st.session_state.genie = {"conv": None, "history": []}
    samples = ["How did the 14-day lapse rate of whales change from Season 6 to Season 7?",
               "What are high-risk payers complaining about, by ticket category?",
               "What was the crash rate by device tier before and after client v7.2?"]
    ex = st.columns(3)
    clicked = next((s for i, s in enumerate(samples) if ex[i].button(s, key=f"s{i}")), None)
    q = st.chat_input("Ask about players, churn, revenue, tickets…") or clicked
    for h in st.session_state.genie["history"]:
        with st.chat_message(h["role"]):
            st.markdown(h["text"] or "")
            if h.get("sql"):
                with st.expander("SQL"):
                    st.code(h["sql"], language="sql")
            if h.get("table") is not None:
                st.dataframe(h["table"], hide_index=True)
    if q:
        st.session_state.genie["history"].append({"role": "user", "text": q})
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            with st.spinner("Genie is thinking…"):
                try:
                    conv, text, sql, table = ask_genie(q, st.session_state.genie["conv"])
                    st.session_state.genie["conv"] = conv
                except Exception as e:
                    text, sql, table = f"Genie error: {e}", None, None
            st.markdown(text or "")
            if sql:
                with st.expander("SQL"):
                    st.code(sql, language="sql")
            if table is not None:
                st.dataframe(table, hide_index=True)
        st.session_state.genie["history"].append({"role": "assistant", "text": text, "sql": sql, "table": table})
