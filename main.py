# main.py
# Bot Completo - SoccerData (API + scraping leve) + fallback SofaScore
# Requisitos: see requirements.txt
#
# ENV (obrigatórias):
# - TELEGRAM_TOKEN
# - CHAT_ID
#
# ENV (opcionais tuning):
# - LOOP_SLEEP (s, default 25)
# - MIN_MIN (default 10)
# - MAX_MIN (default 25)
# - MIN_SHOTS_TOTAL (default 2)
# - MIN_CORNERS_TOTAL (default 2)
# - MIN_XG_TOTAL (default 0.9)
# - MIN_DANGEROUS_ATTACKS (default 15)
# - MIN_MOMENTUM_PCT (default 60)
# - HISTORY_N (default 5)
# - HISTORY_MIN_3PLUS (default 3)
# - REQUEST_TIMEOUT (default 12)
# - INTERNAL_PING (true/false)
# - PING_INTERVAL (sec)
# - PRIMARY_URL (if using INTERNAL_PING)
#
import os
import time
import json
import asyncio
import math
import traceback
from threading import Thread
from datetime import datetime
from pathlib import Path

import requests
import nest_asyncio
from flask import Flask, Response
from telegram import Bot

# try soccerdata import; if not present we'll fallback to SofaScore endpoints
try:
    from soccerdata import SofaScore
    SOFA_AVAILABLE = True
except Exception:
    SOFA_AVAILABLE = False

nest_asyncio.apply()

# ----------------- CONFIG -----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0) or 0)

# live/historic thresholds
MIN_MIN = int(os.getenv("MIN_MIN", 10))
MAX_MIN = int(os.getenv("MAX_MIN", 25))
MIN_SHOTS_TOTAL = int(os.getenv("MIN_SHOTS_TOTAL", 2))
MIN_CORNERS_TOTAL = int(os.getenv("MIN_CORNERS_TOTAL", 2))
MIN_XG_TOTAL = float(os.getenv("MIN_XG_TOTAL", 0.9))
MIN_DANGEROUS_ATTACKS = int(os.getenv("MIN_DANGEROUS_ATTACKS", 15))
MIN_MOMENTUM_PCT = int(os.getenv("MIN_MOMENTUM_PCT", 60))

# history
HISTORY_N = int(os.getenv("HISTORY_N", 5))
HISTORY_MIN_3PLUS = int(os.getenv("HISTORY_MIN_3PLUS", 3))

LOOP_SLEEP = int(os.getenv("LOOP_SLEEP", 25))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 12))

INTERNAL_PING = os.getenv("INTERNAL_PING", "false").lower() == "true"
PING_INTERVAL = int(os.getenv("PING_INTERVAL", 600))
PRIMARY_URL = os.getenv("PRIMARY_URL") or os.getenv("RENDER_EXTERNAL_URL") or os.getenv("APP_URL")

# ----------------- END CONFIG -----------------

app = Flask(__name__)
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; Over0.5Bot/1.0)"})
bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

@app.route("/")
def home():
    return Response("Bot online (SoccerData)", status=200, mimetype='text/plain')

def run_flask():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# --------- Helpers: HTTP & safe get ---------
def safe_get_json(url, params=None):
    try:
        r = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            # try parse json
            try:
                return r.json()
            except Exception:
                return None
        else:
            print(f"[HTTP {r.status_code}] {url}")
            return None
    except Exception as e:
        print(f"[ERR] request {url}: {e}")
        return None

def send_telegram(text):
    if not bot:
        print("[WARN] TELEGRAM not configured")
        return
    try:
        bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        print(f"[ERR] Telegram send: {e}")

# --------- SofaScore endpoints (fallback) ---------
SOFA_LIVE = "https://api.sofascore.com/api/v1/sport/football/events/live"
SOFA_EVENT_STAT = "https://api.sofascore.com/api/v1/event/{eid}/statistics"
SOFA_EVENT_PAGE = "https://api.sofascore.com/api/v1/event/{eid}"
TEAM_EVENTS_1 = "https://api.sofascore.com/api/v1/team/{team_id}/events/last/{n}"
TEAM_EVENTS_2 = "https://api.sofascore.com/api/v1/team/{team_id}/events"

