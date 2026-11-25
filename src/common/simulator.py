"""
PlayerPulse synthetic data simulator.

Simulates a fictional free-to-play, live-service mobile RPG ("Emberline: Rift Tactics") operated by a
fictional studio ("Emberforge Studios"), observed daily from 2026-03-01 to 2026-10-31.

Hidden behavioural model (what makes the ML stage meaningful):
  * each player has latent engagement, skill, spend propensity, device tier and a *satisfaction* state
  * satisfaction moves with wins/losses, crashes, "energy walls" (Season 7 energy rework, launched
    2026-06-02), guild membership and LiveOps events
  * low satisfaction -> fewer sessions (observable decline) -> higher daily churn hazard
  * a crash regression in client v7.2 (2026-08-12) hits low-tier Android devices until hotfix v7.3
  * frustrated players file support tickets / in-game feedback in free text (gamer shorthand),
    sometimes stating churn intent ("uninstalling", "done with this game") -> GenAI extracts signals
Churn is permanent (the player never returns), so "lapse in next 14 days" is a clean label.

Raw outputs (what the studio's systems export to the landing zone):
  player_accounts/    CSV   account-service extract (PII: email, device id, birth year)
  telemetry_daily/    CSV   game-server daily per-player aggregates (monthly .csv.gz files)
  store_transactions/ JSON  App Store / Google Play purchase receipts (monthly files)
  support_tickets/    JSON  helpdesk tickets + in-game feedback, free text (monthly files)
  liveops_calendar/   CSV   seasons, events and client releases
Deliberate data-quality defects are injected (duplicates, negative minutes, null ids) so the
Lakeflow expectations have something to catch.
"""
from __future__ import annotations

import datetime as dt
import json
import os

import numpy as np
import pandas as pd

START = dt.date(2026, 3, 1)
END = dt.date(2026, 10, 31)

REGIONS = [("NA", 0.38, 45), ("EU", 0.30, 60), ("LATAM", 0.17, 110), ("APAC", 0.15, 85)]  # code, share, latency ms
COUNTRIES = {"NA": ["US", "CA"], "EU": ["DE", "FR", "GB", "PL", "ES"], "LATAM": ["BR", "MX", "AR"], "APAC": ["PH", "AU", "ID", "JP"]}
CHANNELS = [("organic", 0.45), ("paid_ua", 0.40), ("influencer", 0.15)]
SKUS = [("gems_small", 0.99, 0.40), ("gems_medium", 4.99, 0.28), ("season_pass", 9.99, 0.14),
        ("gems_large", 19.99, 0.10), ("bundle_legendary", 49.99, 0.06), ("gems_mega", 99.99, 0.02)]
WHALE_SKU_P = [0.10, 0.15, 0.15, 0.25, 0.20, 0.15]

LIVEOPS = [
    ("SEASON", "Season 6: Ashen Crown", "2026-03-01", "2026-06-01", "Standard season"),
    ("SEASON", "Season 7: Rift Energy", "2026-06-02", "2026-08-31", "Energy system rework: matches cost energy, refills slower for non-pass holders"),
    ("SEASON", "Season 8: Ember Tide", "2026-09-01", "2026-11-30", "Energy refill partially restored"),
    ("EVENT", "Spring Clash tournament", "2026-04-10", "2026-04-19", "Limited-time PvP event"),
    ("EVENT", "Ember Festival", "2026-07-10", "2026-07-24", "Login rewards + festival skins"),
    ("EVENT", "Rift Raid", "2026-09-15", "2026-09-30", "Guild raid event"),
    ("RELEASE", "Client v7.0", "2026-06-02", "2026-06-02", "Season 7 client"),
    ("RELEASE", "Client v7.2", "2026-08-12", "2026-08-12", "New renderer; crash regression on low-tier Android GPUs"),
    ("RELEASE", "Client v7.3 hotfix", "2026-09-24", "2026-09-24", "Fixes v7.2 low-tier Android crash"),
]

