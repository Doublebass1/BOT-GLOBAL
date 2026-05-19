import os
import asyncio
import re
import json
import requests
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

load_dotenv()
API_ID          = int(os.getenv("API_ID"))
API_HASH        = os.getenv("API_HASH")
SESSION         = os.getenv("SESSION_STRING")
TARGET          = int(os.getenv("TARGET_GROUP"))
GROQ_KEY        = os.getenv("GROQ_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

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
    """Extrai metadados do YouTube via API oficial."""
    try:
        match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
        if not match:
            return {"error": "ID do vídeo não encontrado na URL"}

        video_id = match.group(1)
        api_key  = os.getenv("YOUTUBE_API_KEY")

        api_url = (
            f"https://www.googleapis.com/youtube/v3/videos"
            f"?id={video_id}&key={api_key}"
            f"&part=snippet,statistics,contentDetails"
        )
        resp = requests.get(api_url, timeout=10)
        data = resp.json()

        if not data.get("items"):
            return {"error": "Vídeo não encontrado na API do YouTube"}

        item    = data["items"][0]
        snippet = item["snippet"]
        stats   = item.get("statistics", {})
        details = item.get("contentDetails", {})

        return {
            "title":       snippet.get("title", "Sem título"),
            "channel":     snippet.get("channelTitle", "Desconhecido"),
            "description": snippet.get("description", "")[:2000],
            "tags":        ", ".join(snippet.get("tags", [])[:10]),
            "duration":    details.get("duration", "?"),
            "views":       stats.get("viewCount", "?"),
            "likes":       stats.get("likeCount", "?"),
            "upload_date": snippet.get("publishedAt", "")[:10],
            "transcript":  "",
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_site_info(url):
    """Tenta extrair texto básico de sites/artigos."""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        text = resp.text
        # Remove tags HTML básicas
        clean = re.sub(r'<[^>]+>', ' ', text)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean[:3000]
    except Exception as e:
        return f"Não foi possível acessar o site: {e}"


def call_groq(prompt):
    """Chama a API Groq com requests."""
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
    # Monta contexto de acordo com a plataforma
    if platform == "YouTube":
        info = fetch_video_info(url)
        if "error" in info:
            contexto = f"Não foi possível extrair metadados. URL: {url}\nErro: {info['error']}"
        else:
            contexto = f"""
Título: {info['title']}
Canal: {info['channel']}
Duração: {info['duration']} | Views: {info['views']} | Likes: {info['likes']}
Publicado em: {info['upload_date']}
Tags: {info['tags']}

Descrição:
{info['description']}
""".strip()
    else:
        conteudo_site = fetch_site_info(url)
        contexto = f"Conteúdo extraído do site:\n{conteudo_site}"

    prompt = f"""Você é um analista especialista. Analise o conteúdo abaixo em português brasileiro.
Responda em DOIS blocos separados exatamente pelo marcador ---TECNICO---

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
        parts    = full.split("---TECNICO---")
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
