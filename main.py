import os
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
from datetime import datetime

# Carrega as variáveis de ambiente
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")
CHAT_ID = os.getenv("CHAT_ID")

# === Funções do Bot ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot de futebol ativo! Use /jogos para ver partidas de hoje ⚽")

async def buscar_jogos_hoje():
    """Busca partidas de hoje usando a API-Football"""
    url = "https://v3.football.api-sports.io/fixtures"
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    headers = {"x-apisports-key": FOOTBALL_API_KEY}

    params = {"date": data_hoje, "league": "39", "season": "2025"}  # Exemplo: Premier League (39)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                return f"⚠️ Erro ao buscar jogos (status {response.status})"
            dados = await response.json()

    jogos = dados.get("response", [])
    if not jogos:
        return "⚽ Nenhum jogo encontrado para hoje."

    mensagem = f"📅 *Jogos de hoje ({data_hoje}):*\n\n"
    for jogo in jogos[:10]:  # limita a 10 pra não ficar muito longo
        casa = jogo["teams"]["home"]["name"]
        fora = jogo["teams"]["away"]["name"]
        hora = jogo["fixture"]["date"][11:16]
        mensagem += f"🕓 {hora} — {casa} 🆚 {fora}\n"

    return mensagem

async def jogos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /jogos"""
    await update.message.reply_text("⏳ Buscando partidas de hoje...")
    texto = await buscar_jogos_hoje()
    await update.message.reply_text(texto, parse_mode="Markdown")

async def enviar_mensagem_auto(application):
    """Mensagem automática ao iniciar"""
    try:
        if not CHAT_ID:
            print("⚠️ Erro: CHAT_ID está vazio.")
            return
        await application.bot.send_message(chat_id=CHAT_ID, text="🤖 Bot foi iniciado com sucesso no Render!")
        print("✅ Mensagem de inicialização enviada com sucesso!")
    except Exception as e:
        print(f"⚠️ Erro ao enviar mensagem automática: {e}")

# === Inicialização ===

async def main():
    print("🤖 Bot iniciado... aguardando mensagens.")

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Adiciona comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("jogos", jogos))

    # Envia mensagem inicial em background
    asyncio.create_task(enviar_mensagem_auto(application))

    # Inicia o polling
    await application.run_polling()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
