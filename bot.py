# bot.py
import os
import time
import discord

# === KONFIG — BYT DESSA ===
GUILD_ID = 123456789012345678        # Högerklicka servern > Copy ID (Developer Mode)
NOTIFY_USER_ID = 123456789012345678  # Högerklicka dig själv > Copy ID
TARGET_GAMES = set()                 # tom set() => notifiera ALLA spel; t.ex. {"Valorant", "Minecraft"}
THROTTLE_SECONDS = 600               # minst X sek mellan samma användare+spel-notis

# === INTENTS ===
intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.presences = True
# (valfritt) om du också vill cacha voice states:
# intents.voice_states = True

# Matcha cache mot intents (fixar felet du såg)
member_cache_flags = discord.MemberCacheFlags.from_intents(intents)

client = discord.Client(intents=intents, member_cache_flags=member_cache_flags)
last_sent: dict[tuple[int, str], float] = {}  # (user_id, game) -> timestamp


def playing_games(activities):
    names = set()
    if not activities:
        return names
    for a in activities:
        # "Spelar ..." i Discord-klienten
        if isinstance(a, discord.Activity) and a.type == discord.ActivityType.playing and a.name:
            names.add(a.name)
    return names


@client.event
async def on_ready():
    print(f"✅ Inloggad som {client.user} ({client.user.id})")


@client.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    # Filtrera till rätt server
    if after.guild is None or after.guild.id != GUILD_ID:
        return

    before_set = playing_games(getattr(before, "activities", []))
    after_set  = playing_games(getattr(after,  "activities", []))

    started = after_set - before_set
    if not started:
        return

    # Filtrera på specifika spel om du angett sådana
    if TARGET_GAMES:
        started = {g for g in started if g in TARGET_GAMES}
        if not started:
            return

    now = time.time()
    dm_target = await client.fetch_user(NOTIFY_USER_ID)

    for game in started:
        key = (after.id, game)
        # Throttla för att undvika spam om presences fladdrar
        if now - last_sent.get(key, 0) < THROTTLE_SECONDS:
            continue

        msg = f"🟢 **{after.display_name}** startade **{game}** på _{after.guild.name}_."
        try:
            await dm_target.send(msg)
            last_sent[key] = now
            print(f"📨 Skickade notis: {msg}")
        except Exception as e:
            print("⚠️ Kunde inte skicka DM:", e)


# === START ===
TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # Sätt i Render → Environment
if not TOKEN:
    raise SystemExit("Sätt miljövariabeln DISCORD_BOT_TOKEN till din bottoken.")
client.run(TOKEN)
