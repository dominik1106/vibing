import yt_dlp
import discord
from discord.ext.pages import Paginator, Page
import os

TOKEN = os.environ.get("BOT_TOKEN")

bot = discord.Bot()

ydl_opts = {
    'format': 'bestaudio',
    'noplaylist': True,
    'default_search': 'ytsearch1',  # ytsearch1 returns the first result
    'quiet': True,
}

ffmpeg_opts = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

queues = {}
loop_flags = {}
current_song = {}

def cleanup(guild_id):
    if guild_id in queues:
        queues.pop(guild_id)
    if guild_id in loop_flags:
        loop_flags.pop(guild_id)
    if guild_id in current_song:
        current_song.pop(guild_id)

def search_song(query: str):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        
        if 'entries' in info:
            info = info["entries"][0]

        return info
    
async def play_next(ctx: discord.ApplicationContext, error = None):
    if error:
        print(error)

    guild_id = ctx.guild_id
    voice_client = ctx.voice_client

    if not voice_client or not voice_client.is_connected():
        # Log or handle the fact that the bot isn't connected to a voice channel
        print(f"Bot is not connected to a voice channel in guild {guild_id}.")
        print(ctx)
        embed = discord.Embed(
            description="Bot is not connected to a voice channel!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if guild_id in loop_flags and loop_flags[guild_id]:
        song = current_song[guild_id]
    elif guild_id in queues and queues[guild_id]:
        song = queues[guild_id].pop(0)
        current_song[guild_id] = song
    else:
        embed = discord.Embed(
            description="No more songs in queue!",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return

    audio_url = song.get("url")

    try:
        source = await discord.FFmpegOpusAudio.from_probe(audio_url, **ffmpeg_opts)
        voice_client.play(source, after=lambda e: bot.loop.create_task(play_next(ctx, e)))
    except Exception as e:
        # Catch any exceptions related to FFmpeg or voice playback
        print(f"Error when trying to play the song: {e}")
        embed = discord.Embed(
            description=f"Error playing the song: {e}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if guild_id not in loop_flags or not loop_flags[guild_id]:
        embed = discord.Embed(
            description=f"Now playing [{song['title']}]({song['webpage_url']})",
            color=discord.Color.blue()
        )

        await ctx.send(embed=embed)

@bot.slash_command(
    name="play",
    description="Add a song to the queue"
)
async def play(ctx: discord.ApplicationContext, search: str):
    await ctx.defer()

    guild_id = ctx.guild_id
    voice_client = ctx.voice_client

    if not voice_client:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            voice_client = await channel.connect()
        else:
            embed = discord.Embed(
                description="You are not connected to a voice channel.",
                color= discord.Color.yellow()
            )
            await ctx.respond(embed=embed)
            return

    if guild_id not in queues:
        queues[guild_id] = []
        
    info = search_song(search)
    queues[guild_id].append(info)

    if not voice_client.is_playing():
        await play_next(ctx)

    embed = discord.Embed(
        description=f"Added [{info['title']}]({info['webpage_url']}) to the queue!",
        color=discord.Color.green()
    )
    
    await ctx.respond(embed=embed)

@bot.slash_command(
    name="stop",
    description="Stops the bot, disconnects it and clears the queue"
)
async def stop(ctx: discord.ApplicationContext):
    guild_id = ctx.guild_id
    voice_client = ctx.voice_client
    if voice_client:
        cleanup(guild_id)
        await voice_client.disconnect()
        embed = discord.Embed(
            description="Bye!",
            color= discord.Color.purple()
        )
        await ctx.respond(embed=embed)
    else:
        embed = discord.Embed(
            description="Not connected to a voice channel!",
            color= discord.Color.red()
        )
        await ctx.respond(embed=embed)

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member == bot.user:
        print(member)
        print(before)
        print(after)
        if before.channel is not None and after.channel is None:
            guild_id = before.channel.guild.id
            cleanup(guild_id)

@bot.slash_command(
    name="skip",
    description="Skips the current song and also disables looping"
)
async def skip(ctx: discord.ApplicationContext):
    guild_id = ctx.guild_id
    voice_client = ctx.voice_client

    if not voice_client:
        embed = discord.Embed(
            description="Not connected to a voice channel!",
            color= discord.Color.red()
        )
    elif voice_client.is_playing():
        voice_client.stop()

        loop_flags[guild_id] = False

        embed = discord.Embed(
            description="Skipped song!",
            color= discord.Color.green()
        )
    else:
        embed = discord.Embed(
            description="No song is currently playing!",
            color= discord.Color.red()
        )

    await ctx.respond(embed=embed)

@bot.slash_command(
    name="loop",
    description="Loops the current song"
)
async def loop(ctx: discord.ApplicationContext):
    guild_id = ctx.guild_id

    if guild_id not in loop_flags:
        loop_flags[guild_id] = False

    loop_flags[guild_id] = not loop_flags[guild_id]

    if loop_flags[guild_id]:
        embed = discord.Embed(
            description="Looping current song!",
            color=discord.Color.blue()
        )
        await ctx.respond(embed=embed)
    else:
        embed = discord.Embed(
            description="No longer looping current song!",
            color=discord.Color.blue()
        )
        await ctx.respond(embed=embed)

@bot.slash_command(
    name="clear",
    description="Clears the queue"
)
async def clear(ctx: discord.ApplicationContext):
    guild_id = ctx.guild_id

    if guild_id in queues:
        queues.pop(guild_id)

    embed = discord.Embed(
        description="Cleared queue!",
        color=discord.Color.green()
    )
    
    await ctx.respond(embed=embed)

@bot.slash_command(
    name="pause",
    description="Toggles pause"
)
async def pause(ctx: discord.ApplicationContext):
    voice_client = ctx.voice_client

    if not voice_client:
        embed = discord.Embed(
            description="Not connected to a voice channel!",
            color=discord.Color.red()
        )
    elif voice_client.is_paused():
        voice_client.resume()
        embed = discord.Embed(
            description="Resuming!",
            color=discord.Color.green()
        )
    else:
        voice_client.pause()
        embed = discord.Embed(
            description="Paused!",
            color=discord.Color.green()
        )

    await ctx.respond(embed=embed)

# Run the bot with your token
bot.run(TOKEN)