# ----- ticket phrase banks (players write in shorthand / slang on purpose) -----------------------
T_CRASH = [
    "game keeps crashing after the update, lost my raid rewards",
    "crashes every time i open the guild hall. galaxy a12. fix pls",
    "app closes mid match since 7.2, lost 3 ranked games in a row",
    "black screen then crash on launch. reinstalled twice",
    "constant crashing on my phone since last patch, unplayable",
]
T_ENERGY = [
    "energy system is a cash grab now. can only play 3 matches then wait hours",
    "why does energy refill so slow?? feels like pay to play",
    "out of energy again. season 7 ruined the game for f2p",
    "used to play all evening, now energy runs out in 20 min",
]
T_MATCH = [
    "matchmaking puts me vs maxed whales every game",
    "lost 10 in a row, matchmaking is broken",
    "how am i supposed to win vs people with legendary everything",
    "ranked is impossible now, keep dropping divisions",
]
T_PAY = [
    "bought the season pass but didnt get the rewards",
    "charged twice for gem pack, want refund",
    "purchase failed but money taken from my card",
]
T_TOXIC = [
    "player in my guild keeps harassing me in chat",
    "toxic chat in ranked, please add better reporting",
]
T_OTHER = [
    "how do i transfer my account to new phone",
    "cant find the festival skins in the shop",
    "is there a way to change my username",
    "love the new festival event, more like this pls!",
    "great game, the raid event was super fun with my guild",
    "not quitting lol just wondering when next season starts",
]
T_INTENT = [
    "thinking of quitting honestly.",
    "uninstalling if this isnt fixed.",
    "done with this game.",
    "my whole guild is leaving.",
    "not spending another cent.",
    "probably moving to another game.",
]


