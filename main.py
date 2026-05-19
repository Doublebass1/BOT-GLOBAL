import os
import asyncio
import re
import json
import urllib.request
import urllib.parse
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

load_dotenv()

API_ID      = int(os.getenv("API_ID"))
API_HASH    = os.getenv("API_HASH")
SESSION     = os.getenv("SESSION_STRING")
TARGET      = int(os.getenv("TARGET_GROUP"))
GEMINI_KEY  = os.getenv("GEMINI_API_KEY")

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

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

def gemini_analyze(url: str, platform: str) -> dict:
    try:
        prompt = f"""Você é um analista especialista. Analise este link:

URL: {url}
Plataforma: {platform}

Responda em dois blocos separados:

---CONTEUDO---
Análise rica do conteúdo:
- O que é? Sobre o que trata?
- Quem produziu? Credibilidade?
- Mensagem principal e pontos relevantes
- Vale a pena consumir? Por quê?

---TECNICO---
Análise técnica e lógica:
- Estrutura e formato do conteúdo
- Se for sistema/app/bot: lógica por trás
- Prompt detalhado para replicar com IA
- Stack tecnológica provável
- Oportunidades de melhoria ou expansão"""

        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}]
        }).encode("utf-8")

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"

        req = urllib.request.Request(
            api_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        full = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        if "---CONTEUDO---" in full and "---TECNICO---" in full:
            parts = full.split("---TECNICO---")
            conteudo = parts[0].replace("---CONTEUDO---", "").strip()
            tecnico = parts[1].strip()
        else:
            conteudo = full
            tecnico = "Análise técnica não disponível."

        return {"conteudo": conteudo, "tecnico": tecnico}

    except Exception as e:
        return {"conteudo": f"Erro: {e}", "tecnico": f"Erro: {e}"}

@client.on(events.NewMessage)
async def handler(event):
    if event.chat_id != TARGET:
        return

    msg  = event.message
    text = msg.text or ""

    urls = URL_PATTERN.findall(text)
    if not urls:
        return

    url = urls[0]
    platform = detect_platform(url)

    aguarde = await event.reply(f"🔍 Analisando `{platform}`... aguarde.")

    resultado = gemini_analyze(url, platform)

    msg_conteudo = (
        f"📋 *ANÁLISE DE CONTEÚDO*\n"
        f"🔗 {platform}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{resultado['conteudo']}"
    )

    msg_tecnico = (
        f"⚙️ *ANÁLISE TÉCNICA & LÓGICA*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{resultado['tecnico']}"
    )

    await aguarde.delete()
    await event.reply(msg_conteudo, parse_mode="markdown")
    await asyncio.sleep(1)
    await event.reply(msg_tecnico, parse_mode="markdown")

async def main():
    await client.start()
    print(f"✅ BOT GLOBAL ativo — monitorando grupo {TARGET}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
