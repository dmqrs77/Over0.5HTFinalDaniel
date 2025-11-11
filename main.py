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
    print("✅ Bot iniciado... aguardando mensagens.")
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    # Inicia o bot (o run_polling já gerencia o loop)
    await application.run_polling()

if __name__ == "__main__":
    # Corrigido: roda o loop existente (sem erro de event loop duplicado)
    asyncio.get_event_loop().run_until_complete(main())

