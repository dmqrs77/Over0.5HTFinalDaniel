import os
import requests
import asyncio
import nest_asyncio
from datetime import datetime
from telegram import Bot
from flask import Flask, Response
from threading import Thread
import time

nest_asyncio.apply()

TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_FOOTBALL_KEY")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

bot = Bot(token=TOKEN) if TOKEN else None

app = Flask(__name__)

@app.route('/')
def home():
    return Response("Bot online", status=200, mimetype='text/plain')

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

async def enviar(msg):
    if not bot:
        print("⚠️ Bot não configurado. Configure TELEGRAM_TOKEN nos Secrets.")
        return
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")

async def main():
    if not TOKEN or not API_KEY or not CHAT_ID:
        print("⚠️ CONFIGURAÇÃO NECESSÁRIA:")
        print("Configure os seguintes Secrets no Replit:")
        print("- TELEGRAM_TOKEN (token do seu bot)")
        print("- API_FOOTBALL_KEY (chave da API Football)")
        print("- CHAT_ID (ID do seu chat/canal)")
        print("\n✅ Servidor Flask rodando. Configure os Secrets para ativar o bot.")
        while True:
            await asyncio.sleep(60)
        return

    await enviar("**BOT ATIVADO COM DADOS REAIS!**\nMonitorando 15'-30' para Over 0.5 HT... ⚽️")

    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": "v3.football.api-sports.io"
    }

    alerted_matches = set()

    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Checando partidas...")
            live = requests.get("https://v3.football.api-sports.io/fixtures?live=all", headers=headers, timeout=10).json()

            for jogo in live.get('response', []):
                minute = jogo['fixture']['status'].get('elapsed')
                if not minute or not (15 <= minute <= 30):
                    continue
                if jogo['goals']['home'] or jogo['goals']['away']:
                    continue

                fid = jogo['fixture']['id']
                
                if fid in alerted_matches:
                    continue

                stats = requests.get(f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fid}", headers=headers, timeout=10).json()
                if not stats.get('response'):
                    continue

                s = stats['response']
                if len(s) < 2:
                    continue

                home_stats, away_stats = s[0]['statistics'], s[1]['statistics']

                def get(stats, tipo):
                    return next((x['value'] for x in stats if x['type'] == tipo), 0)

                shots_h = get(home_stats, 'Shots on Goal') or 0
                shots_a = get(away_stats, 'Shots on Goal') or 0
                corners_h = get(home_stats, 'Corner Kicks') or 0
                corners_a = get(away_stats, 'Corner Kicks') or 0
                xg_h = float(get(home_stats, 'expected_goals') or 0)
                xg_a = float(get(away_stats, 'expected_goals') or 0)

                prob = (xg_h + xg_a + (shots_h + shots_a) / 10 + (corners_h + corners_a) / 20) / 2
                if prob >= 0.85:
                    msg = f"""**🚨 OVER 0.5 HT ALERTA**
**{jogo['teams']['home']['name']} x {jogo['teams']['away']['name']}**
⏱ {minute}' | 0-0
**Chutes:** {shots_h}/{shots_a} | **Escanteios:** {corners_h}/{corners_a}
**xG:** {xg_h:.2f}/{xg_a:.2f} | **Prob:** {prob*100:.0f}%
**ENTRE AGORA! 🔥**"""
                    await enviar(msg)
                    print("✅ ALERTA ENVIADO!")
                    alerted_matches.add(fid)

            await asyncio.sleep(60)

        except Exception as e:
            print(f"Erro no loop: {e}")
            await asyncio.sleep(60)

if __name__ == '__main__':
    print("🚀 Iniciando Flask server...")
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    time.sleep(2)
    print("✅ Flask iniciado! Iniciando bot...")
    
    asyncio.run(main())