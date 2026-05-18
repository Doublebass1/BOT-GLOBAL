import os
import asyncio
import anthropic
import re
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

load_dotenv()

API_ID      = int(os.getenv("API_ID"))
API_HASH    = os.getenv("API_HASH")
SESSION     = os.getenv("SESSION_STRING")
TARGET      = int(os.getenv("TARGET_GROUP"))
CLAUDE_KEY  = os.getenv("ANTHROPIC_API_KEY")

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
claude = anthropic.Anthropic(api_key=CLAUDE_KEY)

URL_PATTERN = re.compile(r'https?://[^\s]+')

PLATFORM_HINTS = {
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "instagram.com": "Instagram",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "tiktok.com": "TikTok",
    "facebook.com": "Facebook",
    "t.me": "Telegram",
    "linkedin.com": "LinkedIn",
    "github.com": "GitHub",
}

def detect_platform(url: str) -> str:
    for domain, name in PLATFORM_HINTS.items():
        if domain in url:
            return name
    return "Site/Artigo"

def analyze_link(url: str, platform: str, context: str = "") -> dict:
    """Usa Claude para analisar o link em dois pareceres."""
    try:
        prompt = f"""Você é um analista especialista. Analise este link:

URL: {url}
Plataforma: {platform}
Contexto adicional: {context if context else "Nenhum"}

Responda em dois blocos separados:

---CONTEUDO---
Faça uma análise rica do conteúdo:
- O que é este conteúdo? Sobre o que trata?
- Quem produziu? Qual o perfil/credibilidade?
- Qual a mensagem principal?
- Pontos mais relevantes
- Contexto e importância
- Vale a pena consumir? Por quê?

---TECNICO---
Faça uma análise técnica e lógica:
- Estrutura e formato do conteúdo
- Métricas e dados relevantes (visualizações, engajamento se visível)
- Se for um sistema/app/bot: qual a lógica por trás? Como foi construído?
- Prompt detalhado para replicar ou desenvolver algo similar com IA
- Stack tecnológica provável
- Oportunidades de melhoria ou expansão

Use linguagem clara, objetiva e profissional. Seja específico e detalhado."""

        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        full = response.content[0].text.strip()

        conteudo = ""
        tecnico = ""

        if "---CONTEUDO---" in full and "---TECNICO---" in full:
            parts = full.split("---TECNICO---")
            conteudo = parts[0].replace("---CONTEUDO---", "").strip()
            tecnico = parts[1].strip()
        else:
            conteudo = full
            tecnico = "Análise técnica não disponível para este conteúdo."

        return {"conteudo": conteudo, "tecnico": tecnico}

    except Exception as e:
        return {
            "conteudo": f"Erro ao analisar: {e}",
            "tecnico": f"Erro ao analisar: {e}"
        }

@client.on(events.NewMessage(chats=TARGET))
async def handler(event):
    msg  = event.message
    text = msg.text or ""

    urls = URL_PATTERN.findall(text)
    if not urls:
        return

    url = urls[0]
    platform = detect_platform(url)

    # Mensagem de espera
    aguarde = await event.reply(f"🔍 Analisando link `{platform}`... aguarde alguns segundos.")

    # Analisa
    resultado = analyze_link(url, platform)

    conteudo = resultado["conteudo"]
    tecnico  = resultado["tecnico"]

    # Envia análise de conteúdo
    msg_conteudo = (
        f"📋 *ANÁLISE DE CONTEÚDO*\n"
        f"🔗 {platform} · `{url[:60]}{'...' if len(url) > 60 else ''}`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{conteudo}"
    )

    # Envia análise técnica
    msg_tecnico = (
        f"⚙️ *ANÁLISE TÉCNICA & LÓGICA*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{tecnico}"
    )

    # Remove mensagem de espera
    await aguarde.delete()

    # Envia os dois pareceres
    await event.reply(msg_conteudo, parse_mode="markdown")
    await asyncio.sleep(1)
    await event.reply(msg_tecnico, parse_mode="markdown")

async def main():
    await client.start()
    print("✅ BOT GLOBAL ativo — Analisador de links online")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
