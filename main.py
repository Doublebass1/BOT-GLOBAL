import os
import asyncio
import re
import json
import time
import urllib.request
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

load_dotenv()

API_ID   = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION  = os.getenv("SESSION_STRING")
TARGET   = int(os.getenv("TARGET_GROUP"))

GEMINI_KEYS = []
for i in range(1, 6):
    k = os.getenv(f"GEMINI_KEY_{i}")
    if k:
        GEMINI_KEYS.append(k)

print(f"🔑 {len(GEMINI_KEYS)} chaves Gemini carregadas")
current_key_index = 0

def get_next_key():
    global current_key_index
    key = GEMINI_KEYS[current_key_index % len(GEMINI_KEYS)]
    current_key_index += 1
    return key

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

def gemini_analyze(url, platform):
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

    for tentativa in range(len(GEMINI_KEYS)):
        key = get_next_key()
        try:
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}]
            }).encode("utf-8")

            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
            req = urllib.request.Request(api_url, data=payload, headers={"Content-Type": "application/json"})

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
            if "429" in str(e):
                print(f"⚠️ Chave {tentativa+1} com limite, tentando próxima...")
                time.sleep(3)
                continue
            return {"conteudo": f"Erro: {e}", "tecnico": f"Erro: {e}"}

    return {"conteudo": "⏳ Limite atingido. Tente em 1 minuto.", "tecnico": "⏳ Limite atingido. Tente em 1 minuto."}

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

    resultado = await asyncio.get_event_loop().run_in_executor(None, gemini_analyze, url, platform)

    await aguarde.delete()
    await event.reply(
        f"📋 *ANÁLISE DE CONTEÚDO*\n🔗 {platform}\n━━━━━━━━━━━━━━━━━━━━\n\n{resultado['conteudo']}",
        parse_mode="markdown"
    )
    await asyncio.sleep(2)
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
