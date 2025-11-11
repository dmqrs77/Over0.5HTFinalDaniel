import os
import requests
import asyncio
import nest_asyncio
from datetime import datetime, date
from telegram import Bot
from flask import Flask, Response
from threading import Thread
import time
import json
from pathlib import Path
import math

nest_asyncio.apply()

# -----------------------
# Config (via ENV vars)
# -----------------------
TOKEN = os.getenv("TELEGRAM_TOKEN")               # seu token Telegram
API_KEY = os.getenv("API_FOOTBALL_KEY")           # chave API-Football (x-rapidapi-key)
CHAT_ID = int(os.getenv("CHAT_ID", 0))            # chat id para enviar mensagens
USAGE_FILE = os.getenv("USAGE_FILE", "usage.json")# arquivo local para contar requisições
MAX_DAILY_REQUESTS = int(os.getenv("MAX_DAILY_REQUESTS", 100))  # limite diário (padrão 100)
MAX_STATS_PER_LOOP = int(os.getenv("MAX_STATS_PER_LOOP", 8))     # limitar stats por iteração
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", 1.5))          # segundos entre requests
LOOP_SLEEP = int(os.getenv("LOOP_SLEEP", 60))                   # tempo entre checagens
BACKOFF_BASE = float(os.getenv("BACKOFF_BASE", 2.0))            # base do backoff exponencial
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 4))                  # retries por request
USAGE_PATH = Path(USAGE_FILE)

bot = Bot(token=TOKEN) if TOKEN else None

app = Flask(__name__)

@app.route('/')
def home():
    return Response("Bot online", status=200, mimetype='text/plain')

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# -----------------------
# Usage persistence
# -----------------------
def load_usage():
    if not USAGE_PATH.exists():
        data = {"date": str(date.today()), "count": 0}
        USAGE_PATH.write_text(json.dumps(data))
        return data
    try:
        data = json.loads(USAGE_PATH.read_text())
    except Exception:
        data = {"date": str(date.today()), "count": 0}
    # reset daily count if date changed
    if data.get("date") != str(date.today()):
        data = {"date": str(date.today()), "count": 0}
        save_usage(data)
    return data

def save_usage(data):
    USAGE_PATH.write_text(json.dumps(data))

def increment_usage(n=1):
    data = load_usage()
    data["count"] = data.get("count", 0) + n
    save_usage(data)

def get_usage_count():
    data = load_usage()
    return data.get("count", 0)

# -----------------------
# HTTP helper with backoff & counting
# -----------------------
session = requests.Session()

def should_allow_request():
    count = get_usage_count()
    return count < MAX_DAILY_REQUESTS

async def safe_get(url, headers=None, params=None, count_as_api=True):
    """
    Faz requests.get de forma segura com backoff exponencial e contagem de uso.
    Usa asyncio.to_thread para não travar o loop.
    """
    # check daily limit first
    if count_as_api and not should_allow_request():
        raise RuntimeError(f"Limite diário de {MAX_DAILY_REQUESTS} requisições atingido ({get_usage_count()})")

    attempt = 0
    while attempt <= MAX_RETRIES:
        try:
            # executar blocking requests.get em thread
            resp = await asyncio.to_thread(session.get, url, headers=headers, params=params, timeout=15)
            status = resp.status_code

            # Contabiliza apenas se for resposta válida (mesmo 4xx/5xx serão contadas como tentativas)
            if count_as_api:
                increment_usage(1)

            # sucesso
            if status == 200:
                return resp.json()
            # rate limit - espera mais tempo
            if status == 429:
                wait = BACKOFF_BASE ** attempt
                print(f"[WARN] 429 recebido. Backoff {wait}s (attempt {attempt}).")
                await asyncio.sleep(wait)
                attempt += 1
                continue
            # auth problems
            if status in (401, 403):
                print(f"[ERROR] HTTP {status} — problema de autenticação/permissão com API (status {status}).")
                # avisa no Telegram (se possível)
                if bot:
                    try:
                        await bot.send_message(chat_id=CHAT_ID, text=f"⚠️ API Football retornou {status}. Verifique sua chave (API_FOOTBALL_KEY).")
                    except Exception as e:
                        print(f"Erro ao notificar via Telegram: {e}")
                # pausa longa para evitar novos bloqueios
                raise RuntimeError(f"Autorização falhou com status {status}")
            # outros erros de cliente/servidor: tenta de novo com backoff
            print(f"[WARN] HTTP {status} recebido. Tentando novamente com backoff.")
            wait = BACKOFF_BASE ** attempt
            await asyncio.sleep(wait)
            attempt += 1
        except requests.RequestException as e:
            # erro de rede
            wait = BACKOFF_BASE ** attempt
            print(f"[WARN] RequestException: {e}. Backoff {wait}s.")
            await asyncio.sleep(wait)
            attempt += 1
    raise RuntimeError("Máximo de tentativas atingido em safe_get")

