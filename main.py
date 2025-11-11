import asyncio
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler

TOKEN = "8003772292:AAEDp-Hwr51tjuWjswqyNt7HnijYufui5aI"
CHAT_ID = "436309150"

bot = Bot(token=TOKEN)

async def start(update, context):
    await update.message.reply_text("✅ Bot iniciado e funcionando!")

async def main():
    print("✅ Bot iniciado... aguardando mensagens.")
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    # Mantém o bot rodando
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        # Se o loop já estiver rodando (erro comum no Render/Python 3.13)
        if "already running" in str(e) or "Cannot close a running event loop" in str(e):
            loop = asyncio.get_event_loop()
            loop.create_task(main())
            loop.run_forever()
        else:
            raise

