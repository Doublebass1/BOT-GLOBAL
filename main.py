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
TARGET      = int(os.getenv("TARGET_GROUP"))  # -5195322872
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
 
def analyze_link(url: str, platform: str) -> dict:
    try:
        prompt = f"""Você é um analista especialista. Analise este link:
 
URL: {url}
Plataforma: {platform}
 
Responda em dois blocos separados:
 
---CONTEUDO---
Faça uma análise rica do conteúdo:
- O que é este conteúdo? Sobre o que trata?
- Quem produziu? Qual o perfil/credibilidade?
- Qual a mensagem principal?
- Pontos mais relevantes
- Vale a pena consumir? Por quê?
 
---TECNICO---
Faça uma análise técnica e lógica:
- Estrutura e formato do conteúdo
- Se for um sistema/app/bot: qual a lógica por trás?
- Prompt detalhado para replicar com IA
- Stack tecnológica provável
- Oportunidades de melhoria ou expansão"""
 
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
 
        full = response.content[0].text.strip()
 
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
    # Só responde no grupo TARGET
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
 
    resultado = analyze_link(url, platform)
 
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