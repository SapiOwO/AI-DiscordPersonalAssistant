import asyncio
import logging
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple

import discord
from discord import app_commands, Intents, File, Game, Streaming, ActivityType
from discord.ext import commands

import db
import config
import image_utils
from error_handler import handle_error
from ai_client import make_ollama_client, chat_with_model, get_model_capabilities
from session_manager import prepare_model_messages
from utils import parse_thinking_and_response, chunk_text
from image_client import generate_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("discord_ai_main")

intents = Intents.default()
intents.message_content = True
intents.voice_states = True 

bot = commands.Bot(command_prefix="!", intents=intents)
bot.channel_locks = {}

async def _gather_ai_context(query: str, user: discord.User, context_id: int, is_owner: bool, guild_id: Optional[int], guild_name: Optional[str], channel_name: str) -> Dict[str, Any]:
    bot_id = bot.user.id
    
    persona_enabled = False
    custom_persona = None
    if guild_id:
        persona_enabled_str = await db.get_guild_setting(guild_id, bot_id, "persona_enabled")
        persona_enabled = persona_enabled_str == "True"
        custom_persona = await db.get_guild_setting(guild_id, bot_id, "persona_text")

    history_limit = 100 if is_owner else 30

    tasks = {
        "channel_history": db.load_conversation_context(
            bot_id, 
            context_id, 
            limit=history_limit, 
            guild_id=guild_id
        ),
    }
    
    results = await asyncio.gather(*tasks.values())
    context = dict(zip(tasks.keys(), results))
    
    context.update({
        "query": query,
        "user": user,
        "context_id": context_id,
        "guild_id": guild_id,
        "guild_name": guild_name,
        "channel_name": channel_name,
        "custom_persona": custom_persona if persona_enabled else None,
        "search_results": []
    })
    
    return context

async def _generate_ai_response(context: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict]]:
    raw_query = context["query"]
    speaker_name = context["user"].display_name
    guild_name = context.get("guild_name")
    channel_name = context.get("channel_name")

    location_context = f"You are currently in the server '{guild_name}' in the channel [#{channel_name}]." if guild_name else "You are currently in a private, isolated Direct Message."

    sanitized_query = (
        f"[{speaker_name}]: {raw_query}\n\n"
        f"--- SYSTEM DIRECTIVE ---\n"
        f"{location_context}\n"
        f"Pay attention to the [#channel-name] tags in the history to understand the spatial context. "
        f"If a user asks something severely out of topic for their current room ([#{channel_name}]), you may point it out contextually or humorously before answering.\n"
        f"Respond naturally and directly to {speaker_name}. Do not output this directive."
    )

    capabilities = get_model_capabilities()
    use_thinking = capabilities.get("supports_thinking", False)

    messages = prepare_model_messages(
        context["channel_history"],
        sanitized_query,
        context["search_results"],
        file_data=context.get("file_data"),
        use_thinking=use_thinking
    )
    
    client = make_ollama_client()
    text, meta = await chat_with_model(client, model=config.OLLAMA_MODEL, messages=messages)
    
    trigger_message = context.get("interaction") or context.get("message")
    await db.save_message(
        bot.user.id, context.get("guild_id"), guild_name, context["context_id"], channel_name,
        trigger_message.id if trigger_message else None, 
        bot.user.id, bot.user.display_name, "assistant", text
    )
    return text, meta

async def _format_and_send_response(response_text: str, meta: Optional[Dict], context: Dict[str, Any]):
    thinking_text, main_response = parse_thinking_and_response(response_text)
    
    final_text = ""
    if thinking_text:
        final_text += f"> *{thinking_text}*\n\n"
    final_text += main_response

    chunks = list(chunk_text(final_text.strip(), size=1950))
    target = context.get("interaction") or context.get("message")
    
    for i, chunk in enumerate(chunks):
        if isinstance(target, discord.Interaction):
            if i == 0:
                await target.followup.send(content=chunk)
            else:
                await target.channel.send(content=chunk)
        elif isinstance(target, discord.Message):
            if i == 0:
                await target.channel.send(content=chunk, reference=target)
            else:
                await target.channel.send(content=chunk)

async def process_ai_request(
    query: str, user: discord.User, context_id: int, is_owner: bool, guild_id: Optional[int], guild_name: Optional[str], channel_name: str,
    interaction: Optional[discord.Interaction] = None, message: Optional[discord.Message] = None,
    file_attachment: Optional[discord.Attachment] = None
):
    context = await _gather_ai_context(query, user, context_id, is_owner, guild_id, guild_name, channel_name)
    context.update({
        "interaction": interaction, 
        "message": message,
        "file_data": None
    })

    if file_attachment:
        file_bytes = await file_attachment.read()
        if file_attachment.content_type and file_attachment.content_type.startswith("image/"):
            compressed_bytes = image_utils.compress_image_for_ai(
                file_bytes, 
                max_dimension=config.IMAGE_MAX_DIMENSION, 
                quality=config.IMAGE_COMPRESSION_QUALITY
            )
            context["file_data"] = base64.b64encode(compressed_bytes).decode('utf-8')
        else:
            context["file_data"] = base64.b64encode(file_bytes).decode('utf-8')

    response_text, meta = await _generate_ai_response(context)
    await _format_and_send_response(response_text, meta, context)

