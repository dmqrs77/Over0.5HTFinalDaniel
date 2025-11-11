from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler
import asyncio

TOKEN = "SEU_TOKEN_AQUI"
CHAT_ID = "SEU_CHAT_ID_AQUI"

async def start(update, context):
    await update.message.reply_text("Bot iniciado e funcionando!")

async def main():
    print("✅ Bot iniciado... aguardando mensagens.")
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    await application.run_polling()

if __name__ == "__main__":
    try:
        # Tenta rodar normalmente
        asyncio.run(main())
    except RuntimeError as e:
        # Caso o Render já tenha um loop ativo, usa o existente
        if "already running" in str(e) or "no current event loop" in str(e):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(main())
        else:
            raise