# ---- extract stats from sofa/json structures (best-effort) ----
def extract_stats_generic(j):
    # try to extract shots_on_target, xg, corners, dangerous attacks, momentum
    out = {
        "shots_on_target_home": 0,
        "shots_on_target_away": 0,
        "xg_home": 0.0,
        "xg_away": 0.0,
        "corners_home": 0,
        "corners_away": 0,
        "dangerous_attacks": 0,
        "momentum_pct": 0
    }
    if not j:
        return out
    # several heuristics: search keys recursively
    def rec(o, path=""):
        if isinstance(o, dict):
            for k,v in o.items():
                lk = k.lower()
                newp = f"{path}.{lk}"
                if isinstance(v, (int, float, str)):
                    sval = None
                    try:
                        sval = float(v)
                    except:
                        sval = None
                    # xg
                    if "xg" in lk or ("expected" in lk and "goal" in lk):
                        if "home" in newp:
                            out["xg_home"] = float(v or 0)
                        elif "away" in newp:
                            out["xg_away"] = float(v or 0)
                        else:
                            if out["xg_home"] == 0:
                                out["xg_home"] = float(v or 0)
                            elif out["xg_away"] == 0:
                                out["xg_away"] = float(v or 0)
                    # shots on target
                    if ("shots" in lk and ("target" in lk or "on target" in lk)) or "shotsontarget" in lk:
                        if "home" in newp:
                            out["shots_on_target_home"] = int(float(v or 0))
                        elif "away" in newp:
                            out["shots_on_target_away"] = int(float(v or 0))
                        else:
                            if out["shots_on_target_home"] == 0:
                                out["shots_on_target_home"] = int(float(v or 0))
                            elif out["shots_on_target_away"] == 0:
                                out["shots_on_target_away"] = int(float(v or 0))
                    # corners
                    if "corner" in lk:
                        if "home" in newp:
                            out["corners_home"] = int(float(v or 0))
                        elif "away" in newp:
                            out["corners_away"] = int(float(v or 0))
                        else:
                            if out["corners_home"] == 0:
                                out["corners_home"] = int(float(v or 0))
                            elif out["corners_away"] == 0:
                                out["corners_away"] = int(float(v or 0))
                    # dangerous attacks or momentum
                    if "danger" in lk or "dangerous" in lk:
                        try:
                            out["dangerous_attacks"] = int(float(v or 0))
                        except:
                            pass
                    if "momentum" in lk or "possessionmomentum" in lk or "moment" in lk:
                        try:
                            out["momentum_pct"] = int(float(v or 0))
                        except:
                            pass
                elif isinstance(v, (dict, list)):
                    rec(v, newp)
        elif isinstance(o, list):
            for i, it in enumerate(o):
                rec(it, f"{path}[{i}]")
    try:
        rec(j)
    except Exception:
        pass
    return out

# ---- SoccerData wrapper (preferred) ----
sofa_obj = None
if SOFA_AVAILABLE:
    try:
        sofa_obj = SofaScore()
    except Exception:
        sofa_obj = None

# ---- get live events via soccerdata when possible, else fallback to SofaScore endpoint ----
def get_live_events():
    # try soccerdata SofaScore
    try:
        if sofa_obj:
            try:
                live = sofa_obj.read_live_events()
                if isinstance(live, (list, tuple)):
                    return live
                # sometimes a dataframe or dict; convert best-effort
                return live
            except Exception as e:
                print("[WARN] soccerdata read_live_events failed:", e)
    except Exception:
        pass
    # fallback: direct sofascore endpoint
    j = safe_get_json(SOFA_LIVE)
    if not j:
        return []
    # typical shape: j['events'] or j
    if isinstance(j, dict):
        for k in ("events", "data", "items", "content", "results"):
            if k in j and isinstance(j[k], list):
                return j[k]
        # fallback: sometimes root has list
        for v in j.values():
            if isinstance(v, list):
                return v
    if isinstance(j, list):
        return j
    return []

# ---- parse minute and scores from event (best-effort) ----
def parse_minute(ev):
    # try common fields
    try:
        if isinstance(ev, dict):
            st = ev.get("status") or {}
            minute = st.get("elapsed") or ev.get("elapsed") or ev.get("time", {}).get("minute")
            if isinstance(minute, int):
                return minute
            if isinstance(minute, str) and minute.isdigit():
                return int(minute)
            if "clock" in ev:
                clk = ev.get("clock")
                if isinstance(clk, dict) and "minute" in clk:
                    return int(clk["minute"])
    except Exception:
        pass
    return None

