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
    """Remove markdown/code formatting and extra whitespace"""
    if not text:
        return text
    # Remove triple backtick code blocks (multi-line and single-line)
    text = re.sub(r"```(?:lua)?\n?(.*?)```", r"\1", text, flags=re.DOTALL)
    # Remove inline code
    text = re.sub(r"`([^`]*)`", r"\1", text)
    # Remove ** bold formatting
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    # Remove * italic formatting  
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    return text.strip()

def get_message_full_content(message):
    parts = []
    embed_fields = {}
    if message.content and message.content.strip():
        parts.append(message.content)
    for embed in getattr(message, "embeds", []):
        if getattr(embed, "title", None):
            parts.append(embed.title)
        if getattr(embed, "description", None):
            parts.append(embed.description)
        for field in getattr(embed, "fields", []):
            # Use raw key for full matching, and store
            embed_fields[field.name.strip().lower()] = field.value.strip()
            parts.append(f"{field.name}\n{field.value}")
    for att in getattr(message, "attachments", []):
        parts.append(att.url)
    return "\n".join(parts) if parts else "(no content)", embed_fields

def find_field_by_suffix(fields, suffixes):
    """Find field in dict whose key ends with any of the suffixes (case-insensitive)"""
    for key, value in fields.items():
        for suf in suffixes:
            if key.endswith(suf.lower()):
                return value
    return None

def parse_info(msg, embed_fields=None):
    embed_fields = embed_fields or {}

    # Find values by suffix (matching your actual embed keys)
    name = find_field_by_suffix(embed_fields, ["name"])
    money = find_field_by_suffix(embed_fields, ["moneypersec"])
    players = find_field_by_suffix(embed_fields, ["players"])
    jobid_mobile = find_field_by_suffix(embed_fields, ["idmobile"])
    jobid_pc = find_field_by_suffix(embed_fields, ["idpc"])
    script = find_field_by_suffix(embed_fields, ["script"])

    # Fallback to regex if not found in embed
    if not name:
        name = (
            re.search(r'(?:<:brainrot:[^>]+>|:brainrot:)\s*Name\s*\n(?:```)?([^\n`]+)', msg, re.MULTILINE) or
            re.search(r'🏷️ Name\s*\n(?:```)?([^\n`]+)', msg, re.MULTILINE)
        )
        name = name.group(1).strip() if name else None
    if not money:
        money = (
            re.search(r'(?:<:money:[^>]+>|:money:)\s*Money per sec\s*\n(?:```)?([^\n`]+)', msg, re.MULTILINE) or
            re.search(r'💰 Money per sec\s*\n(?:```)?([^\n`]+)', msg, re.MULTILINE)
        )
        money = money.group(1).strip() if money else None
    if not players:
        players = (
            re.search(r'(?:<:players:[^>]+>|:players:)\s*Players\s*\n(?:```)?([^\n`]+)', msg, re.MULTILINE) or
            re.search(r'👥 Players\s*\n(?:```)?([^\n`]+)', msg, re.MULTILINE)
        )
        players = players.group(1).strip() if players else None
    if not jobid_mobile:
        jobid_mobile = (
            re.search(r'(?:<:phone:[^>]+>|:phone:)\s*ID \(Mobile\)\s*\n([^\n`]+)', msg, re.MULTILINE)
        )
        jobid_mobile = jobid_mobile.group(1).strip() if jobid_mobile else None
    if not jobid_pc:
        jobid_pc = (
            re.search(r'(?:<:script:[^>]+>|:script:)\s*ID \(PC\)\s*\n(?:```)?([^\n`]+)', msg, re.MULTILINE)
        )
        jobid_pc = jobid_pc.group(1).strip() if jobid_pc else None
    if not script:
        script = (
            re.search(r'(?:<:script:[^>]+>|:script:)\s*Script\s*\n```lua\n?(.*?)```', msg, re.DOTALL) or
            re.search(r'Join Script \(PC\)\s*\n(game:GetService\("TeleportService"\):TeleportToPlaceInstance\([^\n]+)', msg, re.MULTILINE)
        )
        script = script.group(1).strip() if script else None

    # Clean all fields
    name = clean_field(name)
    money = clean_field(money)
    players_str = clean_field(players)
    jobid_mobile = clean_field(jobid_mobile)
    jobid_pc = clean_field(jobid_pc)
    script = clean_field(script)

    current_players = None
    max_players = None
    if players_str:
        m = re.match(r'(\d+)\s*/\s*(\d+)', players_str)
        if m:
            current_players = int(m.group(1))
            max_players = int(m.group(2))

    # Instanceid: prefer PC, fallback to mobile
    instanceid = jobid_pc or jobid_mobile

    # Placeid: try to extract from script, fallback to constant
    placeid = "109983668079237"
    if script:
        m = re.search(r'TeleportToPlaceInstance\((\d+),["\']?([A-Za-z0-9\-]+)', script)
        if m:
            placeid = m.group(1)
            instanceid = m.group(2)

    return {
        "name": name,
        "money": money,
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
    if info["placeid"] and info["instanceid"]:
        join_url = f"https://chillihub1.github.io/chillihub-joiner/?placeId={info['placeid']}&gameInstanceId={info['instanceid']}"
        fields.append({
            "name": "🌐 Join Link",
            "value": "[Click to Join](%s)" % join_url,
            "inline": False
        })
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
    if info["name"] and info["money"] and info["players"] and info["instanceid"]:
        embed_payload = build_embed(info)
        send_to_webhooks(embed_payload)
        print(f"✅ Sent embed to all webhooks for: {info['name']}")
        send_to_backend(info)
    else:
        send_to_webhooks({"content": full_content})
        print(f"⚠️ Sent plain text to all webhooks (missing fields)")

client.run(TOKEN)
