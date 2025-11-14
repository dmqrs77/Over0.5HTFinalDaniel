import os
import time
import requests
import nest_asyncio
from flask import Flask
from telegram import Bot
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup

# Evita problemas de loop async
nest_asyncio.apply()

# Flask app para manter online
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot rodando!"

# Variáveis de ambiente
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
LOOP_SLEEP = int(os.getenv("LOOP_SLEEP", 25))

bot = Bot(token=TELEGRAM_TOKEN)

########################################
# LOGICA DO SCRAPER
########################################

def get_live_matches():
    url = "https://www.soccerstats.com/matches.asp?matchday=1"
    html = requests.get(url, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")

    games = []

    rows = soup.select("table#btable tbody tr")

    for r in rows:
        cols = r.find_all("td")
        if len(cols) < 5:
            continue

        try:
            minute = cols[0].text.strip()
            home = cols[1].text.strip()
            away = cols[3].text.strip()
            score = cols[2].text.strip()

            games.append({
                "minute": minute,
                "home": home,
                "away": away,
                "score": score
            })
        except:
            pass

    return games

########################################
# ROTINA PRINCIPAL
########################################

def bot_loop():
    print("Rodando varredura...")

    matches = get_live_matches()

    for m in matches:
        try:
            minute = m["minute"]

            # Exemplo: detectar apenas minutos entre 10 e 25
            if "'" in minute:
                min_now = int(minute.replace("'", ""))
                if 10 <= min_now <= 25:

                    msg = (
                        f"⚽ *Jogo Encontrado*\n"
                        f"{m['home']} x {m['away']}\n"
                        f"Minuto: {minute}\n"
                        f"Placar: {m['score']}"
                    )

                    bot.send_message(
                        chat_id=CHAT_ID,
                        text=msg,
                        parse_mode="Markdown"
                    )

        except Exception as e:
            print("Erro enviando jogo:", e)

########################################
# SCHEDULER
########################################

scheduler = BackgroundScheduler()
scheduler.add_job(bot_loop, "interval", seconds=LOOP_SLEEP)
scheduler.start()

########################################
# START
########################################
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
