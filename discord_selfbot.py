import os
import discord
import re
import requests
import threading

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_IDS = [int(cid.strip()) for cid in os.getenv("CHANNEL_ID", "1234567890").split(",")]
WEBHOOK_URLS = [url.strip() for url in os.getenv("WEBHOOK_URLS", "").split(",") if url.strip()]
BACKEND_URL = os.getenv("BACKEND_URL")

client = discord.Client()

def clean_field(text):
    if not text:
        return text
    # Remove bold, italic, and code formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'^`{3,}([^\n]*?)`{3,}$', r'\1', text, flags=re.DOTALL)
    text = text.replace('`', '').strip()
    return text

def parse_embed_fields(message):
    # Only process the first embed (your format)
    if not message.embeds or not hasattr(message.embeds[0], 'fields'):
        return None
    embed = message.embeds[0]
    fields = {f.name.strip().lower(): clean_field(f.value) for f in embed.fields}
    name = fields.get("🏷️ name") or fields.get("name")
    money = fields.get("💰 money per sec") or fields.get("money per sec")
    players = fields.get("👥 players") or fields.get("players")
    jobid = fields.get("🆔 job id (pc)") or fields.get("job id (pc)") or fields.get("job id")
    if jobid:
        jobid = jobid.replace("\n", "").strip()
    return dict(name=name, money=money, players=players, jobid=jobid)

def build_embed(info):
    fields = []
    if info["name"]:
        fields.append({"name": "🏷️ Name", "value": f"**{info['name']}**", "inline": False})
    if info["money"]:
        fields.append({"name": "💰 Money per sec", "value": f"**{info['money']}**", "inline": True})
    if info["players"]:
        fields.append({"name": "👥 Players", "value": f"**{info['players']}**", "inline": True})
    if info["jobid"]:
        fields.append({"name": "🆔 Job ID (PC)", "value": f"```{info['jobid']}```", "inline": False})
    return {
        "title": "Brainrot Notify | notasnek",
        "color": 0x8e44ad,
        "fields": fields,
        "footer": {"text": "Made by notasnek"}
    }

def send_to_webhooks(payload):
    def send(url, payload):
        try:
            r = requests.post(url, json={"embeds": [payload]}, timeout=10)
            print("✅ Webhook sent" if r.status_code in [200,204] else f"❌ Webhook error {r.status_code}")
        except Exception as e:
            print(f"❌ Webhook exception: {e}")
    for url in WEBHOOK_URLS:
        threading.Thread(target=send, args=(url, payload)).start()

def send_to_backend(info):
    # Your backend expects name, serverId, jobId. We'll use a constant serverId for these embed messages.
    server_id = "brainrot"
    if not info["name"] or not info["jobid"]:
        print("Skipping backend send - missing name or jobid")
        return
    payload = {
        "name": info["name"],
        "serverId": server_id,
        "jobId": info["jobid"]
    }
    try:
        r = requests.post(BACKEND_URL, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"✅ Sent to backend: {info['name']}")
        else:
            print(f"❌ Backend error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"❌ Failed to send to backend: {e}")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    print(f'Watching channels: {CHANNEL_IDS}')

@client.event
async def on_message(message):
    if message.channel.id not in CHANNEL_IDS:
        return
    info = parse_embed_fields(message)
    print("Parsed info:", info)
    if info and info["name"] and info["jobid"]:
        embed_payload = build_embed(info)
        send_to_webhooks(embed_payload)
        send_to_backend(info)
        print(f"✅ Sent embed and backend for: {info['name']}")
    else:
        print("⚠️ Missing required fields. Skipping.")

client.run(TOKEN)
