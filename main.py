import asyncio
import os
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Carrega variáveis do Render (.env)
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")

# ==================== FUNÇÕES ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start no Telegram"""
    await update.message.reply_text("🤖 Bot ativo e rodando no Render!")


async def testar_api_football():
    """Faz uma requisição simples para testar a API"""
    if not FOOTBALL_API_KEY:
        return "⚠️ API key não configurada!"

    url = "https://api.football-data.org/v4/competitions"
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    total = len(data.get("competitions", []))
                    return f"✅ API Football-Data está funcionando! ({total} competições retornadas)"
                else:
                    return f"❌ Erro na API Football-Data: HTTP {resp.status}"
    except Exception as e:
        return f"⚠️ Erro ao testar API: {e}"


async def enviar_mensagem_inicial(application):
    """Envia mensagem automática ao iniciar o bot"""
    if not CHAT_ID:
        print("⚠️ CHAT_ID não configurado.")
        return

    try:
        # Testa a API antes de avisar o usuário
        resultado_api = await testar_api_football()

        await application.bot.send_message(
            chat_id=CHAT_ID,
            text=f"🚀 Bot iniciado com sucesso no Render!\n\n{resultado_api}"
        )
        print("✅ Mensagem inicial enviada.")
    except Exception as e:
        print(f"⚠️ Erro ao enviar mensagem automática: {e}")


# ==================== LOOP PRINCIPAL ====================

async def main():
    print("🤖 Iniciando bot...")

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    # Envia mensagem inicial em segundo plano
    asyncio.create_task(enviar_mensagem_inicial(application))

    await application.initialize()
    await application.start()
    print("✅ Bot conectado ao Telegram.")

    # Inicia polling sem fechar o loop
    await application.updater.start_polling()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
