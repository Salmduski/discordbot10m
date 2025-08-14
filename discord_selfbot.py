import os
import discord
import re
import requests
import threading

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_IDS = [int(cid.strip()) for cid in os.getenv("CHANNEL_ID", "1234567890").split(",")]
# Support multiple webhook URLs separated by commas
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
    # Remove extra whitespace
    return text.strip()

def parse_info(msg):
    # Try new "brainrot" style first, then emoji, then text format
    name = (
        re.search(r':brainrot:\s*Name\s*\n([^\n]+)', msg, re.MULTILINE) or
        re.search(r':settings:\s*Name\s*\n([^\n]+)', msg, re.MULTILINE) or
        re.search(r'🏷️ Name\s*\n([^\n]+)', msg, re.MULTILINE)
    )

    money = (
        re.search(r':money:\s*Money per sec\s*\n([^\n]+)', msg, re.MULTILINE) or
        re.search(r':media:\s*Money per sec\s*\n([^\n]+)', msg, re.MULTILINE) or
        re.search(r'💰 Money per sec\s*\n([^\n]+)', msg, re.MULTILINE)
    )

    players = (
        re.search(r':players:\s*Players\s*\n([^\n]+)', msg, re.MULTILINE) or
        re.search(r':member:\s*Players\s*\n([^\n]+)', msg, re.MULTILINE) or
        re.search(r'👥 Players\s*\n([^\n]+)', msg, re.MULTILINE)
    )

    # Try both "Job ID" and "ID" formats with multiline (for mobile/iOS/PC)
    jobid_mobile = (
        re.search(r':phone:\s*ID \(Mobile\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE) or
        re.search(r'Job ID \(Mobile\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE) or
        re.search(r'ID \(Mobile\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE)
    )

    jobid_ios = (
        re.search(r'Job ID \(iOS\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE) or
        re.search(r'ID \(iOS\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE)
    )

    jobid_pc = (
        re.search(r':script:\s*ID \(PC\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE) or
        re.search(r'Job ID \(PC\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE) or
        re.search(r'ID \(PC\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE)
    )

    script = re.search(r'Join Script \(PC\)\s*\n(game:GetService\("TeleportService"\):TeleportToPlaceInstance\([^\n]+\))', msg, re.MULTILINE)
    join_match = re.search(r'TeleportToPlaceInstance\((\d+),[ "\']*([A-Za-z0-9\-+/=]+)[ "\']*,', msg)

    players_str = clean_field(players.group(1)) if players else None
    current_players = None
    max_players = None
    if players_str:
        m = re.match(r'(\d+)\s*/\s*(\d+)', players_str)
        if m:
            current_players = int(m.group(1))
            max_players = int(m.group(2))

    # Try to get instanceid: prefer PC, fallback to iOS, then mobile
    instanceid = (
        jobid_pc.group(1).strip() if jobid_pc else
        jobid_ios.group(1).strip() if jobid_ios else
        jobid_mobile.group(1).strip() if jobid_mobile else
        None
    )

    # Try to get placeid from the join script. If not found, use fixed placeid
    placeid = join_match.group(1) if join_match else "109983668079237"

    return {
        "name": clean_field(name.group(1)) if name else None,
        "money": clean_field(money.group(1)) if money else None,
        "players": players_str,
        "current_players": current_players,
        "max_players": max_players,
        "jobid_mobile": jobid_mobile.group(1).strip() if jobid_mobile else None,
        "jobid_ios": jobid_ios.group(1).strip() if jobid_ios else None,
        "jobid_pc": jobid_pc.group(1).strip() if jobid_pc else None,
        "script": script.group(1).strip() if script else None,
        "placeid": placeid,
        "instanceid": instanceid
    }

def get_message_full_content(message):
    parts = []
    if message.content and message.content.strip():
        parts.append(message.content)
    for embed in message.embeds:
        if embed.title:
            parts.append(embed.title)
        if embed.description:
            parts.append(embed.description)
        for field in getattr(embed, "fields", []):
            parts.append(f"{field.name}\n{field.value}")
    for att in message.attachments:
        parts.append(att.url)
    return "\n".join(parts) if parts else "(no content)"

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
    
    # Original join link method (if we have both placeid and instanceid and placeid is not the default)
    if info["placeid"] and info["instanceid"] and info["placeid"] != "109983668079237":
        join_url = f"https://chillihub1.github.io/chillihub-joiner/?placeId={info['placeid']}&gameInstanceId={info['instanceid']}"
        fields.append({
            "name": "🌐 Join Link",
            "value": "[Click to Join](%s)" % join_url,
            "inline": False
        })
    
    # New join script method (ONLY if we have instanceid but no original script)
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
    if info["jobid_ios"]:
        fields.append({
            "name": "🆔 Job ID (iOS)",
            "value": f"`{info['jobid_ios']}`",
            "inline": False
        })
    if info["jobid_pc"]:
        fields.append({
            "name": "🆔 Job ID (PC)",
            "value": f"```\n{info['jobid_pc']}\n```",
            "inline": False
        })
    
    # Original join script method (if it exists in the message) - UNCHANGED
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
    """Send payload to all configured webhooks"""
    def send_to_webhook(url, payload):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code in [200, 204]:
                print(f"✅ Sent to webhook: {url[:50]}...")
            else:
                print(f"❌ Webhook error {response.status_code} for {url[:50]}...")
        except Exception as e:
            print(f"❌ Failed to send to webhook {url[:50]}...: {e}")
    
    # Send to all webhooks in parallel using threads
    threads = []
    for webhook_url in WEBHOOK_URLS:
        thread = threading.Thread(target=send_to_webhook, args=(webhook_url, payload))
        thread.start()
        threads.append(thread)
    
    # Wait for all requests to complete
    for thread in threads:
        thread.join()

def send_to_backend(info):
    """
    Send info to backend - now sends clean data without markdown formatting
    """
    # Only require name now
    if not info["name"]:
        print("Skipping backend send - missing name")
        return

    payload = {
        "name": info["name"],  # Already cleaned by clean_field()
        "serverId": str(info["placeid"]),
        "jobId": str(info["instanceid"]) if info["instanceid"] else "",
        "instanceId": str(info["instanceid"]) if info["instanceid"] else "",
        "players": info["players"],  # Already cleaned by clean_field()
        "moneyPerSec": info["money"]  # Already cleaned by clean_field()
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

    full_content = get_message_full_content(message)
    info = parse_info(full_content)
    
    # Debug print to see what we're parsing
    print(f"Debug - Parsed info: name='{info['name']}', money='{info['money']}', players='{info['players']}', instanceid='{info['instanceid']}'")
    
    # Always send to Discord embed if name, money, players are there
    if info["name"] and info["money"] and info["players"]:
        embed_payload = build_embed(info)
        send_to_webhooks(embed_payload)
        print(f"✅ Sent embed to all webhooks for: {info['name']}")
        send_to_backend(info)
    else:
        send_to_webhooks({"content": full_content})
        print(f"⚠️ Sent plain text to all webhooks (missing fields)")

client.run(TOKEN)