def _sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def simulate(out_dir: str, n_initial: int = 30000, installs_per_day: int = 140, seed: int = 7, verbose: bool = True) -> dict:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(START, END, freq="D")
    D = len(dates)
    cap = n_initial + int(installs_per_day * D * 1.2) + 1000

    def day(s):
        return (pd.Timestamp(s) - pd.Timestamp(START)).days

    s7, s8 = day("2026-06-02"), day("2026-09-01")
    v72, v73 = day("2026-08-12"), day("2026-09-24")
    events = [(day("2026-04-10"), day("2026-04-19")), (day("2026-07-10"), day("2026-07-24")), (day("2026-09-15"), day("2026-09-30"))]
    season_starts = [0, s7, s8]

    # ---------------- player attributes -------------------------------------------------------
    install_day = np.empty(cap, dtype=int)
    install_day[:n_initial] = -rng.integers(15, 540, n_initial)
    k = n_initial
    for t in range(D):
        n_new = min(rng.poisson(installs_per_day * (1.6 if t in (s7, s7 + 1, s8, s8 + 1) else 1.0)), cap - k)
        install_day[k:k + n_new] = t
        k += n_new
    N = k
    install_day = install_day[:N]
    region = rng.choice(len(REGIONS), N, p=[r[1] for r in REGIONS])
    channel = rng.choice(len(CHANNELS), N, p=[c[1] for c in CHANNELS])
    android = rng.random(N) < np.where(region == 0, 0.45, 0.72)
    low_tier = android & (rng.random(N) < 0.35)
    age = np.clip(np.round(rng.normal(27, 8, N)), 13, 65).astype(int)
    minor = age < 18
    eng = rng.normal(0, 1, N) + np.where(channel == 1, -0.25, 0.0)
    skill = rng.normal(0, 1, N)
    spend_prop = np.exp(rng.normal(-6.4, 2.2, N)) * np.where(minor, 0.3, 1.0)  # long-tailed: whales
    whale = spend_prop > np.quantile(spend_prop, 0.985)
    low_spender = spend_prop < np.quantile(spend_prop, 0.6)
    guild = rng.random(N) < 0.35 + 0.1 * (eng > 0.5)
    base_s = rng.normal(0.4, 0.5, N)
    vet = install_day < 0
    eng[vet] += 0.35  # veterans already survived early churn

    s = base_s.copy()
    alive = np.ones(N, dtype=bool)
    churn_day = np.full(N, 10 ** 6)
    level = np.where(vet, np.clip(rng.normal(32, 10, N), 5, 60), 1).astype(float)
    loss_streak = np.zeros(N)
    crash7 = np.zeros(N); wall7 = np.zeros(N)
    last_buy = np.full(N, -999)
    grievance = np.zeros(N)  # unresolved payment issue / harassment: churn driver invisible in telemetry
    guild_ids = np.where(guild, rng.integers(1, 1800, N), 0)
    lat_base = np.array([r[2] for r in REGIONS])[region]
    pid = np.array([f"P{i + 1:07d}" for i in range(N)])

    tele_rows, tx_rows, tk_rows = [], [], []
    tx_id, tk_id = 10_000_000, 400_000

    for t in range(D):
        inst = (install_day <= t) & alive
        dsi = t - install_day
        ev = any(a <= t <= b for a, b in events)
        wkend = dates[t].day_of_week >= 5
        in_s7 = s7 <= t < s8
        p_play = _sig(0.2 + 0.85 * eng + 1.1 * s + 0.35 * ev + 0.25 * wkend + 0.4 * (dsi < 3))
        idx = np.where(inst & (rng.random(N) < p_play))[0]
        n = len(idx)
        sessions = 1 + rng.poisson(np.clip(1.2 + 0.6 * eng[idx] + 0.5 * s[idx], 0.1, 6))
        matches = rng.poisson(np.clip(sessions * 2.2, 0.5, 30))
        energy_cap = np.where(in_s7 & ~whale[idx], 6, 40)
        walls = (np.where(matches > energy_cap, 1 + rng.poisson(0.8, n), 0)
                 + in_s7 * rng.poisson(0.25, n) * ~whale[idx])
        matches = np.minimum(matches, energy_cap + rng.integers(0, 3, n))
        mm_pen = 0.35 * (t >= s7) * low_spender[idx]
        wins = rng.binomial(matches, _sig(0.35 * skill[idx] - mm_pen + 0.05 * (level[idx] < 10)))
        losses = matches - wins
        crash_rate = 0.015 + 0.22 * (low_tier[idx] & (v72 <= t < v73)) + 0.03 * low_tier[idx]
        crashes = rng.binomial(sessions, np.clip(crash_rate, 0, 0.9))
        minutes = np.round(np.maximum(1, sessions * rng.normal(14, 5, n) + matches * 3.5 - crashes * 4), 1)
        latency = np.round(lat_base[idx] * rng.lognormal(0, 0.18, n) + 25 * crashes, 0)
        loss_streak[idx] = np.where(wins == 0, loss_streak[idx] + losses, np.maximum(0, losses - wins))
        level[idx] += matches / 12.0
        crash7 *= 0.86; wall7 *= 0.86; grievance *= 0.99
        crash7[idx] += crashes; wall7[idx] += walls

        # satisfaction dynamics
        ds = np.zeros(N)
        ds[idx] = (0.06 * (wins - losses) / np.maximum(matches, 1) - 0.09 * crashes - 0.05 * walls
                   - 0.03 * (loss_streak[idx] >= 6) + 0.03 * ev)
        s = 0.95 * s + 0.05 * base_s + ds + 0.02 * guild - 0.012 * in_s7 * ~whale
        leave = guild & inst & (s < -0.6) & (rng.random(N) < 0.02)
        guild[leave] = False; guild_ids[leave] = 0
        join = ~guild & inst & (rng.random(N) < 0.002)
        guild[join] = True; guild_ids[join] = rng.integers(1, 1800, int(join.sum()))

        # purchases
        pass_push = 2.5 if any(0 <= t - ss < 7 for ss in season_starts) else 1.0
        p_buy = np.clip(spend_prop[idx] * _sig(1.2 * s[idx] + 0.5) * pass_push * (1 + 0.6 * ev)
                        * (1 + 0.8 * in_s7 * (walls > 0)), 0, 0.9)
        buyers = idx[rng.random(n) < p_buy]
        buyer_set = set(buyers.tolist())
        pay_fail = set()
        for i in buyers:
            if rng.random() < 0.03:  # store / entitlement failure (charged, items not granted)
                pay_fail.add(int(i))
            j = rng.choice(len(SKUS), p=WHALE_SKU_P if whale[i] else [x[2] for x in SKUS])
            tx_id += 1
            ts = pd.Timestamp(dates[t]) + pd.Timedelta(minutes=int(rng.integers(0, 1440)))
            amt, status = SKUS[j][1], "COMPLETED"
            if rng.random() < 0.01:
                amt, status = -amt, "REFUNDED"
            tx_rows.append((f"TX{tx_id}", pid[i], ts.isoformat(), "google_play" if android[i] else "app_store",
                            SKUS[j][0], amt, "USD", status))
            last_buy[i] = t

        # support tickets / in-game feedback
        p_tk = (0.0008 + 0.025 * (crashes > 0) + 0.008 * (walls > 1) + 0.006 * (loss_streak[idx] >= 8)
                + 0.02 * (whale[idx] & (walls > 0)) + 0.6 * np.isin(idx, list(pay_fail)) + 0.002 * guild[idx])
        for q in np.where(rng.random(n) < p_tk)[0]:
            i = idx[q]
            opts, wts = [T_OTHER], [0.25]
            if crashes[q] > 0: opts.append(T_CRASH); wts.append(3.0)
            if walls[q] > 0: opts.append(T_ENERGY); wts.append(1.5)
            if loss_streak[i] >= 6: opts.append(T_MATCH); wts.append(1.2)
            if int(i) in pay_fail: opts.append(T_PAY); wts.append(50.0)
            elif i in buyer_set and rng.random() < 0.1: opts.append(T_PAY); wts.append(0.6)
            if guild[i] and rng.random() < 0.08: opts.append(T_TOXIC); wts.append(2.0)
            wts = np.array(wts) / sum(wts)
            bank = opts[rng.choice(len(opts), p=wts)]
            text = str(rng.choice(bank))
            if bank is T_PAY and rng.random() < 0.75:
                grievance[i] += 1.0
            if bank is T_TOXIC:
                grievance[i] += 0.8
            if (s[i] < -0.4 and rng.random() < 0.45) or (grievance[i] > 0.5 and rng.random() < 0.6):
                text = text + " " + str(rng.choice(T_INTENT))
            r = rng.random()
            text = text.upper() if r < 0.08 else text.capitalize() if r < 0.35 else text
            tk_id += 1
            tk_rows.append((f"TK{tk_id}", pid[i], (pd.Timestamp(dates[t]) + pd.Timedelta(minutes=int(rng.integers(0, 1440)))).isoformat(),
                            str(rng.choice(["helpdesk", "in_game_feedback", "helpdesk"])), text))

        tele_rows.append(pd.DataFrame({
            "player_id": pid[idx], "activity_date": dates[t].strftime("%Y-%m-%d"),
            "sessions": sessions, "minutes_played": minutes, "matches": matches, "wins": wins, "losses": losses,
            "energy_walls": walls.astype(int), "crashes": crashes, "avg_latency_ms": latency,
            "max_level": np.floor(level[idx]).astype(int), "guild_id": guild_ids[idx],
            "client_version": "7.3" if t >= v73 else "7.2" if t >= v72 else "7.0" if t >= s7 else "6.4",
        }))

        # churn hazard (permanent)
        logit = (-6.2 - 1.5 * s + 1.2 * (dsi < 7) + 0.5 * (dsi < 30) + 0.35 * (loss_streak >= 6)
                 + 0.20 * np.minimum(crash7, 5) + 0.12 * np.minimum(wall7, 6) - 0.55 * guild
                 - 0.5 * (t - last_buy < 14) - 0.4 * eng + 2.6 * np.minimum(grievance, 1.5))
        ch = inst & (rng.random(N) < _sig(logit))
        alive[ch] = False
        churn_day[ch] = t

    tele = pd.concat(tele_rows, ignore_index=True)
    if verbose:
        print(f"simulated {D} days, {N:,} players, {len(tele):,} telemetry rows, {len(tx_rows):,} purchases, {len(tk_rows):,} tickets")

    os.makedirs(out_dir, exist_ok=True)
    for sub in ["player_accounts", "telemetry_daily", "store_transactions", "support_tickets", "liveops_calendar"]:
        os.makedirs(os.path.join(out_dir, sub), exist_ok=True)

    acc = pd.DataFrame({
        "player_id": pid,
        "email": [f"player{i + 1}@{d}" for i, d in enumerate(rng.choice(["mail.example", "inbox.example", "webmail.example"], N))],
        "device_id": [f"{'AND' if a else 'IOS'}-{x:09x}" for a, x in zip(android, rng.integers(16 ** 8, 16 ** 9, N))],
        "platform": np.where(android, "android", "ios"),
        "device_tier": np.where(low_tier, "low", np.where(rng.random(N) < 0.5, "mid", "high")),
        "region": np.array([r[0] for r in REGIONS])[region],
        "country_code": [str(rng.choice(COUNTRIES[REGIONS[r][0]])) for r in region],
        "birth_year": 2026 - age,
        "acquisition_channel": np.array([c[0] for c in CHANNELS])[channel],
        "install_date": [(START + dt.timedelta(days=int(x))).isoformat() for x in install_day],
        "marketing_opt_in": rng.random(N) < 0.62,
    })
    pd.concat([acc, acc.sample(25, random_state=3)]).to_csv(
        os.path.join(out_dir, "player_accounts", f"player_accounts_{END.isoformat()}.csv"), index=False)

    tele["month"] = tele.activity_date.str[:7]
    for m, g in tele.groupby("month"):
        g = g.drop(columns="month").copy()
        bad = rng.random(len(g)) < 0.0004
        g.loc[bad, "minutes_played"] = -g.loc[bad, "minutes_played"]
        g.loc[rng.random(len(g)) < 0.0002, "player_id"] = None
        g = pd.concat([g, g.sample(frac=0.001, random_state=1)])
        g.to_csv(os.path.join(out_dir, "telemetry_daily", f"telemetry_{m}.csv.gz"), index=False, compression="gzip")

    tx = pd.DataFrame(tx_rows, columns=["transaction_id", "player_id", "purchase_ts", "store", "sku", "amount_usd", "currency", "status"])
    tx["month"] = tx.purchase_ts.str[:7]
    for m, g in tx.groupby("month"):
        g.drop(columns="month").to_json(os.path.join(out_dir, "store_transactions", f"receipts_{m}.json"), orient="records", lines=True)

    tk = pd.DataFrame(tk_rows, columns=["ticket_id", "player_id", "created_ts", "channel", "message"])
    tk["month"] = tk.created_ts.str[:7]
    for m, g in tk.groupby("month"):
        g.drop(columns="month").to_json(os.path.join(out_dir, "support_tickets", f"tickets_{m}.json"), orient="records", lines=True)

    pd.DataFrame(LIVEOPS, columns=["entry_type", "name", "start_date", "end_date", "description"]).to_csv(
        os.path.join(out_dir, "liveops_calendar", "liveops_calendar.csv"), index=False)

    churned = churn_day < 10 ** 6
    stats = {
        "days": D, "players": int(N), "minors": int(minor.sum()), "telemetry_rows": int(len(tele)),
        "purchases": len(tx), "gross_revenue_usd": round(float(tx.amount_usd.sum()), 2),
        "payers": int(tx.player_id.nunique()), "tickets": len(tk), "churned_players": int(churned.sum()),
        "churn_by_month": pd.Series(dates[churn_day[churned]].strftime("%Y-%m")).value_counts().sort_index().to_dict(),
        "dau_by_month": (tele.groupby("month").player_id.count() / tele.groupby("month").activity_date.nunique()).round(0).to_dict(),
        "revenue_by_month": tx.groupby("month").amount_usd.sum().round(0).to_dict(),
    }
    if verbose:
        print(json.dumps(stats, indent=2, default=str))
    return stats


if __name__ == "__main__":
    import sys
    simulate(sys.argv[1] if len(sys.argv) > 1 else "/tmp/playerpulse_raw")
