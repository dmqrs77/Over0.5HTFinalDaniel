import os
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler
import asyncio

# Lê o token e o chat_id do ambiente (seguro)
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TOKEN)

async def start(update, context):
    await update.message.reply_text("✅ Bot iniciado e funcionando!")

async def main():
    print("🤖 Bot iniciado... aguardando mensagens.")
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
