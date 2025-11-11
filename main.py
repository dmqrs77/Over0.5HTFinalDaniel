from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler

TOKEN = "SEU_TOKEN_AQUI"
CHAT_ID = "SEU_CHAT_ID_AQUI"

async def start(update, context):
    await update.message.reply_text("Bot iniciado e funcionando!")

async def main():
    print("✅ Bot iniciado... aguardando mensagens.")
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    await application.run_polling()

if _name_ == "_main_":
    import asyncio
    try:
        # Tenta criar e usar o novo loop explicitamente (compatível com Python 3.13)
        asyncio.run(main())
    except RuntimeError:
        # Se já houver um loop rodando, usa o existente
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
