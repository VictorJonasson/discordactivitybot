import time
import discord

# === KONFIG ===
GUILD_ID = 398246398975410198        # byt till din servers ID
NOTIFY_USER_ID = 245611732788051970  # byt till ditt user ID
TARGET_GAMES = set()                 # tom set() = notifiera alla spel
THROTTLE_SECONDS = 600               # minst X sekunder mellan samma användare+spel-notis

# === DIN TOKEN (hårdkodad) ===
TOKEN = "din_token_här_mellan_citattecken"

# === DISCORD SETUP ===
intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.presences = True  # glöm inte slå på Presence + Server Members i Developer Portal

member_cache_flags = discord.MemberCacheFlags.all()

client = discord.Client(intents=intents, member_cache_flags=member_cache_flags)
last_sent = {}  # (user_id, game) -> timestamp

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
    print(f"✅ Inloggad som {client.user} ({client.user.id})")

@client.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    if after.guild is None or after.guild.id != GUILD_ID:
        return

    before_set = playing_games(getattr(before, "activities", []))
    after_set  = playing_games(getattr(after,  "activities", []))

    started = after_set - before_set
    if not started:
        return

    if TARGET_GAMES:
        started = {g for g in started if g in TARGET_GAMES}
        if not started:
            return

    now = time.time()
    user = after
    dm_target = await client.fetch_user(NOTIFY_USER_ID)

    for game in started:
        key = (user.id, game)
        if now - last_sent.get(key, 0) < THROTTLE_SECONDS:
            continue

        msg = f"🟢 **{user.display_name}** startade **{game}** på _{after.guild.name}_."
        try:
            await dm_target.send(msg)
            last_sent[key] = now
            print(f"Skickade notis: {msg}")
        except Exception as e:
            print("Kunde inte skicka DM:", e)

client.run(TOKEN)
