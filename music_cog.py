# music_cog.py
import asyncio
import os
import logging 
import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
YTDL_SEARCH_OPTIONS = {
    'format': 'bestaudio/best',
    'extract_flat': 'search',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch5',
    'source_address': '0.0.0.0'
}

YTDL_PLAY_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0'
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

FFMPEG_PATH = os.getenv("FFMPEG_PATH") or "ffmpeg"
INACTIVITY_TIMEOUT = int(os.getenv("INACTIVITY_TIMEOUT", "300"))
logger = logging.getLogger("music_cog")

# --- Song Selection View ---
class SongSelectionView(discord.ui.View):
    def __init__(self, entries, music_cog_instance, interaction):
        super().__init__(timeout=60.0)
        self.entries = entries
        self.music_cog = music_cog_instance
        self.interaction = interaction
        self.selection_made = False

        for i, entry in enumerate(self.entries):
            self.add_item(SongButton(i + 1, entry))

    async def on_timeout(self):
        if not self.selection_made:
            for item in self.children:
                item.disabled = True
            try:
                await self.interaction.edit_original_response(content="*Selection timed out.*", embed=None, view=self)
            except discord.NotFound:
                pass

class SongButton(discord.ui.Button):
    def __init__(self, number, entry):
        super().__init__(label=str(number), style=discord.ButtonStyle.secondary)
        self.entry = entry

    async def callback(self, interaction: discord.Interaction):
        if self.view.selection_made:
            await interaction.response.send_message("A selection has already been made.", ephemeral=True)
            return

        self.view.selection_made = True
        for item in self.view.children:
            item.disabled = True
        
        await self.view.interaction.edit_original_response(content=f"You selected: **{self.entry.get('title', 'Unknown Title')}**", embed=None, view=self.view)
        await self.view.music_cog.add_song_to_queue(interaction, self.entry)

# --- Music State Class ---
class MusicState:
    def __init__(self, bot, guild):
        self.bot = bot
        self.guild = guild
        self.queue = []
        self.now_playing = None
        self.voice_client = None
        self.loop_mode = "NONE" # NONE, SONG, QUEUE
        self.last_text_channel = None
        self.inactivity_task = None
        self.play_next_song = asyncio.Event()
        self.bot.loop.create_task(self.audio_player_task())

    def start_inactivity_timer(self):
        if self.inactivity_task:
            self.inactivity_task.cancel()
        self.inactivity_task = self.bot.loop.create_task(self.disconnect_after_timeout())
    
    def cancel_inactivity_timer(self):
        if self.inactivity_task:
            self.inactivity_task.cancel()

    async def disconnect_after_timeout(self):
        await asyncio.sleep(INACTIVITY_TIMEOUT)
        if self.voice_client and not self.voice_client.is_playing() and not self.now_playing:
            if self.last_text_channel:
                await self.last_text_channel.send(f"Disconnected due to inactivity for {INACTIVITY_TIMEOUT // 60} minutes.")
            await self.voice_client.disconnect()
            if self.guild.id in self.bot.get_cog("Music").guild_states:
                del self.bot.get_cog("Music").guild_states[self.guild.id]

    async def audio_player_task(self):
        while True:
            self.play_next_song.clear()
            await self.play_next_song.wait()

            self.cancel_inactivity_timer()

            if self.loop_mode == "SONG" and self.now_playing:
                self.queue.insert(0, self.now_playing)
            elif self.loop_mode == "QUEUE" and self.now_playing:
                self.queue.append(self.now_playing)

            if not self.queue:
                self.now_playing = None
                self.start_inactivity_timer()
                continue

            self.now_playing = self.queue.pop(0)
            
            try:
                # OPTIMIZATION: Using FFmpegOpusAudio instead of FFmpegPCMAudio for perfect smooth streaming
                source = await discord.FFmpegOpusAudio.from_probe(self.now_playing['stream_url'], executable=FFMPEG_PATH, **FFMPEG_OPTIONS)
                self.voice_client.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.play_next_song.set))
                if self.last_text_channel:
                    embed = discord.Embed(title="▶️ Now Playing", description=f"[{self.now_playing['title']}]({self.now_playing['url']})", color=discord.Color.blue())
                    embed.set_footer(text=f"Requested by {self.now_playing['requester'].display_name}")
                    await self.last_text_channel.send(embed=embed)
            except Exception as e:
                error_embed = discord.Embed(title="❌ Player Error", description=f"`{e}`\n\nEnsure FFmpeg is installed and configured correctly.", color=discord.Color.red())
                if self.last_text_channel:
                    await self.last_text_channel.send(embed=error_embed)
                self.now_playing = None
                self.start_inactivity_timer()

