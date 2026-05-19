import os
import asyncio
import re
import json
import urllib.request
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

load_dotenv()

API_ID        = int(os.getenv("API_ID"))
API_HASH      = os.getenv("API_HASH")
SESSION       = os.getenv("SESSION_STRING")
TARGET        = int(os.getenv("TARGET_GROUP"))
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
URL_PATTERN = re.compile(r'https?://[^\s]+')

PLATFORM_HINTS = {
    "youtube.com": "YouTube", "youtu.be": "YouTube",
    "instagram.com": "Instagram", "twitter.com": "Twitter/X",
    "x.com": "Twitter/X", "tiktok.com": "TikTok",
    "facebook.com": "Facebook", "t.me": "Telegram",
    "linkedin.com": "LinkedIn", "github.com": "GitHub",
}

def detect_platform(url):
    for domain, name in PLATFORM_HINTS.items():
        if domain in url:
            return name
    return "Site/Artigo"

def analyze(url, platform):
    try:
        prompt = f"""Analise este link em português brasileiro e responda em dois blocos:

URL: {url}
Plataforma: {platform}

---CONTEUDO---
- O que é? Sobre o que trata?
- Quem produziu? Credibilidade?
- Mensagem principal e pontos relevantes
- Vale a pena consumir? Por quê?

---TECNICO---
- Estrutura e formato do conteúdo
- Se for sistema/app/bot: lógica por trás
- Prompt para replicar com IA
- Stack tecnológica provável
- Oportunidades de melhoria"""

        payload = json.dumps({
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "messages": [{"role": "user", "content": prompt}]
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "HTTP-Referer": "https://t.me",
                "X-Title": "BOT GLOBAL"
            }
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        full = data["choices"][0]["message"]["content"].strip()

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

    text = event.message.text or ""
    urls = URL_PATTERN.findall(text)
    if not urls:
        return

    url = urls[0]
    platform = detect_platform(url)
    aguarde = await event.reply(f"🔍 Analisando `{platform}`... aguarde.")

    resultado = await asyncio.get_event_loop().run_in_executor(None, analyze, url, platform)

    await aguarde.delete()
    await event.reply(
        f"📋 *ANÁLISE DE CONTEÚDO*\n🔗 {platform}\n━━━━━━━━━━━━━━━━━━━━\n\n{resultado['conteudo']}",
        parse_mode="markdown"
    )
    await asyncio.sleep(1)
    await event.reply(
        f"⚙️ *ANÁLISE TÉCNICA & LÓGICA*\n━━━━━━━━━━━━━━━━━━━━\n\n{resultado['tecnico']}",
        parse_mode="markdown"
    )

async def main():
    await client.start()
    print(f"✅ BOT GLOBAL ativo — monitorando grupo {TARGET}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