def parse_score(ev):
    try:
        # many variations: homeScore/homeTeam.score/score.home etc.
        home = ev.get("homeScore") if "homeScore" in ev else None
        away = ev.get("awayScore") if "awayScore" in ev else None
        if home is None:
            ht = ev.get("home") or ev.get("homeTeam")
            if isinstance(ht, dict):
                home = ht.get("score") or ht.get("goals") or ht.get("result")
        if away is None:
            at = ev.get("away") or ev.get("awayTeam")
            if isinstance(at, dict):
                away = at.get("score") or at.get("goals") or at.get("result")
        if home is None or away is None:
            sc = ev.get("score") or ev.get("result")
            if isinstance(sc, dict):
                home = sc.get("home") or sc.get("fullTime", {}).get("home")
                away = sc.get("away") or sc.get("fullTime", {}).get("away")
        if home is None or away is None:
            # default 0,0
            return (0,0)
        return (int(home), int(away))
    except Exception:
        return (0,0)

# ---- get event statistics using soccerdata or sofascore endpoint ----
def get_event_stats(ev):
    # if soccerdata object can fetch statistics for event, prefer it
    try:
        if sofa_obj:
            try:
                # soccerdata SofaScore object likely exposes event statistics methods
                # we'll attempt call and fall back silently if not supported
                st = sofa_obj.read_event_statistics(ev.get("id") or ev.get("eventId") or ev.get("matchId"))
                if st is not None:
                    return extract_stats_generic(st)
            except Exception:
                pass
    except Exception:
        pass
    # fallback to sofascore statistics endpoint
    eid = ev.get("id") or ev.get("eventId") or ev.get("matchId")
    if not eid:
        return None
    url = SOFA_EVENT_STAT.format(eid=eid)
    j = safe_get_json(url)
    if j:
        return extract_stats_generic(j)
    # fallback to event page
    url2 = SOFA_EVENT_PAGE.format(eid=eid)
    j2 = safe_get_json(url2)
    if j2:
        return extract_stats_generic(j2)
    return None

# ---- team history (last N finished matches) using soccerdata or sofascore endpoints ----
def get_team_history(team_id, n=HISTORY_N):
    # try soccerdata wrapper first
    try:
        if sofa_obj:
            try:
                df = sofa_obj.read_team_results(team_id)
                # soccerdata often returns pandas DataFrame; convert rows to dicts
                if df is not None:
                    # take last n finished matches
                    recs = []
                    try:
                        # iterate rows
                        rows = df.tail(n).to_dict(orient="records")
                        for r in reversed(rows):  # most recent first
                            # expected keys: home_score, away_score, ht_home, ht_away
                            recs.append({
                                "home_score": int(r.get("home_score") or r.get("home") or 0),
                                "away_score": int(r.get("away_score") or r.get("away") or 0),
                                "ht_home": int(r.get("ht_home") or r.get("ht_home_score") or 0),
                                "ht_away": int(r.get("ht_away") or r.get("ht_away_score") or 0),
                            })
                        if recs:
                            return recs[:n]
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass
    # fallback to team events endpoints in SofaScore API
    tried = []
    for template in (TEAM_EVENTS_1, TEAM_EVENTS_2):
        try:
            url = template.format(team_id=team_id, n=n)
            tried.append(url)
            j = safe_get_json(url)
            if not j:
                continue
            items = None
            if isinstance(j, list):
                items = j
            elif isinstance(j, dict):
                for k in ("events","data","items","content","results"):
                    if k in j and isinstance(j[k], list):
                        items = j[k]
                        break
                if items is None:
                    # find any list in values
                    for v in j.values():
                        if isinstance(v, list):
                            items = v
                            break
            if not items:
                continue
            finished = []
            for ev in items:
                # check finished status heuristics
                st = ev.get("status") or {}
                status_code = st.get("type") or st.get("code") or ev.get("status")
                is_finished = False
                if isinstance(status_code, str) and status_code.lower() in ("ended","finished","ft","closed"):
                    is_finished = True
                if isinstance(status_code, int) and status_code == 3:
                    is_finished = True
                desc = st.get("description") or ""
                if not is_finished and isinstance(desc, str) and "FT" in desc:
                    is_finished = True
                if not is_finished:
                    continue
                # extract scores
                home = ev.get("homeScore") or (ev.get("home") or {}).get("score")
                away = ev.get("awayScore") or (ev.get("away") or {}).get("score")
                ht_home = None
                ht_away = None
                if isinstance(ev.get("halfTime"), dict):
                    ht_home = ev["halfTime"].get("home")
                    ht_away = ev["halfTime"].get("away")
                if ht_home is None and "htScore" in ev:
                    ht = ev.get("htScore")
                    if isinstance(ht, dict):
                        ht_home = ht.get("home"); ht_away = ht.get("away")
                finished.append({
                    "home_score": int(home) if home is not None else 0,
                    "away_score": int(away) if away is not None else 0,
                    "ht_home": int(ht_home) if ht_home is not None else 0,
                    "ht_away": int(ht_away) if ht_away is not None else 0
                })
                if len(finished) >= n:
                    break
            if finished:
                return finished[:n]
        except Exception:
            continue
    print(f"[WARN] team history not found; tried: {tried}")
    return []

