import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do Render (ou .env local)
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")
CHAT_ID = os.getenv("CHAT_ID")

# Função para comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot está ativo e funcionando!")

# Função para enviar mensagem automática ao iniciar
async def enviar_mensagem_auto(application):
    try:
        if not CHAT_ID:
            print("⚠️ Erro: CHAT_ID está vazio.")
            return
        await application.bot.send_message(chat_id=CHAT_ID, text="🤖 Bot foi iniciado com sucesso no Render!")
        print("✅ Mensagem de inicialização enviada com sucesso!")
    except Exception as e:
        print(f"⚠️ Erro ao enviar mensagem automática: {e}")

# Função principal
async def main():
    print("🤖 Bot iniciado... aguardando mensagens.")

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Adiciona comando /start
    application.add_handler(CommandHandler("start", start))

    # Envia mensagem inicial (sem travar o polling)
    asyncio.create_task(enviar_mensagem_auto(application))

    # Inicia o polling (loop principal)
    await application.run_polling()

# Executa o bot corretamente no Render
if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
