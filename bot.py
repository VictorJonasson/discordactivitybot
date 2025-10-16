import os
import time
import asyncio
import discord
from aiohttp import web

# --- Liten webserver för Render hälsokoll ---
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
NOTIFY_USER_ID = 245611732788051970  # ditt Discord user ID (du som får DM)
TARGET_GAMES = set()                 # t.ex. {"Valorant", "Minecraft"}; tom set() = alla
THROTTLE_SECONDS = 600               # throttling för spel-notiser
VOICE_THROTTLE_SECONDS = 120         # throttling för voice-notiser
MONITOR_USER_ID = 219400078790623232 # <-- ID:t på personen du vill övervaka i röstkanaler

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
last_monitor_state: bool | None = None  # None = okänt, True = i voice, False = inte

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

        # Kolla direkt vid start om monitor-användaren är i voice
        monitored = guild.get_member(MONITOR_USER_ID)
        dm_target = await client.fetch_user(NOTIFY_USER_ID)
        if monitored:
            if monitored.voice and monitored.voice.channel:
                msg = f"🎧 **{monitored.display_name}** är redan i röstkanalen **{monitored.voice.channel.name}**."
                await dm_target.send(msg)
                print(f"📨 Init voice-status: {msg}")
            else:
                msg = f"🔇 **{monitored.display_name}** är inte i någon röstkanal just nu."
                await dm_target.send(msg)
                print(f"📨 Init voice-status: {msg}")
    else:
        print("⚠️ Kunde inte hitta guild direkt — laddas vid event.")

    try:
        dm_target = await client.fetch_user(NOTIFY_USER_ID)
        await dm_target.send(f"✅ Din bot **{client.user.name}** är nu online och aktiv på Discord! 🚀")
        print(f"📨 Skickade startnotis till {dm_target.name}.")
    except Exception as e:
        print(f"⚠️ Kunde inte skicka startnotis-DM: {e}")


@client.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    if after.guild is None or after.guild.id != GUILD_ID:
        return

    before_set = playing_games(getattr(before, "activities", []))
    after_set  = playing_games(getattr(after,  "activities", []))
    started = after_set - before_set

    if before_set != after_set:
        print(f"🔄 Presence ändrad: {after.display_name} | Före: {before_set or '-'} | Efter: {after_set or '-'}")

    if not started:
        return

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
    global last_monitor_state

    if member.guild is None or member.guild.id != GUILD_ID:
        return

    dm_target = await client.fetch_user(NOTIFY_USER_ID)

    # --- Vanlig notifiering: någon går in i voice ---
    joined = before.channel is None and after.channel is not None
    if joined:
        now = time.time()
        key = (member.id, after.channel.id)
        if now - last_voice_sent.get(key, 0) > VOICE_THROTTLE_SECONDS:
            msg = f"🔊 **{member.display_name}** gick in i röstkanalen **{after.channel.name}**."
            await dm_target.send(msg)
            last_voice_sent[key] = now
            print(f"📨 DM (voice): {member.display_name} → {after.channel.name}")

    # --- Specifik övervakad användare ---
    if member.id == MONITOR_USER_ID:
        in_voice = after.channel is not None
        if last_monitor_state is None or in_voice != last_monitor_state:
            last_monitor_state = in_voice
            if in_voice:
                msg = f"🎧 Din övervakade användare **{member.display_name}** gick in i **{after.channel.name}**."
            else:
                msg = f"🔇 Din övervakade användare **{member.display_name}** lämnade röstkanalen."
            await dm_target.send(msg)
            print(f"📨 DM (monitor): {msg}")


# === START ===
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise SystemExit("❌ Miljövariabeln DISCORD_BOT_TOKEN saknas. Lägg till den på Render → Environment.")

async def main():
    await asyncio.gather(run_web(), client.start(TOKEN))

asyncio.run(main())