# --- Music Cog Class ---
class MusicCog(commands.Cog, name="Music"):
    def __init__(self, bot):
        self.bot = bot
        self.guild_states = {}

    def get_guild_state(self, guild_id: int) -> MusicState:
        if guild_id not in self.guild_states:
            self.guild_states[guild_id] = MusicState(self.bot, self.bot.get_guild(guild_id))
        return self.guild_states[guild_id]

    async def add_song_to_queue(self, interaction: discord.Interaction, entry: dict):
        state = self.get_guild_state(interaction.guild_id)
        state.last_text_channel = interaction.channel

        loop = self.bot.loop or asyncio.get_event_loop()
        
        try:
            with yt_dlp.YoutubeDL(YTDL_PLAY_OPTIONS) as ydl:
                play_data = await loop.run_in_executor(None, lambda: ydl.extract_info(entry['url'], download=False))

            song_info = {
                'title': play_data.get('title', 'Unknown Title'),
                'url': play_data.get('webpage_url', ''),
                'stream_url': play_data.get('url', ''),
                'requester': interaction.user,
                'text_channel': interaction.channel
            }
            state.queue.append(song_info)

            if not state.voice_client.is_playing():
                state.play_next_song.set()

        except Exception as e:
            logger.exception(f"Error adding song to queue: {e}")
            await interaction.channel.send("An error occurred while preparing the song.", ephemeral=True)

    @app_commands.command(name="play", description="Plays a song or shows search results.")
    @app_commands.describe(query="The song title or YouTube URL.")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("You must be in a voice channel to use this command.", ephemeral=True)
            return
        
        state = self.get_guild_state(interaction.guild_id)
        state.last_text_channel = interaction.channel

        if state.voice_client is None or not state.voice_client.is_connected():
            state.voice_client = await interaction.user.voice.channel.connect()
        elif state.voice_client.channel != interaction.user.voice.channel:
            await state.voice_client.move_to(interaction.user.voice.channel)

        loop = self.bot.loop or asyncio.get_event_loop()
        
        is_url = query.startswith('http://') or query.startswith('https://')
        if is_url:
            with yt_dlp.YoutubeDL(YTDL_PLAY_OPTIONS) as ydl:
                entry = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
            await self.add_song_to_queue(interaction, entry)
            embed = discord.Embed(title="🎵 Added to Queue", description=f"[{entry.get('title')}]({entry.get('webpage_url')})", color=0x2ECC71)
            await interaction.followup.send(embed=embed)
        else:
            with yt_dlp.YoutubeDL(YTDL_SEARCH_OPTIONS) as ydl:
                data = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
            
            if 'entries' not in data or not data['entries']:
                await interaction.followup.send(f"Could not find any results for: `{query}`", ephemeral=True)
                return

            entries = data['entries'][:5]
            embed = discord.Embed(title="🔎 Search Results", description="Please select a song to play:", color=0x3498DB)
            for i, entry in enumerate(entries):
                title = entry.get('title', 'Untitled')
                uploader = entry.get('uploader', 'N/A')
                duration = entry.get('duration_string', 'N/A')
                field_name = f"{i+1}. {title[:250]}"
                field_value = f"by {uploader} | Duration: {duration}"
                embed.add_field(name=field_name, value=field_value[:1024], inline=False)
            
            view = SongSelectionView(entries, self, interaction)
            await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="skip", description="Skips the currently playing song.")
    async def skip(self, interaction: discord.Interaction):
        state = self.get_guild_state(interaction.guild_id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped the current song.")
        else:
            await interaction.response.send_message("Nothing is currently playing to skip.", ephemeral=True)

    @app_commands.command(name="queue", description="Shows the list of songs in the queue.")
    async def queue(self, interaction: discord.Interaction):
        state = self.get_guild_state(interaction.guild_id)
        
        if not state.queue and not state.now_playing:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return

        embed = discord.Embed(title="📜 Music Queue", color=0x3498DB)
        if state.now_playing:
            embed.add_field(name="▶️ Now Playing", value=f"[{state.now_playing['title']}]({state.now_playing['url']})", inline=False)
        
        if state.queue:
            queue_list = "\n".join(f"{i+1}. {song['title'][:100]}" for i, song in enumerate(state.queue[:10]))
            if len(state.queue) > 10:
                queue_list += f"\n...and {len(state.queue) - 10} more."
            embed.add_field(name="⌛ Up Next", value=queue_list, inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Shows details about the currently playing song.")
    async def nowplaying(self, interaction: discord.Interaction):
        state = self.get_guild_state(interaction.guild_id)
        if state.now_playing:
            embed = discord.Embed(title="▶️ Now Playing", description=f"[{state.now_playing['title']}]({state.now_playing['url']})", color=discord.Color.blue())
            embed.set_footer(text=f"Requested by {state.now_playing['requester'].display_name}")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Nothing is currently playing.", ephemeral=True)

    @app_commands.command(name="remove", description="Removes a specific song from the queue.")
    @app_commands.describe(number="The track number to remove from the queue.")
    async def remove(self, interaction: discord.Interaction, number: int):
        state = self.get_guild_state(interaction.guild_id)
        if not state.queue:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return
        
        if 1 <= number <= len(state.queue):
            removed_song = state.queue.pop(number - 1)
            await interaction.response.send_message(f"🗑️ Removed **{removed_song['title']}** from the queue.")
        else:
            await interaction.response.send_message(f"Invalid number. Please enter a number between 1 and {len(state.queue)}.", ephemeral=True)

    @app_commands.command(name="loop", description="Changes the loop mode.")
    @app_commands.describe(mode="The loop mode to set (None, Song, Queue).")
    @app_commands.choices(mode=[
        app_commands.Choice(name="None", value="NONE"),
        app_commands.Choice(name="Song", value="SONG"),
        app_commands.Choice(name="Queue", value="QUEUE"),
    ])
    async def loop(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        state = self.get_guild_state(interaction.guild_id)
        state.loop_mode = mode.value
        await interaction.response.send_message(f"🔁 Loop mode set to **{mode.name}**.")

    @app_commands.command(name="pause", description="Pauses the currently playing song.")
    async def pause(self, interaction: discord.Interaction):
        state = self.get_guild_state(interaction.guild_id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.pause()
            await interaction.response.send_message("⏸️ Music paused.")
        else:
            await interaction.response.send_message("Nothing is currently playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resumes the paused song.")
    async def resume(self, interaction: discord.Interaction):
        state = self.get_guild_state(interaction.guild_id)
        if state.voice_client and state.voice_client.is_paused():
            state.voice_client.resume()
            await interaction.response.send_message("▶️ Music resumed.")
        else:
            await interaction.response.send_message("The music is not paused.", ephemeral=True)

    @app_commands.command(name="disconnect", description="Stops music and disconnects the bot.")
    async def disconnect(self, interaction: discord.Interaction):
        state = self.get_guild_state(interaction.guild_id)
        if state.voice_client:
            state.cancel_inactivity_timer()
            await state.voice_client.disconnect()
            if interaction.guild_id in self.guild_states:
                del self.guild_states[interaction.guild_id]
            await interaction.response.send_message("👋 Disconnected.")
        else:
            await interaction.response.send_message("The bot is not in a voice channel.", ephemeral=True)

    @app_commands.command(name="stop", description="Alias for /disconnect.")
    async def stop(self, interaction: discord.Interaction):
        await self.disconnect(interaction)

async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))