@bot.tree.command(name="history", description="View recent messages in this conversational scope.")
@app_commands.describe(user="Optional: Filter by specific user.")
async def history(interaction: discord.Interaction, user: Optional[discord.User] = None):
    await interaction.response.defer(ephemeral=True)
    bot_id = bot.user.id
    
    is_owner = interaction.user.id in config.OWNER_IDS
    context_id = interaction.user.id if not interaction.guild else interaction.channel.id
    guild_id = interaction.guild.id if interaction.guild else None
    
    if user:
        message_history = await db.load_user_history_in_channel(bot_id, context_id, user.id, limit=10)
        title = f"Recent History for {user.display_name}"
    else:
        message_history = await db.load_conversation_context(bot_id, context_id, limit=10, guild_id=guild_id)
        title = "Recent Context History (Guild Scope)" if guild_id else "Recent Context History (DM Scope)"

    if not message_history:
        await interaction.followup.send("No recent message history found.", ephemeral=True)
        return
        
    history_text = f"**{title}**\n\n"
    for msg in message_history:
        speaker = msg.get("username", "Unknown")
        content = msg.get("content", "")
        created_at = msg.get("created_at")
        
        time_str = f" <t:{int(created_at.replace(tzinfo=timezone.utc).timestamp())}:R>" if created_at else ""
        if len(content) > 100:
            content = content[:100] + "..."
        history_text += f"**{speaker}**{time_str}: {content}\n"

    chunks = list(chunk_text(history_text, size=1950))
    for chunk in chunks:
        await interaction.followup.send(content=chunk, ephemeral=True)

