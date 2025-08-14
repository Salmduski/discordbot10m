import os
import discord
import re
import requests
import threading

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_IDS = [int(cid.strip()) for cid in os.getenv("CHANNEL_ID", "1234567890").split(",")]
WEBHOOK_URLS = [url.strip() for url in os.getenv("WEBHOOK_URLS", "").split(",") if url.strip()]
BACKEND_URL = os.getenv("BACKEND_URL")

client = discord.Client()  # Selfbot, NO intents!

def clean_field(text):
    """Remove markdown formatting and extra whitespace"""
    if not text:
        return text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    return text.strip()

def get_message_full_content(message):
    parts = []
    embed_fields = {}
    # Message content
    if message.content and message.content.strip():
        parts.append(message.content)
    # Embeds
    for embed in getattr(message, "embeds", []):
        if getattr(embed, "title", None):
            parts.append(embed.title)
        if getattr(embed, "description", None):
            parts.append(embed.description)
        for field in getattr(embed, "fields", []):
            key = field.name.strip().replace(":", "").replace("(", "").replace(")", "").replace("/", "").replace(" ", "").lower()
            embed_fields[key] = field.value.strip()
            parts.append(f"{field.name}\n{field.value}")
    # Attachments
    for att in getattr(message, "attachments", []):
        parts.append(att.url)
    return "\n".join(parts) if parts else "(no content)", embed_fields