# ---- historic rules check (as you requested) ----
def history_passes(team_history):
    """
    team_history: list of last N matches (most recent first), where a record has:
       home_score, away_score, ht_home, ht_away
    Conditions:
      - none of last N matches ended 0-0 (FT)
      - team scored at HT in at least HISTORY_MIN_3PLUS matches (3 or more)
      - also compute HT goals avg and xG avg placeholder (xG avg may be unavailable here)
    """
    if not team_history or len(team_history) < HISTORY_N:
        return False, {"notes":"incomplete_history"}
    final_zero_count = 0
    ht_goal_count = 0
    ht_goals_sum = 0
    # We don't always know if the team was home/away in the returned list; for team-specific endpoints typically it's ordered accordingly.
    # We'll conservatively treat any HT goals credited to 'team side' as a HT goal.
    for rec in team_history[:HISTORY_N]:
        if rec.get("home_score",0) == 0 and rec.get("away_score",0) == 0:
            final_zero_count += 1
        # if any HT goal exists, count as HT goal presence
        if (rec.get("ht_home",0) or rec.get("ht_away",0)):
            # we can't always ensure team scored specifically; counting match where any HT goal occurred is a proxy
            # This is best-effort based on available endpoints.
            ht_goal_count += 1
        ht_goals_sum += (rec.get("ht_home",0) + rec.get("ht_away",0))
    no_final_zeros = (final_zero_count == 0)
    enough_ht = (ht_goal_count >= HISTORY_MIN_3PLUS)
    ht_avg = ht_goals_sum / HISTORY_N if HISTORY_N else 0.0
    return (no_final_zeros and enough_ht), {"final_zero_count": final_zero_count, "ht_goal_count": ht_goal_count, "ht_avg": ht_avg}

# ---- prob calculation (same formula you had) ----
def calculate_prob(stats):
    xg_h = float(stats.get("xg_home", 0) or 0)
    xg_a = float(stats.get("xg_away", 0) or 0)
    shots_h = int(stats.get("shots_on_target_home", 0) or 0)
    shots_a = int(stats.get("shots_on_target_away", 0) or 0)
    corners_h = int(stats.get("corners_home", 0) or 0)
    corners_a = int(stats.get("corners_away", 0) or 0)
    prob = (xg_h + xg_a + (shots_h + shots_a) / 10.0 + (corners_h + corners_a) / 20.0) / 2.0
    return prob

# ---- format message ----
def format_msg(ev, stats, prob, hist_home_info, hist_away_info):
    home_name = (ev.get("homeTeam") or ev.get("home") or {}).get("name") or (ev.get("home",{}).get("name")) or "Home"
    away_name = (ev.get("awayTeam") or ev.get("away") or {}).get("name") or (ev.get("away",{}).get("name")) or "Away"
    minute = parse_minute(ev) or "?"
    home_score, away_score = parse_score(ev)
    shots_on = int(stats.get("shots_on_target_home",0)) + int(stats.get("shots_on_target_away",0))
    corners = int(stats.get("corners_home",0)) + int(stats.get("corners_away",0))
    xg_total = float(stats.get("xg_home",0.0)) + float(stats.get("xg_away",0.0))
    dangerous = int(stats.get("dangerous_attacks",0))
    momentum = int(stats.get("momentum_pct",0))
    prob_pct = int(prob * 100)
    # historic info
    h_home = hist_home_info or {}
    h_away = hist_away_info or {}
    home_ht_avg = h_home.get("ht_avg", 0.0)
    away_ht_avg = h_away.get("ht_avg", 0.0)
    home_3plus = h_home.get("ht_goal_count", 0)
    away_3plus = h_away.get("ht_goal_count", 0)
    msg = (f"*🚨 ALTA CHANCE DE GOL HT*\n"
           f"*{home_name} x {away_name}*\n"
           f"⏱ *{minute}'* | {home_score}-{away_score}\n\n"
           f"*📊 Estatísticas ao vivo*\n"
           f"- Shots on target: *{shots_on}*\n"
           f"- Escanteios: *{corners}*\n"
           f"- xG total: *{xg_total:.2f}*\n"
           f"- Ataques perigosos: *{dangerous}*\n"
           f"- Momentum: *{momentum}%*\n\n"
           f"*📚 Histórico (últimos {HISTORY_N} jogos)*\n"
           f"- Mandante: HT goals em *{home_3plus}* / {HISTORY_N}\n"
           f"- Visitante: HT goals em *{away_3plus}* / {HISTORY_N}\n"
           f"- Nenhum 0x0 FT nos últimos {HISTORY_N}\n"
           f"- Média HT goals: *{home_ht_avg:.2f} / {away_ht_avg:.2f}*\n\n"
           f"*Prob (modelo): {prob_pct}%*\n"
           f"👉 *Entrada sugerida: Over 0.5 HT*")
    return msg

