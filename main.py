import asyncio
import requests
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🧩 Coloque seu token e chat_id aqui
TOKEN = "SEU_TOKEN_AQUI"
CHAT_ID = "SEU_CHAT_ID_AQUI"

# Inicializa o bot
bot = Bot(token=TOKEN)

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot iniciado e funcionando!")

# Função principal
async def main():
    print("✅ Bot iniciado... aguardando mensagens.")
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    # Mantém o bot rodando continuamente
    await application.run_polling()

if _name_ == "_main_":
    asyncio.run(main())