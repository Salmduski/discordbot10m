import os
import discord
import re
import requests
import threading

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_IDS = [int(cid.strip()) for cid in os.getenv("CHANNEL_ID", "1234567890").split(",")]
WEBHOOK_URLS = [url.strip() for url in os.getenv("WEBHOOK_URLS", "").split(",") if url.strip()]
BACKEND_URL = os.getenv("BACKEND_URL")

client = discord.Client()  # No intents!

def clean_field(text):
    """Remove markdown formatting and extra whitespace"""
    if not text:
        return text
    # Remove ** bold formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    # Remove * italic formatting  
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    # Remove code block formatting (```...```)
    text = re.sub(r'^`{3}(.*?)`{3}$', r'\1', text, flags=re.DOTALL)
    # Remove single backticks
    text = re.sub(r'`([^`]*)`', r'\1', text)
    return text.strip()

def parse_info_from_embed(message):
    """Parse info from Discord embed fields (supports your screenshot style)"""
    # Only process the first embed, as in your screenshot
    if not message.embeds or not hasattr(message.embeds[0], 'fields'):
        return {"name": None, "money": None, "players": None, "jobid": None}
    embed = message.embeds[0]
    field_map = {}
    for field in embed.fields:
        key = field.name.strip().lower()
        value = clean_field(field.value)
        field_map[key] = value

    name = field_map.get("🏷️ name") or field_map.get("name")
    money = field_map.get("💰 money per sec") or field_map.get("money per sec")
    players = field_map.get("👥 players") or field_map.get("players")
    jobid = (field_map.get("job id (pc)") or 
             field_map.get("🆔 job id (pc)") or 
             field_map.get("job id") or 
             field_map.get("🆔 job id"))
    if jobid:
        jobid = jobid.replace("`", "").replace("\n", "").strip()

    return {
        "name": name,
        "money": money,
        "players": players,
        "jobid": jobid
    }

def build_embed(info):
    fields = []
    if info["name"]:
        fields.append({
            "name": "🏷️ Name",
            "value": f"**{info['name']}**",
            "inline": False
        })
    if info["money"]:
        fields.append({
            "name": "💰 Money per sec",
            "value": f"**{info['money']}**",
            "inline": True
        })
    if info["players"]:
        fields.append({
            "name": "👥 Players",
            "value": f"**{info['players']}**",
            "inline": True
        })
    if info["jobid"]:
        fields.append({
            "name": "🆔 Job ID (PC)",
            "value": f"```{info['jobid']}```",
            "inline": False
        })

    embed = {
        "title": "Brainrot Notify | notasnek",
        "color": 0x8e44ad,  # purple
        "fields": fields,
        "footer": {"text": "Made by notasnek"}
    }
    return {"embeds": [embed]}

def send_to_webhooks(payload):
    def send(url, payload):
        try:
            response = requests.post(url, json=payload, timeout=10)
            print("✅ Webhook sent" if response.status_code in [200,204] else f"❌ Webhook error {response.status_code}")
        except Exception as e:
            print(f"❌ Webhook exception: {e}")
    threads = []
    for url in WEBHOOK_URLS:
        t = threading.Thread(target=send, args=(url, payload))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

def send_to_backend(info):
    if not info["name"] or not info["jobid"]:
        print("Skipping backend send - missing name or jobid")
        return
    payload = {
        "name": info["name"],
        "moneyPerSec": info["money"] or "",
        "jobId": info["jobid"],
        "instanceId": info["jobid"],
        "players": info["players"] or ""
    }
    try:
        response = requests.post(BACKEND_URL, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Sent to backend: {info['name']}")
        elif response.status_code == 429:
            print(f"⚠️ Rate limited for backend: {info['name']}")
        else:
            print(f"❌ Backend error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Failed to send to backend: {e}")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    print(f'Configured to send to {len(WEBHOOK_URLS)} webhook(s)')

@client.event
async def on_message(message):
    if message.channel.id not in CHANNEL_IDS:
        return

    info = parse_info_from_embed(message)
    print("Parsed info:", info)
    if info["name"] and info["money"] and info["players"] and info["jobid"]:
        embed_payload = build_embed(info)
        send_to_webhooks(embed_payload)
        send_to_backend(info)
        print(f"✅ Sent embed and backend for: {info['name']}")
    else:
        print("⚠️ Missing required fields. Skipping.")

client.run(TOKEN)
