import os
import time
import discord

# === KONFIG ===
GUILD_ID = 398246398975410198        # byt till din servers ID
NOTIFY_USER_ID = 245611732788051970  # byt till ditt Discord user ID
TARGET_GAMES = set()                 # t.ex. {"Valorant", "Minecraft"} eller tom set() för alla
THROTTLE_SECONDS = 600               # minst X sekunder mellan samma användare+spel-notis

# === INTENTS ===
intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.presences = True
member_cache_flags = discord.MemberCacheFlags.from_intents(intents)

client = discord.Client(intents=intents, member_cache_flags=member_cache_flags)
last_sent: dict[tuple[int, str], float] = {}


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
        print(f"🔍 Lyssnar på server: {guild.name} ({guild.id})")
        print(f"👥 Antal medlemmar laddade: {len(guild.members)}")
    else:
        print("⚠️ Kunde inte hitta guild direkt — kommer ladda när event triggas.")

    # === Skicka DM till ägaren när botten startar ===
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

    # Logga förändringar för debugging
    if before_set != after_set:
        print(f"🔄 Presence ändrad: {after.display_name}")
        print(f"   Före:  {before_set or '-'}")
        print(f"   Efter: {after_set or '-'}")

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
        if now - last_sent.get(key, 0) < THROTTLE_SECONDS:
            continue

        msg = f"🟢 **{after.display_name}** startade **{game}** på _{after.guild.name}_."
        try:
            await dm_target.send(msg)
            last_sent[key] = now
            print(f"📨 DM skickad → {after.display_name}: {game}")
        except Exception as e:
            print(f"⚠️ Kunde inte skicka DM till {after.display_name}: {e}")


# === START ===
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise SystemExit("❌ Miljövariabeln DISCORD_BOT_TOKEN saknas. Lägg till den på Render → Environment.")

client.run(TOKEN)
