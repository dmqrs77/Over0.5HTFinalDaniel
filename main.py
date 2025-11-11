import os
import asyncio
import requests
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🔐 Tokens e variáveis (vindos do Render → Environment)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

# Inicializa o bot
bot = Bot(token=TELEGRAM_TOKEN)

# Comando /start
async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot iniciado e funcionando corretamente!")

# Exemplo simples de função automática
async def enviar_mensagem_auto():
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🤖 Bot foi iniciado com sucesso no Render!")
    except Exception as e:
        print(f"⚠️ Erro ao enviar mensagem automática: {e}")

# Função principal
async def main():
    print("🤖 Bot iniciado... aguardando mensagens.")

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    # Envia mensagem automática assim que o bot sobe
    await enviar_mensagem_auto()

    # Mantém o bot rodando
    await application.run_polling()

# Evita erro de “event loop already running”
if __name__ == "__main__":
    async def start():
        await main()

    try:
        asyncio.run(start())
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(start())