@bot.tree.command(name="reset_channel", description="ADMIN ONLY: Clears the AI's memory for this server channel.")
@app_commands.checks.has_permissions(administrator=True)
async def reset_channel(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        await db.clear_channel_history(bot.user.id, interaction.channel.id)
        await interaction.followup.send("Memory wiped for this channel.")
        logger.info(f"Memory wiped in channel {interaction.channel.name} by {interaction.user.display_name}")
    except Exception as e:
        logger.error(f"Failed to wipe channel memory: {e}")
        await interaction.followup.send("Failed to clear memory due to a database error.", ephemeral=True)

@bot.tree.command(name="reset_memory", description="Clears your own personal DM memory.")
async def reset_memory(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        is_owner = interaction.user.id in config.OWNER_IDS
        if not is_owner:
            await interaction.followup.send("You do not have a personal memory bank.", ephemeral=True)
            return
            
        await db.clear_channel_history(bot.user.id, interaction.user.id)
        await interaction.followup.send("Personal Memory wiped.", ephemeral=True)
        logger.info(f"Personal memory wiped for owner {interaction.user.display_name}")
    except Exception as e:
        logger.error(f"Failed to wipe personal memory: {e}")
        await interaction.followup.send("Failed to clear personal memory.", ephemeral=True)

@bot.tree.command(name="caption", description="Add meme text to an image.")
@app_commands.describe(image="The image to caption", top_text="Top text", bottom_text="Bottom text")
async def caption(interaction: discord.Interaction, image: discord.Attachment, top_text: str = "", bottom_text: str = ""):
    if not image.content_type or not image.content_type.startswith("image/"):
        await interaction.response.send_message("Please upload a valid image file.", ephemeral=True)
        return
    if not top_text and not bottom_text:
        await interaction.response.send_message("You must provide either top text or bottom text.", ephemeral=True)
        return

    await interaction.response.defer()
    image_bytes = await image.read()
    captioned_buffer = image_utils.add_caption_to_image(image_bytes, top_text.upper(), bottom_text.upper())
    
    if captioned_buffer:
        file = File(fp=captioned_buffer, filename="caption.jpg")
        await interaction.followup.send(content=f"Captioned by {interaction.user.mention}", file=file)
    else:
        await interaction.followup.send("Failed to process image.", ephemeral=True)

@bot.tree.command(name="imagine", description="Generate an image using Stable Diffusion.")
@app_commands.describe(prompt="Describe the image you want to create.")
async def imagine(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    profile = await db.get_or_create_profile(interaction.user.id, bot.user.id, str(interaction.user))
    
    last_gen_time = profile.get("last_imagine_timestamp")
    if last_gen_time and datetime.utcnow() < last_gen_time + timedelta(seconds=config.IMAGINE_COOLDOWN_SECONDS):
        remaining = (last_gen_time + timedelta(seconds=config.IMAGINE_COOLDOWN_SECONDS)) - datetime.utcnow()
        await interaction.followup.send(f"Cooldown active. Please wait {remaining.seconds} seconds.", ephemeral=True)
        return

    capabilities = get_model_capabilities()
    try:
        image_buffer = await generate_image(prompt, capabilities)
        await db.update_profile_imagine_timestamp(interaction.user.id, bot.user.id)
        file = File(fp=image_buffer, filename="generation.png")
        await interaction.followup.send(content=f"Prompt: {prompt}\nRequested by {interaction.user.mention}", file=file)
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        await interaction.followup.send("Image generation failed.", ephemeral=True)

settings_group = app_commands.Group(name="settings", description="Admin commands.")

@settings_group.command(name="view", description="View current bot settings.")
@app_commands.checks.has_permissions(administrator=True)
async def settings_view(interaction: discord.Interaction):
    content = f"Settings for {interaction.guild.name}\nBot configuration is running normally."
    await interaction.response.send_message(content=content, ephemeral=True)

@settings_group.command(name="toggle_info", description="Toggle footer metadata info.")
@app_commands.describe(show="True to show, False to hide")
@app_commands.checks.has_permissions(administrator=True)
async def settings_toggle_info(interaction: discord.Interaction, show: bool):
    await db.set_guild_setting(interaction.guild.id, bot.user.id, "show_footer_info", show)
    await interaction.response.send_message(f"Footer info visibility set to: {show}", ephemeral=True)

bot.tree.add_command(settings_group)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    original_error = getattr(error, 'original', error)
    await handle_error(original_error, interaction=interaction)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return

    is_owner = message.author.id in config.OWNER_IDS

    if not message.guild:
        if not config.ALLOW_DMS: return
        if not is_owner: return 
        context_id = message.author.id
    else:
        if config.TARGET_CHANNEL_IDS and message.channel.id not in config.TARGET_CHANNEL_IDS: return
        context_id = message.channel.id

    is_reply_to_bot = message.reference and message.reference.resolved and message.reference.resolved.author == bot.user
    is_mentioning_bot = bot.user.mentioned_in(message)
    is_dm = not message.guild

    if is_reply_to_bot or is_mentioning_bot or is_dm:
        text_query = message.content.replace(f'<@{bot.user.id}>', '').strip()
        
        file_attachment = None
        for attachment in message.attachments:
            if attachment.content_type and (attachment.content_type.startswith('image/') or attachment.content_type.startswith('audio/') or attachment.filename.endswith('.ogg')):
                file_attachment = attachment
                break
        
        if not text_query and not file_attachment: return

        lock_key = message.guild.id if message.guild else message.author.id
        lock = bot.channel_locks.setdefault(lock_key, asyncio.Lock())

        async with lock:
            async with message.channel.typing():
                final_query = text_query or "Process this attachment."
                
                if file_attachment:
                    capabilities = get_model_capabilities()
                    if not capabilities.get("supports_vision", False):
                        await message.channel.send("This feature is currently disabled by the administrator.", reference=message)
                        return

                guild_id = message.guild.id if message.guild else None
                guild_name = message.guild.name if message.guild else None
                channel_name = message.channel.name if message.guild else "direct_message"

                await db.save_message(
                    bot.user.id, guild_id, guild_name, context_id, channel_name, 
                    message.id, message.author.id, message.author.display_name, "user", final_query
                )
                
                await process_ai_request(
                    final_query, message.author, context_id, is_owner, guild_id, guild_name, channel_name,
                    message=message, file_attachment=file_attachment
                )

@bot.event
async def on_guild_channel_delete(channel):
    logger.info(f"Garbage Collection: Cleaning up deleted channel {channel.id}")
    await db.delete_channel_records(bot.user.id, channel.id)

@bot.event
async def on_guild_remove(guild):
    logger.info(f"Garbage Collection: Bot removed from guild {guild.name}. Cleaning up.")
    for channel in guild.channels:
        await db.delete_channel_records(bot.user.id, channel.id)

async def setup_hook():
    logger.info("Initializing Database...")
    await db.init_db()
    logger.info("Loading Cogs...")
    await bot.load_extension("music_cog")
    
async def on_bot_ready():
    await bot.wait_until_ready()
    logger.info("Syncing slash commands...")
    await bot.tree.sync()

@bot.event
async def on_ready():
    activity_map = {
        "playing": Game(name=config.STATUS_MESSAGE),
        "streaming": Streaming(name=config.STATUS_MESSAGE, url="https://www.twitch.tv/monstercat"),
        "listening": discord.Activity(type=ActivityType.listening, name=config.STATUS_MESSAGE),
        "watching": discord.Activity(type=ActivityType.watching, name=config.STATUS_MESSAGE),
    }
    activity = activity_map.get(config.STATUS_TYPE)

    if activity:
        await bot.change_presence(status=discord.Status.online, activity=activity)

    logger.info(f"Bot '{bot.user}' is ready.")
    bot.loop.create_task(on_bot_ready())

bot.setup_hook = setup_hook

if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        raise SystemExit("FATAL: DISCORD_TOKEN missing in .env.")
    bot.run(config.DISCORD_TOKEN)