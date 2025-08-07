import os
import discord
import re
import requests

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_IDS = [int(cid.strip()) for cid in os.getenv("CHANNEL_ID", "1234567890").split(",")]
RIPPER_BACKEND_URL = os.getenv("RIPPER_BACKEND_URL")

# Old discord.py version - no intents needed
client = discord.Client()

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

def parse_info_from_embed(message):
    """Parse information from Discord embed fields"""
    info = {
        "name": None,
        "money": None,
        "players": None,
        "jobid_mobile": None,
        "jobid_pc": None,
        "jobid_ios": None,
        "instanceid": None
    }
    
    for embed in message.embeds:
        for field in embed.fields:
            field_name = field.name.lower().strip()
            field_value = clean_field(field.value)
            
            # Match field names (case insensitive)
            if "name" in field_name:
                info["name"] = field_value
            elif "money" in field_name or "per sec" in field_name:
                info["money"] = field_value
            elif "players" in field_name:
                info["players"] = field_value
            elif "id (mobile)" in field_name or "mobile" in field_name:
                info["jobid_mobile"] = field_value
            elif "id (pc)" in field_name or "(pc)" in field_name:
                info["jobid_pc"] = field_value
            elif "id (ios)" in field_name or "(ios)" in field_name:
                info["jobid_ios"] = field_value
    
    # Set instanceid (prefer PC, then iOS, then Mobile)
    info["instanceid"] = (
        info["jobid_pc"] if info["jobid_pc"] else
        info["jobid_ios"] if info["jobid_ios"] else
        info["jobid_mobile"] if info["jobid_mobile"] else
        None
    )
    
    return info

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

    # Try parsing from embed fields first (new method)
    if message.embeds:
        info = parse_info_from_embed(message)
    else:
        # Fallback to content parsing (old method)
        full_content = get_message_full_content(message)
        info = parse_info(full_content)
    
    # Debug print to see what we're parsing
    print(f"Debug - Parsed info: name='{info['name']}', money='{info['money']}', players='{info['players']}', instanceid='{info['instanceid']}'")
    
    # ONLY send to ripper backend /job endpoint if we have an instanceid
    if info.get("instanceid"):
        try:
            requests.post(f"{RIPPER_BACKEND_URL}/job", json={"jobId": info["instanceid"]}, timeout=5)
            print(f"✅ Submitted job to ripper /job endpoint: {info['instanceid'][:20]}...")
        except Exception as e:
            print(f"❌ Ripper /job submit failed: {e}")

client.run(TOKEN)
