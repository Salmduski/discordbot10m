import os
import discord
import re
import requests

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_IDS = [int(cid.strip()) for cid in os.getenv("CHANNEL_ID", "1234567890").split(",")]
RIPPER_BACKEND_URL = "https://chatboxs-production.up.railway.app"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

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
    # Try emoji format first, then text format with proper multiline handling
    name = re.search(r'🏷️ Name\s*\n([^\n]+)', msg, re.MULTILINE)
    if not name:
        name = re.search(r':settings: Name\s*\n([^\n]+)', msg, re.MULTILINE)
    
    money = re.search(r'💰 Money per sec\s*\n([^\n]+)', msg, re.MULTILINE)
    if not money:
        money = re.search(r':media: Money per sec\s*\n([^\n]+)', msg, re.MULTILINE)
    
    players = re.search(r'👥 Players\s*\n([^\n]+)', msg, re.MULTILINE)
    if not players:
        players = re.search(r':member: Players\s*\n([^\n]+)', msg, re.MULTILINE)
    
    # Try both "Job ID" and "ID" formats with multiline - NO DECRYPTION, JUST RAW
    jobid_mobile = re.search(r'Job ID \(Mobile\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE)
    if not jobid_mobile:
        jobid_mobile = re.search(r'ID \(Mobile\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE)
    
    jobid_ios = re.search(r'Job ID \(iOS\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE)
    if not jobid_ios:
        jobid_ios = re.search(r'ID \(iOS\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE)
    
    jobid_pc = re.search(r'Job ID \(PC\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE)
    if not jobid_pc:
        jobid_pc = re.search(r'ID \(PC\)\s*\n([A-Za-z0-9\-+/=]+)', msg, re.MULTILINE)

    # Try to get instanceid: prefer PC, fallback to iOS, then mobile - RAW, NO DECRYPTION
    instanceid = (
        jobid_pc.group(1).strip() if jobid_pc else
        jobid_ios.group(1).strip() if jobid_ios else
        jobid_mobile.group(1).strip() if jobid_mobile else
        None
    )

    return {
        "name": clean_field(name.group(1)) if name else None,
        "money": clean_field(money.group(1)) if money else None,
        "players": clean_field(players.group(1)) if players else None,
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

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    print(f'Monitoring channels: {CHANNEL_IDS}')
    print(f'Ripper backend: {RIPPER_BACKEND_URL}')

@client.event
async def on_message(message):
    if message.channel.id not in CHANNEL_IDS:
        return

    full_content = get_message_full_content(message)
    info = parse_info(full_content)
    
    # Debug print to see what we're parsing
    print(f"Debug - Parsed info: name='{info['name']}', money='{info['money']}', players='{info['players']}', instanceid='{info['instanceid']}'")
    
    # ONLY send to ripper backend /job endpoint if we have an instanceid
    if info.get("instanceid"):
        try:
            # Fixed: Send to /job endpoint specifically
            requests.post(f"{RIPPER_BACKEND_URL}/job", json={"jobId": info["instanceid"]}, timeout=5)
            print(f"✅ Submitted job to ripper /job endpoint: {info['instanceid'][:20]}...")
        except Exception as e:
            print(f"❌ Ripper /job submit failed: {e}")

client.run(TOKEN)