# -----------------------
# Funções do bot
# -----------------------
async def enviar(msg):
    if not bot:
        print("⚠️ Bot não configurado. Configure TELEGRAM_TOKEN nos Secrets.")
        return
    try:
        # send_message pode ser sync/async dependendo da lib; usando asyncio.to_thread para garantir
        await asyncio.to_thread(bot.send_message, chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")

# -----------------------
# Lógica principal
# -----------------------
async def main():
    if not TOKEN or not API_KEY or not CHAT_ID:
        print("⚠️ CONFIGURAÇÃO NECESSÁRIA:")
        print("Configure os Secrets no Render:")
        print("- TELEGRAM_TOKEN (token do seu bot)")
        print("- API_FOOTBALL_KEY (chave da API Football)")
        print("- CHAT_ID (ID do seu chat/canal)")
        print("\n✅ Servidor Flask rodando. Configure os Secrets para ativar o bot.")
        while True:
            await asyncio.sleep(60)
        return

    print("✅ Iniciando bot com proteções contra suspensão da API...")

    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": "v3.football.api-sports.io"
    }

    alerted_matches = set()
    # pequeno cache em memória para stats e live, com TTL
    cache = {
        "live": {"data": None, "ts": 0, "ttl": 25},     # cache live por 25s
        "stats": {}                                     # stats: fixture_id -> (data, ts)
    }

    await enviar("**BOT ATIVADO (modo protegido)**\nMonitorando partidas com controle de requisições.")

    while True:
        try:
            # checa daily usage e avisa se perto do limite
            used = get_usage_count()
            if used >= MAX_DAILY_REQUESTS:
                msg = f"⚠️ Limite diário de requisições atingido ({used}/{MAX_DAILY_REQUESTS}). Parando checagens até o próximo dia."
                print(msg)
                await enviar(msg)
                # dorme até meia-noite local (ou 3600s se preferir)
                # calcular segundos até o próximo dia
                now = datetime.now()
                tomorrow = datetime.combine(now.date(), datetime.min.time()) + timedelta(days=1)
                seconds_to_midnight = (tomorrow - now).total_seconds()
                # para simplicidade, dormimos 1 hora antes de re-checar
                await asyncio.sleep(3600)
                continue
            # obtém fixtures ao vivo (cache)
            now_ts = time.time()
            if not cache["live"]["data"] or now_ts - cache["live"]["ts"] > cache["live"]["ttl"]:
                url_live = "https://v3.football.api-sports.io/fixtures"
                params = {"live": "all"}
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Checando partidas ao vivo...")
                live_json = await safe_get(url_live, headers=headers, params=params)
                cache["live"]["data"] = live_json
                cache["live"]["ts"] = now_ts
            else:
                live_json = cache["live"]["data"]

            # percorre partidas
            candidates = []
            for jogo in live_json.get('response', []):
                minute = jogo['fixture']['status'].get('elapsed')
                # regra: só entre 15 e 30
                if not minute or not (15 <= minute <= 30):
                    continue
                # ignora se já houve gol
                if jogo['goals']['home'] or jogo['goals']['away']:
                    continue
                fid = jogo['fixture']['id']
                # ignora se já alertado
                if fid in alerted_matches:
                    continue
                # tudo ok: adiciona candidato
                candidates.append(jogo)

            # limitar quantos stats vamos buscar essa iteração
            stats_requested = 0
            for jogo in candidates:
                if stats_requested >= MAX_STATS_PER_LOOP:
                    break

                fid = jogo['fixture']['id']
                # checar cache local de stats (TTL 40s)
                st = cache["stats"].get(fid)
                if st and (time.time() - st[1] < 40):
                    stats_json = st[0]
                else:
                    # busca estatísticas
                    url_stats = "https://v3.football.api-sports.io/fixtures/statistics"
                    params = {"fixture": fid}
                    try:
                        stats_json = await safe_get(url_stats, headers=headers, params=params)
                    except RuntimeError as e:
                        print(f"[ERROR] Falha ao buscar estatísticas para fixture {fid}: {e}")
                        # se falhar, pula esse jogo (sem spam)
                        continue
                    cache["stats"][fid] = (stats_json, time.time())
                    # espera um pouco para evitar bursts
                    await asyncio.sleep(REQUEST_DELAY)
                    stats_requested += 1

                if not stats_json.get('response'):
                    continue

                s = stats_json['response']
                if len(s) < 2:
                    continue

                home_stats, away_stats = s[0]['statistics'], s[1]['statistics']

                def get_val(stats_list, tipo):
                    return next((x['value'] for x in stats_list if x['type'] == tipo), 0)

                shots_h = get_val(home_stats, 'Shots on Goal') or 0
                shots_a = get_val(away_stats, 'Shots on Goal') or 0
                corners_h = get_val(home_stats, 'Corner Kicks') or 0
                corners_a = get_val(away_stats, 'Corner Kicks') or 0
                try:
                    xg_h = float(get_val(home_stats, 'expected_goals') or 0)
                    xg_a = float(get_val(away_stats, 'expected_goals') or 0)
                except Exception:
                    xg_h = xg_a = 0.0

                prob = (xg_h + xg_a + (shots_h + shots_a) / 10 + (corners_h + corners_a) / 20) / 2
                if prob >= 0.85:
                    msg = f"""**🚨 OVER 0.5 HT ALERTA**
**{jogo['teams']['home']['name']} x {jogo['teams']['away']['name']}**
⏱ {jogo['fixture']['status'].get('elapsed', '?')}' | 0-0
**Chutes:** {shots_h}/{shots_a} | **Escanteios:** {corners_h}/{corners_a}
**xG:** {xg_h:.2f}/{xg_a:.2f} | **Prob:** {prob*100:.0f}%
**ENTRE AGORA! 🔥**"""
                    await enviar(msg)
                    print("✅ ALERTA ENVIADO!")
                    alerted_matches.add(fid)

            # evita loop agressivo
            await asyncio.sleep(LOOP_SLEEP)

        except RuntimeError as e:
            # erros controlados (ex: limite diário)
            print(f"[RuntimeError] {e}")
            # se for autorização, pausa longa
            if "Autorização" in str(e) or "Autorização" in repr(e):
                await asyncio.sleep(600)
            else:
                await asyncio.sleep(60)
        except Exception as e:
            print(f"Erro no loop principal: {e}")
            await asyncio.sleep(60)

if __name__ == '__main__':
    print("🚀 Iniciando Flask server...")
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    time.sleep(2)
    print("✅ Flask iniciado! Iniciando bot protegido...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Encerrando...")
