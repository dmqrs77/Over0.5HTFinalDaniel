import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🔒 Pegando TOKEN e CHAT_ID do ambiente do Render
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Função /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot iniciado e funcionando!")

# Função principal
async def main():
    print("🤖 Bot iniciado... aguardando mensagens.")
    application = ApplicationBuilder().token(TOKEN).build()

    # Adiciona comandos
    application.add_handler(CommandHandler("start", start))

    # Mantém o bot rodando
    await application.run_polling()

# Proteção contra o erro do Render (loop já em execução)
if __name__ == "__main__":
    try:
        # Verifica se já existe um loop ativo
        asyncio.get_running_loop()
        asyncio.ensure_future(main())
    except RuntimeError:
        # Se não existir, cria um novo loop
        asyncio.run(main())
