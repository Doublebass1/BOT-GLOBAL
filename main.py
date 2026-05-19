import os
import asyncio
import re
import json
import requests
import yt_dlp
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

load_dotenv()
API_ID   = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION  = os.getenv("SESSION_STRING")
TARGET   = int(os.getenv("TARGET_GROUP"))
GROQ_KEY = os.getenv("GROQ_API_KEY")

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


def fetch_video_info(url):
    """Extrai título, descrição e subtítulos do vídeo com yt-dlp."""
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "writesubtitles": False,
        "subtitleslangs": ["pt", "en"],
        "writeautomaticsub": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title       = info.get("title", "Sem título")
            description = info.get("description", "")[:1500]
            channel     = info.get("uploader", "Desconhecido")
            duration    = info.get("duration_string", "?")
            view_count  = info.get("view_count", 0)
            upload_date = info.get("upload_date", "")
            tags        = ", ".join(info.get("tags", [])[:10])

            # Tenta pegar transcrição automática
            transcript = ""
            subtitles = info.get("automatic_captions") or info.get("subtitles") or {}
            for lang in ["pt", "en"]:
                if lang in subtitles:
                    entries = subtitles[lang]
                    # Pega o formato json3 ou qualquer um disponível
                    for entry in entries:
                        if entry.get("ext") == "json3":
                            try:
                                r = requests.get(entry["url"], timeout=10)
                                data = r.json()
                                texts = [
                                    e.get("segs", [{}])[0].get("utf8", "")
                                    for e in data.get("events", [])
                                    if e.get("segs")
                                ]
                                transcript = " ".join(texts)[:3000]
                            except:
                                pass
                            break
                    if transcript:
                        break

            return {
                "title": title,
                "channel": channel,
                "duration": duration,
                "views": view_count,
                "upload_date": upload_date,
                "description": description,
                "tags": tags,
                "transcript": transcript,
            }
    except Exception as e:
        return {"error": str(e)}


def call_groq(prompt):
    """Chama a API Groq com requests (evita bloqueio Cloudflare)."""
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
            },
            timeout=30,
        )
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Erro ao chamar Groq: {e}"


def analyze(url, platform):
    # 1. Tenta extrair info real do vídeo
    info = fetch_video_info(url)

    if "error" in info:
        contexto = f"Não foi possível extrair o conteúdo diretamente. URL: {url}"
    else:
        contexto = f"""
Título: {info['title']}
Canal/Autor: {info['channel']}
Duração: {info['duration']} | Views: {info['views']} | Data: {info['upload_date']}
Tags: {info['tags']}

Descrição:
{info['description']}

Transcrição (parcial):
{info['transcript'] or 'Não disponível'}
""".strip()

    # 2. Monta prompt rico com o conteúdo real
    prompt = f"""Você é um analista especialista. Analise o conteúdo abaixo em português brasileiro e responda em DOIS blocos separados pelo marcador ---TECNICO---:

Plataforma: {platform}
URL: {url}

{contexto}

---CONTEUDO---
- O que é e sobre o que trata
- Quem produziu e credibilidade
- Mensagem principal e pontos mais relevantes
- Vale a pena consumir? Por quê?

---TECNICO---
- Estrutura e formato do conteúdo
- Se for sistema/app/bot: lógica por trás
- Prompt completo e detalhado para replicar com IA (pronto para usar)
- Stack tecnológica provável
- Oportunidades de melhoria"""

    full = call_groq(prompt)

    if "---TECNICO---" in full:
        parts = full.split("---TECNICO---")
        conteudo = parts[0].replace("---CONTEUDO---", "").strip()
        tecnico  = parts[1].strip()
    else:
        conteudo = full
        tecnico  = "Análise técnica não disponível."

    return {"conteudo": conteudo, "tecnico": tecnico}


@client.on(events.NewMessage)
async def handler(event):
    if event.chat_id != TARGET:
        return
    text = event.message.text or ""
    urls = URL_PATTERN.findall(text)
    if not urls:
        return

    url      = urls[0]
    platform = detect_platform(url)
    aguarde  = await event.reply(f"🔍 Analisando `{platform}`... aguarde.")

    resultado = await asyncio.get_event_loop().run_in_executor(
        None, analyze, url, platform
    )

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
