import os
import time
import asyncio
import discord
from aiohttp import web

# --- Liten webserver för Render hälsokoll (för Web Service) ---
async def health(_):
    return web.Response(text="ok")

async def run_web():
    app = web.Application()
    app.add_routes([web.get("/", health)])
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# === KONFIG ===
GUILD_ID = 398246398975410198        # din servers ID
NOTIFY_USER_ID = 245611732788051970  # den som får DM (du)
# 🔎 Övervakade användare (ange här EN eller FLERA – men bara här):
MONITOR_USER_IDS: set[int] = {
    219400078790623232,
    256819685306269696,# lägg till/ta bort ID:n här
}

# Spel-filter (tom set() = alla spel)
TARGET_GAMES = set()                 # t.ex. {"Valorant", "Minecraft"}
THROTTLE_SECONDS = 600               # min tid mellan spel-notiser per (user, game)
VOICE_THROTTLE_SECONDS = 120         # min tid mellan voice-notiser per (user, channel)

# === INTENTS ===
intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.presences = True
intents.voice_states = True
member_cache_flags = discord.MemberCacheFlags.from_intents(intents)

client = discord.Client(intents=intents, member_cache_flags=member_cache_flags)

# --- states ---
last_game_sent: dict[tuple[int, str], float] = {}
last_voice_sent: dict[tuple[int, int], float] = {}
last_monitor_voice: dict[int, bool] = {}  # user_id -> i_voice senast (True/False)

def playing_games(activities):
    names = set()
    if not activities:
        return names
    for a in activities:
        if isinstance(a, discord.Activity) and a.type == discord.ActivityType.playing and a.name:
            names.add(a.name)
    return names

@client.event
async def on_ready():
    print(f"✅ Botten är inloggad som {client.user} ({client.user.id})")
    guild = client.get_guild(GUILD_ID)
    if guild:
        print(f"🔍 Lyssnar på server: {guild.name} ({guild.id}) | Medlemmar: {len(guild.members)}")
    else:
        print("⚠️ Kunde inte hitta guild direkt — laddas vid event.")

    # Startnotis
    try:
        dm_target = await client.fetch_user(NOTIFY_USER_ID)
        await dm_target.send(f"✅ Din bot **{client.user.name}** är nu online och aktiv på Discord! 🚀")
        print(f"📨 Skickade startnotis till {dm_target.name}.")
    except Exception as e:
        print(f"⚠️ Kunde inte skicka startnotis-DM: {e}")

    # Initial status för alla övervakade (voice + ev. pågående spel)
    if guild and MONITOR_USER_IDS:
        dm_target = await client.fetch_user(NOTIFY_USER_ID)
        for uid in MONITOR_USER_IDS:
            m = guild.get_member(uid)
            if not m:
                print(f"ℹ️ Hittar inte user {uid} i cache ännu.")
                continue

            in_voice = bool(m.voice and m.voice.channel)
            last_monitor_voice[uid] = in_voice
            if in_voice:
                await dm_target.send(f"🎧 **{m.display_name}** är i **{m.voice.channel.name}** (vid start).")
            else:
                await dm_target.send(f"🔇 **{m.display_name}** är inte i röstkanal (vid start).")

            current_games = playing_games(getattr(m, "activities", []))
            if current_games:
                await dm_target.send(f"🎮 **{m.display_name}** spelar redan: {', '.join(sorted(current_games))} (vid start).")

@client.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    # Endast rätt server och endast övervakade användare
    if after.guild is None or after.guild.id != GUILD_ID or after.id not in MONITOR_USER_IDS:
        return

    before_set = playing_games(getattr(before, "activities", []))
    after_set  = playing_games(getattr(after,  "activities", []))
    started = after_set - before_set

    if before_set != after_set:
        print(f"🔄 Presence ändrad: {after.display_name} | Före: {before_set or '-'} | Efter: {after_set or '-'}")

    if not started:
        return

    # Spelfilter (om satt)
    if TARGET_GAMES:
        started = {g for g in started if g in TARGET_GAMES}
        if not started:
            return

    now = time.time()
    dm_target = await client.fetch_user(NOTIFY_USER_ID)
    for game in started:
        key = (after.id, game)
        if now - last_game_sent.get(key, 0) < THROTTLE_SECONDS:
            continue
        msg = f"🟢 **{after.display_name}** startade **{game}** på _{after.guild.name}_."
        try:
            await dm_target.send(msg)
            last_game_sent[key] = now
            print(f"📨 DM (spel): {after.display_name} → {game}")
        except Exception as e:
            print(f"⚠️ DM-fel (spel) till {after.display_name}: {e}")

@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    # Endast rätt server
    if member.guild is None or member.guild.id != GUILD_ID:
        return

    # Vi bryr oss bara om övervakade användare
    if member.id not in MONITOR_USER_IDS:
        return

    dm_target = await client.fetch_user(NOTIFY_USER_ID)

    # Beräkna ny voice-status
    in_voice = after.channel is not None
    prev = last_monitor_voice.get(member.id)

    # Notifiera endast vid förändring (join/leave)
    if prev is None or in_voice != prev:
        last_monitor_voice[member.id] = in_voice
        if in_voice:
            msg = f"🎧 **{member.display_name}** gick in i **{after.channel.name}**."
        else:
            msg = f"🔇 **{member.display_name}** lämnade röstkanalen."
        try:
            await dm_target.send(msg)
            print(f"📨 DM (voice/monitor): {msg}")
        except Exception as e:
            print(f"⚠️ DM-fel (voice/monitor) till {member.display_name}: {e}")

# === START ===
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise SystemExit("❌ Miljövariabeln DISCORD_BOT_TOKEN saknas. Lägg till den på Render → Environment.")

async def main():
    # Web Service-variant (hålls vid liv av health endpoint)
    await asyncio.gather(run_web(), client.start(TOKEN))

asyncio.run(main())
