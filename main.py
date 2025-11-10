import requests
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler
import asyncio

TOKEN = "SEU_TOKEN_AQUI"
CHAT_ID = "SEU_CHAT_ID_AQUI"

# Inicializa o bot
bot = Bot(token=TOKEN)

async def start(update, context):
    await update.message.reply_text("Bot iniciado e funcionando!")

async def main():
    print("Bot iniciado... aguardando mensagens.")
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    # Mantém o bot rodando no modo polling
    await application.run_polling()

if _name_ == "_main_":
    asyncio.run(main())