# ---- monitor loop ----
alerted = set()

async def monitor():
    global alerted
    print("[+] Monitor iniciado (SoccerData + fallback)")
    while True:
        try:
            events = get_live_events()
            if not events:
                await asyncio.sleep(LOOP_SLEEP)
                continue
            for ev in events:
                try:
                    # identify event id
                    eid = ev.get("id") or ev.get("eventId") or ev.get("matchId")
                    if not eid:
                        continue
                    if str(eid) in alerted:
                        continue
                    minute = parse_minute(ev)
                    if minute is None:
                        continue
                    if minute < MIN_MIN or minute > MAX_MIN:
                        continue
                    h_score, a_score = parse_score(ev)
                    if h_score != 0 or a_score != 0:
                        continue
                    # get stats
                    stats = get_event_stats(ev)
                    if not stats:
                        continue
                    shots_total = int(stats.get("shots_on_target_home",0)) + int(stats.get("shots_on_target_away",0))
                    corners_total = int(stats.get("corners_home",0)) + int(stats.get("corners_away",0))
                    xg_total = float(stats.get("xg_home",0.0)) + float(stats.get("xg_away",0.0))
                    dangerous = int(stats.get("dangerous_attacks",0))
                    momentum = int(stats.get("momentum_pct",0))
                    if shots_total < MIN_SHOTS_TOTAL:
                        continue
                    if corners_total < MIN_CORNERS_TOTAL:
                        continue
                    if xg_total < MIN_XG_TOTAL:
                        continue
                    if dangerous < MIN_DANGEROUS_ATTACKS:
                        continue
                    if momentum < MIN_MOMENTUM_PCT:
                        continue
                    # history checks: need team ids
                    home_team = ev.get("homeTeam") or ev.get("home") or {}
                    away_team = ev.get("awayTeam") or ev.get("away") or {}
                    home_tid = home_team.get("id") or home_team.get("teamId")
                    away_tid = away_team.get("id") or away_team.get("teamId")
                    if not home_tid or not away_tid:
                        # fallback: try name-based lookup (skip history if not available)
                        print(f"[WARN] team ids not found for event {eid}, skipping history check")
                        continue
                    hist_home = get_team_history(home_tid, n=HISTORY_N)
                    hist_away = get_team_history(away_tid, n=HISTORY_N)
                    ok_home, info_home = history_passes(hist_home)
                    ok_away, info_away = history_passes(hist_away)
                    if not (ok_home and ok_away):
                        print(f"[SKIP] history fail for {eid} home_ok={ok_home} away_ok={ok_away} info_h={info_home} info_a={info_away}")
                        continue
                    prob = calculate_prob(stats)
                    if prob < 0.85:
                        print(f"[SKIP] prob {prob:.2f} < 0.85 for {eid}")
                        continue
                    # all passed -> alert
                    msg = format_msg(ev, stats, prob, info_home, info_away)
                    send_telegram(msg)
                    alerted.add(str(eid))
                    print(f"[ALERT] event {eid} -> sent")
                except Exception as e:
                    print("[ERR] inside loop event:", e)
                    traceback.print_exc()
            await asyncio.sleep(LOOP_SLEEP)
        except Exception as e:
            print("[ERR] monitor main:", e)
            traceback.print_exc()
            await asyncio.sleep(10)

# ---- internal ping thread (optional) ----
def internal_ping(url):
    while True:
        try:
            requests.get(url, timeout=8)
        except:
            pass
        time.sleep(PING_INTERVAL)

if __name__ == "__main__":
    # start flask
    t = Thread(target=run_flask, daemon=True)
    t.start()
    time.sleep(1)
    print("[*] Flask started.")
    # internal ping if enabled
    if INTERNAL_PING and PRIMARY_URL:
        p = Thread(target=internal_ping, args=(PRIMARY_URL,), daemon=True)
        p.start()
        print("[*] internal pinging", PRIMARY_URL)
    # start monitor
    try:
        asyncio.run(monitor())
    except KeyboardInterrupt:
        print("Stopping...")


