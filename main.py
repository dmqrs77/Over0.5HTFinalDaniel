import os
import asyncio
import requests
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🔐 Variáveis de ambiente (Render → Environment)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # opcional, só se quiser enviar mensagens automáticas
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot iniciado e funcionando!")

async def jogos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para buscar jogos de futebol"""
    url = "https://api.football-data.org/v4/matches"
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        data = response.json()

        if "matches" in data and len(data["matches"]) > 0:
            msg = "⚽ Próximos jogos:\n\n"
            for match in data["matches"][:5]:  # mostra só 5 jogos
                casa = match["homeTeam"]["name"]
                fora = match["awayTeam"]["name"]
                hora = match["utcDate"].replace("T", " ").replace("Z", "")
                msg += f"🏟️ {casa} x {fora}\n🕒 {hora}\n\n"
        else:
            msg = "Nenhum jogo encontrado."
    except Exception as e:
        msg = f"Erro ao buscar jogos: {e}"

    await update.message.reply_text(msg)

async def enviar_mensagem_auto():
    """Exemplo: enviar uma mensagem automática ao iniciar o bot"""
    if CHAT_ID:
        await bot.send_message(chat_id=CHAT_ID, text="🤖 Bot foi iniciado com sucesso no Render!")

async def main():
    print("🤖 Bot iniciado... aguardando mensagens.")
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("jogos", jogos))

    # Envia mensagem automática (opcional)
    await enviar_mensagem_auto()

    # Mantém o bot rodando
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