def parse_info(msg, embed_fields=None):
    embed_fields = embed_fields or {}
    def ef(keys):
        for key in keys:
            k = key.lower()
            for ek, ev in embed_fields.items():
                if ek == k:
                    return ev
        return None

    # Try embed fields first
    name = ef(["name", "brainrotname", "🏷️name"])
    money = ef(["moneypersec", "moneymoneypersec", "💰moneypersec"])
    players = ef(["players", "playersplayers", "👥players"])
    jobid_mobile = ef(["idmobile", "phoneidmobile", "🆔idmobile"])
    jobid_pc = ef(["idpc", "scriptidpc", "🆔idpc"])
    script = ef(["script", "scriptscript"])
    # Fallback to regex if not found in embed
    if not name:
        name = (
            re.search(r':brainrot:\s*Name\s*\n([^\n]+)', msg, re.MULTILINE) or
            re.search(r':settings:\s*Name\s*\n([^\n]+)', msg, re.MULTILINE) or
            re.search(r'🏷️ Name\s*\n([^\n]+)', msg, re.MULTILINE)
        )
        name = name.group(1).strip() if name else None
    if not money:
        money = (
            re.search(r':money:\s*Money per sec\s*\n([^\n]+)', msg, re.MULTILINE) or
            re.search(r':media:\s*Money per sec\s*\n([^\n]+)', msg, re.MULTILINE) or
            re.search(r'💰 Money per sec\s*\n([^\n]+)', msg, re.MULTILINE)
        )
        money = money.group(1).strip() if money else None
    if not players:
        players = (
            re.search(r':players:\s*Players\s*\n([^\n]+)', msg, re.MULTILINE) or
            re.search(r':member:\s*Players\s*\n([^\n]+)', msg, re.MULTILINE) or
            re.search(r'👥 Players\s*\n([^\n]+)', msg, re.MULTILINE)
        )
        players = players.group(1).strip() if players else None

    players_str = clean_field(players) if players else None
    current_players = None
    max_players = None
    if players_str:
        m = re.match(r'(\d+)\s*/\s*(\d+)', players_str)
        if m:
            current_players = int(m.group(1))
            max_players = int(m.group(2))

    instanceid = jobid_pc or jobid_mobile
    placeid = "109983668079237"
    # Try to extract from script field
    if script:
        m = re.search(r'TeleportToPlaceInstance\((\d+),["\']?([A-Za-z0-9\-]+)', script)
        if m:
            placeid = m.group(1)
            instanceid = m.group(2)

    return {
        "name": clean_field(name) if name else None,
        "money": clean_field(money) if money else None,
        "players": players_str,
        "current_players": current_players,
        "max_players": max_players,
        "jobid_mobile": jobid_mobile,
        "jobid_pc": jobid_pc,
        "script": script,
        "placeid": placeid,
        "instanceid": instanceid
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
    # Join link
    if info["placeid"] and info["instanceid"] and info["placeid"] != "109983668079237":
        join_url = f"https://chillihub1.github.io/chillihub-joiner/?placeId={info['placeid']}&gameInstanceId={info['instanceid']}"
        fields.append({
            "name": "🌐 Join Link",
            "value": "[Click to Join](%s)" % join_url,
            "inline": False
        })
    # Join script (if we have instanceid but not original script)
    if info["instanceid"] and not info["script"]:
        join_script = f"""local TeleportService = game:GetService("TeleportService")
local Players = game:GetService("Players")
local localPlayer = Players.LocalPlayer

local placeId = {info['placeid']}
local jobId = "{info['instanceid']}"

local success, err = pcall(function()
    TeleportService:TeleportToPlaceInstance(placeId, jobId, localPlayer)
end)

if not success then
    warn("Teleport failed: " .. tostring(err))
else
    print("Teleporting to job ID: " .. jobId)
end"""
        fields.append({
            "name": "📜 Join Script",
            "value": f"```lua\n{join_script}\n```",
            "inline": False
        })
    if info["jobid_mobile"]:
        fields.append({
            "name": "🆔 Job ID (Mobile)",
            "value": f"`{info['jobid_mobile']}`",
            "inline": False
        })
    if info["jobid_pc"]:
        fields.append({
            "name": "🆔 Job ID (PC)",
            "value": f"```\n{info['jobid_pc']}\n```",
            "inline": False
        })
    if info["script"]:
        fields.append({
            "name": "📜 Join Script (PC)",
            "value": f"```lua\n{info['script']}\n```",
            "inline": False
        })
    embed = {
        "title": "Eps1lon Hub Notifier",
        "color": 0x5865F2,
        "fields": fields
    }
    return {"embeds": [embed]}

def send_to_webhooks(payload):
    def send_to_webhook(url, payload):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code in [200, 204]:
                print(f"✅ Sent to webhook: {url[:50]}...")
            else:
                print(f"❌ Webhook error {response.status_code} for {url[:50]}...")
        except Exception as e:
            print(f"❌ Failed to send to webhook {url[:50]}...: {e}")
    threads = []
    for webhook_url in WEBHOOK_URLS:
        thread = threading.Thread(target=send_to_webhook, args=(webhook_url, payload))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()

def send_to_backend(info):
    if not info["name"]:
        print("Skipping backend send - missing name")
        return
    payload = {
        "name": info["name"],
        "serverId": str(info["placeid"]),
        "jobId": str(info["instanceid"]) if info["instanceid"] else "",
        "instanceId": str(info["instanceid"]) if info["instanceid"] else "",
        "players": info["players"],
        "moneyPerSec": info["money"]
    }
    try:
        response = requests.post(BACKEND_URL, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Sent to backend: {info['name']} -> {payload.get('serverId','(none)')[:8]}... ({info['players']})")
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
    full_content, embed_fields = get_message_full_content(message)
    print("Raw message content:", full_content)
    print("Embed fields:", embed_fields)
    info = parse_info(full_content, embed_fields)
    print(f"Debug - Parsed info: name='{info['name']}', money='{info['money']}', players='{info['players']}', instanceid='{info['instanceid']}'")
    if info["name"] and info["money"] and info["players"]:
        embed_payload = build_embed(info)
        send_to_webhooks(embed_payload)
        print(f"✅ Sent embed to all webhooks for: {info['name']}")
        send_to_backend(info)
    else:
        send_to_webhooks({"content": full_content})
        print(f"⚠️ Sent plain text to all webhooks (missing fields)")

client.run(TOKEN)
