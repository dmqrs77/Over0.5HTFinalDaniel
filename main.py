import os
import time
import requests
import nest_asyncio
from bs4 import BeautifulSoup
from flask import Flask
from telegram import Bot

# Evita conflito de loop assíncrono
nest_asyncio.apply()

# Configurações do bot via variáveis de ambiente
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

LOOP_SLEEP = int(os.getenv("LOOP_SLEEP", 25))
MIN_MIN = int(os.getenv("MIN_MIN", 10))
MAX_MIN = int(os.getenv("MAX_MIN", 25))
MIN_SHOTS_TOTAL = int(os.getenv("MIN_SHOTS_TOTAL", 2))
MIN_CORNERS_TOTAL = int(os.getenv("MIN_CORNERS_TOTAL", 2))
MIN_XG_TOTAL = float(os.getenv("MIN_XG_TOTAL", 0.9))
MIN_DANGEROUS = int(os.getenv("MIN_DANGEROUS_ATTACKS", 15))
MIN_MOMENTUM = int(os.getenv("MIN_MOMENTUM_PCT", 60))
HISTORY_N = int(os.getenv("HISTORY_N", 5))
HISTORY_MIN_3PLUS = int(os.getenv("HISTORY_MIN_3PLUS", 3))

PRIMARY_URL = os.getenv("PRIMARY_URL", "https://seu-app.onrender.com")

bot = Bot(token=TELEGRAM_TOKEN)
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot rodando no Render!"


def get_match_data():
    try:
        url = "https://www.flashscore.com/match/"
        html = requests.get(url).text

        # 🚨 TROQUEI AQUI: removido "lxml"
        soup = BeautifulSoup(html, "html.parser")

        # Seu scraping aqui…
        return {}
    except Exception as e:
        print("Erro ao obter dados:", e)
        return None


def loop_bot():
    print("Loop iniciado…")
    while True:
        data = get_match_data()
        if data:
            bot.send_message(chat_id=CHAT_ID, text="⚽ Bot está funcionando!")
        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    from threading import Thread

    # Thread para o loop do bot
    t = Thread(target=loop_bot)
    t.daemon = True
    t.start()

    # Inicializa o servidor web
    app.run(host="0.0.0.0", port=10000)

