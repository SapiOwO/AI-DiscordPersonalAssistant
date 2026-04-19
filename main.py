import os
os.environ.pop("SSLKEYLOGFILE", None)

import asyncio
import logging
import base64
import re
import random
import io
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from collections import defaultdict, deque

import discord
from discord import app_commands, Intents, File, Game, Streaming, ActivityType
from discord.ext import commands, tasks

import db
import config
import image_utils
import memory_manager
import audio_manager
from error_handler import handle_error
from ai_client import make_ollama_client, chat_with_model, get_model_capabilities
from session_manager import prepare_model_messages
from utils import parse_thinking_and_response, chunk_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("discord_ai_main")

intents = Intents.default()
intents.message_content = True
intents.voice_states = True 

bot = commands.Bot(command_prefix="!", intents=intents)
bot.channel_locks = {}

ram_buffers = defaultdict(lambda: deque(maxlen=20))
dynamic_configs = {}
afk_tracker = {}

vision_cache = {}
VISION_CACHE_MAX_TURNS = 5

global_last_active = datetime.now()
current_bot_status = discord.Status.online

def clean_text(text: str) -> str:
    return re.sub(r'[^a-z0-9\s]', '', text.lower()).strip()

_INJECTION_PATTERNS = [
    r'ignore (?:all )?previous (?:instructions|prompts|directives)',
    r'(?:output|reveal|show|print|display) (?:your |the )?system prompt',
    r'you are now (?:a |an )',
    r'new instructions?:',
    r'forget (?:all |everything)',
    r'disregard (?:all |your )',
    r'override (?:your |all )',
    r'act as (?:if |though )?(?:you are |a )',
]
_INJECTION_RE = re.compile('|'.join(_INJECTION_PATTERNS), flags=re.IGNORECASE)

def sanitize_memory_text(text: str) -> str:
    return _INJECTION_RE.sub('[REDACTED]', text)

def get_current_activity():
    activity_map = {
        "playing": Game(name=config.STATUS_MESSAGE),
        "streaming": Streaming(name=config.STATUS_MESSAGE, url="https://www.twitch.tv/monstercat"),
        "listening": discord.Activity(type=ActivityType.listening, name=config.STATUS_MESSAGE),
        "watching": discord.Activity(type=ActivityType.watching, name=config.STATUS_MESSAGE),
    }
    return activity_map.get(config.STATUS_TYPE)

def parse_reminder_intent(text: str) -> int:
    text_lower = text.lower()
    explicit_pattern = r'\b(brb|wait|gimme|give me|wake me up|remind me|hold on).*?(\d+)\s*(h|hr|hour|m|min|minute|s|sec|second)s?\b'
    match = re.search(explicit_pattern, text_lower)
    
    if match:
        val = int(match.group(2))
        unit = match.group(3)
        if unit.startswith('h'): return val * 3600
        elif unit.startswith('m'): return val * 60
        elif unit.startswith('s'): return val
        return 0
        
    implicit_pattern = r'\b(brb|be right back|wait|gimme a sec|give me a sec|hold on|1 sec|one sec|1 min|one min)\b'
    if re.search(implicit_pattern, text_lower):
        return random.randint(120, 300)
        
    return 0

async def schedule_smart_reminder(delay_seconds: int, user: discord.User, context_id: int, is_owner: bool, guild_id: Optional[int], guild_name: Optional[str], channel_name: str, channel_topic: Optional[str], original_text: str):
    await asyncio.sleep(delay_seconds)
    lock_key = guild_id if guild_id else user.id
    lock = bot.channel_locks.setdefault(lock_key, asyncio.Lock())
    
    async with lock:
        await process_ai_request(
            query="[SYSTEM REMINDER TRIGGER]",
            user=user,
            context_id=context_id,
            is_owner=is_owner,
            guild_id=guild_id,
            guild_name=guild_name,
            channel_name=channel_name,
            channel_topic=channel_topic,
            is_reminder_ping=True,
            reminder_delay=delay_seconds,
            reminder_text=original_text
        )

async def _gather_ai_context(query: str, user: discord.User, context_id: int, is_owner: bool, guild_id: Optional[int], guild_name: Optional[str], channel_name: str, channel_topic: Optional[str], include_ram: bool = False, skip_rag: bool = False) -> Dict[str, Any]:
    bot_id = bot.user.id
    
    persona_enabled = False
    custom_persona = None
    if guild_id:
        persona_enabled_str = await db.get_guild_setting(guild_id, bot_id, "persona_enabled")
        persona_enabled = persona_enabled_str == "True"
        custom_persona = await db.get_guild_setting(guild_id, bot_id, "persona_text")

    history_limit = 100 if is_owner else 30
    
    pass_guild_id = guild_id if config.OMNIPRESENT_MEMORY else None

    tasks_dict = {
        "channel_history": db.load_conversation_context(
            bot_id, 
            context_id, 
            limit=history_limit, 
            guild_id=pass_guild_id
        )
    }
    
    if not skip_rag:
        tasks_dict["long_term_memories"] = memory_manager.search_memory(user.id, query, n_results=3)
    
    results = await asyncio.gather(*tasks_dict.values())
    context = dict(zip(tasks_dict.keys(), results))
    
    if include_ram and context_id in ram_buffers:
        ram_history = list(ram_buffers[context_id])
        formatted_ram = [{"role": "user", "username": msg["author_name"], "content": f"[#{msg['channel_name']}] {msg['content']}"} for msg in ram_history]
        context["channel_history"] = context["channel_history"] + formatted_ram

    context.update({
        "query": query,
        "user": user,
        "context_id": context_id,
        "guild_id": guild_id,
        "guild_name": guild_name,
        "channel_name": channel_name,
        "channel_topic": channel_topic,
        "custom_persona": custom_persona if persona_enabled else None,
        "search_results": []
    })
    
    return context

async def _generate_ai_response(context: Dict[str, Any], is_afk_ping: bool = False, ping_count: int = 0, is_sleep_wakeup: bool = False, hours_asleep: int = 0, is_reminder_ping: bool = False, reminder_delay: int = 0, reminder_text: str = "") -> Tuple[Optional[str], Optional[Dict]]:
    raw_query = context["query"]
    speaker_name = context["user"].display_name
    speaker_id = context["user"].id
    guild_name = context.get("guild_name")
    channel_name = context.get("channel_name")
    channel_topic = context.get("channel_topic")

    current_time = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    
    location_context = f"Current Local Time: {current_time}."
    if guild_name:
        location_context += f" You are in server '{guild_name}', channel [#{channel_name}]."
        if channel_topic:
            location_context += f" Channel Topic: '{channel_topic}'."
    else:
        location_context += " You are in a private Direct Message."

    memory_injection = ""
    if context.get("long_term_memories"):
        sanitized_memories = sanitize_memory_text(context['long_term_memories'])
        memory_injection = f"--- MEMORY RECALL ---\n{sanitized_memories}\n"

    burst_mode = os.getenv("BURST_TYPING_MODE", "True").lower() in ("true", "1", "yes")
    voice_mode = context.get("voice_mode", False)

    base_persona = context.get("custom_persona") or config.DEFAULT_PERSONA
    dynamic_system_prompt = (
        f"{base_persona}\n\n"
        f"[SYSTEM AWARENESS - DO NOT REPEAT OR ACKNOWLEDGE THIS BLOCK]\n"
        f"{location_context}\n"
        f"{memory_injection}"
        f"The user speaking right now is {speaker_name}."
    ).strip()
    
    context["custom_persona"] = dynamic_system_prompt

    if is_reminder_ping:
        delay_str = f"{reminder_delay // 3600} hours" if reminder_delay >= 3600 else f"{reminder_delay // 60} minutes"
        sanitized_query = f"[SYSTEM COMMAND]: The user <@{speaker_id}> asked for a reminder '{reminder_text}' {delay_str} ago. Reach out to them naturally. You must include <@{speaker_id}>."
    elif is_afk_ping:
        if is_sleep_wakeup:
            sanitized_query = f"[SYSTEM COMMAND]: The user <@{speaker_id}> went to sleep ~{hours_asleep} hours ago. Wake them up naturally. You must include <@{speaker_id}>."
        else:
            sanitized_query = f"[SYSTEM COMMAND]: The user <@{speaker_id}> has been AFK. Reach out proactively. You must include <@{speaker_id}>."
    else:
        sanitized_query = raw_query

    capabilities = get_model_capabilities()
    use_thinking = capabilities.get("supports_thinking", False)

    messages = prepare_model_messages(
        context["channel_history"],
        sanitized_query,
        context["search_results"],
        file_data=context.get("file_data"),
        use_thinking=use_thinking,
        burst_mode=burst_mode,
        voice_mode=voice_mode,
        custom_persona=context["custom_persona"],
    )
    
    client = make_ollama_client()
    text, meta = await chat_with_model(client, model=config.OLLAMA_MODEL, messages=messages)
    
    trigger_message = context.get("interaction") or context.get("message")
    
    db_response_text = text.replace('|', ' ').replace('\n', ' ') if burst_mode else text
    await db.save_message(
        bot.user.id, context.get("guild_id"), guild_name, context["context_id"], channel_name,
        trigger_message.id if trigger_message else None, 
        bot.user.id, bot.user.display_name, "assistant", db_response_text
    )
    
    return text, meta

async def _format_and_send_response(response_text: str, meta: Optional[Dict], context: Dict[str, Any], voice_reply: bool = False):
    if "[Response]" in response_text:
        response_text = response_text.split("[Response]")[-1]
    
    response_text = re.sub(r'\[Thinking.*?\]', '', response_text, flags=re.IGNORECASE|re.DOTALL)
    response_text = re.sub(r'<[^>]+>', '', response_text) 
    response_text = response_text.replace('>', '').strip()

    thinking_text, main_response = parse_thinking_and_response(response_text)
    target_channel = context.get("interaction").channel if context.get("interaction") else (context.get("message").channel if context.get("message") else bot.get_channel(context["context_id"]) or await bot.fetch_user(context["context_id"]))

    if voice_reply:
        async with target_channel.typing():
            clean_tts_text = main_response.replace('|', ' ').replace('\n', ' ')
            audio_data = await audio_manager.synthesize(clean_tts_text)
            
            if audio_data:
                voice_file = discord.File(fp=io.BytesIO(audio_data), filename="voice_note.ogg")
                if context.get("message"):
                    await target_channel.send(file=voice_file, reference=context.get("message"))
                else:
                    await target_channel.send(file=voice_file)
            else:
                await target_channel.send(config.RESPONSE_TEMPLATES["audio_failed"])
        return 

    sent_initial = False
    burst_mode = os.getenv("BURST_TYPING_MODE", "True").lower() in ("true", "1", "yes")

    if thinking_text:
        think_chunks = list(chunk_text(f"> *{thinking_text}*\n", size=1950))
        for tc in think_chunks:
            if not sent_initial and context.get("interaction"):
                await context.get("interaction").followup.send(content=tc)
                sent_initial = True
            elif not sent_initial and context.get("message"):
                await context.get("message").channel.send(content=tc, reference=context.get("message"))
                sent_initial = True
            else:
                await target_channel.send(content=tc)

    if burst_mode:
        normalized_response = main_response.replace('\n', '|')
        raw_chunks = normalized_response.split('|')
        valid_chunks = [c.strip() for c in raw_chunks if c.strip()]
    else:
        valid_chunks = [main_response.strip()]

    for i, chunk in enumerate(valid_chunks):
        if not chunk: continue
        sub_chunks = list(chunk_text(chunk, size=1950))
        for d_chunk in sub_chunks:
            typing_time = min(len(d_chunk) * 0.04, 3.5) if burst_mode else 1.0
            
            async with target_channel.typing():
                await asyncio.sleep(typing_time)
            
            if not sent_initial and context.get("interaction"):
                await context.get("interaction").followup.send(content=d_chunk)
                sent_initial = True
            elif not sent_initial and context.get("message"):
                await context.get("message").channel.send(content=d_chunk, reference=context.get("message"))
                sent_initial = True
            else:
                await target_channel.send(content=d_chunk)

async def process_ai_request(
    query: str, user: discord.User, context_id: int, is_owner: bool, guild_id: Optional[int], guild_name: Optional[str], channel_name: str, channel_topic: Optional[str],
    interaction: Optional[discord.Interaction] = None, message: Optional[discord.Message] = None,
    file_attachment: Optional[discord.Attachment] = None, include_ram: bool = False, is_afk_ping: bool = False, ping_count: int = 0, is_sleep_wakeup: bool = False, hours_asleep: int = 0,
    is_reminder_ping: bool = False, reminder_delay: int = 0, reminder_text: str = ""
):
    target_channel = None
    if interaction:
        target_channel = interaction.channel
    elif message:
        target_channel = message.channel

    try:
        if include_ram and context_id in ram_buffers:
            ram_history = list(ram_buffers[context_id])
            if ram_history and getattr(message, 'id', None) == ram_history[-1]["message_id"]:
                ram_history.pop()
            
            for rm in ram_history:
                await db.save_message(
                    bot.user.id, guild_id, guild_name, context_id, channel_name, 
                    rm["message_id"], rm["author_id"], rm["author_name"], "user", rm["content"]
                )
            ram_buffers[context_id].clear()

        skip_rag = is_afk_ping or is_reminder_ping
        should_voice_reply = False
        file_bytes = None
        image_b64 = None
        is_new_image = False

        if file_attachment:
            try:
                file_bytes = await file_attachment.read()
            except Exception as e:
                logger.error(f"Failed to download attachment '{file_attachment.filename}': {e}")
                if target_channel:
                    await target_channel.send(config.RESPONSE_TEMPLATES["error_download"])
                return

            content_type = file_attachment.content_type or ""
            filename_lower = (file_attachment.filename or "").lower()
            image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff')

            is_audio = (
                content_type.startswith('audio/') or
                filename_lower.endswith('.ogg') or
                filename_lower.endswith('.wav') or
                filename_lower.endswith('.mp3')
            )
            is_image = content_type.startswith('image/') or filename_lower.endswith(image_extensions)

            if is_audio:
                transcribed_text = await audio_manager.transcribe(file_bytes)
                if transcribed_text:
                    if query and query != "Process this.":
                        query = f"{query}\n[Voice Transcribed]: {transcribed_text}"
                    else:
                        query = f"[Voice Transcribed]: {transcribed_text}"
                    should_voice_reply = True
                else:
                    query += "\n\n[SYSTEM NOTE: User sent an inaudible or empty voice message.]"
                    should_voice_reply = True

            elif is_image:
                try:
                    compressed_bytes = image_utils.compress_image_for_ai(
                        file_bytes,
                        max_dimension=config.IMAGE_MAX_DIMENSION,
                        quality=config.IMAGE_COMPRESSION_QUALITY
                    )
                    image_b64 = base64.b64encode(compressed_bytes).decode('utf-8')
                    is_new_image = True
                    logger.info(f"Image processed: {len(file_bytes)} bytes -> {len(compressed_bytes)} compressed -> {len(image_b64)} b64 chars")

                    vision_cache[context_id] = {
                        "b64": image_b64,
                        "text_prompt": query,
                        "turn_count": 0,
                        "timestamp": datetime.now()
                    }
                    logger.info(f"Vision cache: Stored new image for context {context_id}")
                except Exception as e:
                    logger.error(f"Image compression/encoding failed: {e}")
                    query += "\n\n[SYSTEM NOTE: User sent an image but it could not be processed.]"

        vision_recall_note = ""
        if not image_b64 and context_id in vision_cache:
            cached = vision_cache[context_id]
            if cached["turn_count"] < VISION_CACHE_MAX_TURNS:
                image_b64 = cached["b64"]
                cached["turn_count"] += 1
                vision_recall_note = (
                    f"\n\n[SYSTEM NOTE: The user previously shared an image with the prompt: "
                    f"'{cached['text_prompt'][:200]}'. You are recalling that image now to answer their follow-up.]"
                )
                logger.debug(f"Vision cache: Recalled cached image (turn {cached['turn_count']}/{VISION_CACHE_MAX_TURNS})")
            else:
                del vision_cache[context_id]
                logger.debug(f"Vision cache: Expired for context {context_id}")

        clean_query_for_memory = query
        if message and not is_afk_ping and not is_reminder_ping:
            await db.save_message(
                bot.user.id, guild_id, guild_name, context_id, channel_name,
                message.id, message.author.id, message.author.display_name, "user", query
            )

        if vision_recall_note:
            query += vision_recall_note

        context = await _gather_ai_context(
            query, user, context_id, is_owner, guild_id, guild_name,
            channel_name, channel_topic, include_ram=include_ram, skip_rag=skip_rag
        )
        context.update({
            "interaction": interaction, 
            "message": message,
            "file_data": image_b64,
            "voice_mode": should_voice_reply
        })

        response_text, meta = await _generate_ai_response(
            context, is_afk_ping=is_afk_ping, ping_count=ping_count, 
            is_sleep_wakeup=is_sleep_wakeup, hours_asleep=hours_asleep,
            is_reminder_ping=is_reminder_ping, reminder_delay=reminder_delay, reminder_text=reminder_text
        )
        
        await _format_and_send_response(response_text, meta, context, voice_reply=should_voice_reply)

        if not skip_rag and not clean_query_for_memory.startswith("[SYSTEM"):
            msg_id_str = str(message.id) if message else str(int(datetime.now().timestamp()))
            thinking_text, clean_response = parse_thinking_and_response(response_text)

            user_memory_text = clean_query_for_memory
            if is_new_image:
                user_memory_text = f"{clean_query_for_memory} [Image was shared. AI observed: {clean_response[:300]}]"

            await memory_manager.save_memory(user.id, user.display_name, "user", user_memory_text, msg_id_str)
            await memory_manager.save_memory(
                user.id, bot.user.display_name, "assistant",
                clean_response.replace('|', ' ').replace('\n', ' '), f"ai_{msg_id_str}"
            )

    except asyncio.TimeoutError:
        logger.error(f"AI request timed out for user {user.display_name} in context {context_id}")
        if target_channel:
            await target_channel.send(config.RESPONSE_TEMPLATES["error_timeout"])
    except Exception as e:
        logger.error(f"Error in process_ai_request: {e}", exc_info=True)
        if target_channel:
            await target_channel.send(config.RESPONSE_TEMPLATES["error_generic"])

def reset_afk_timer(channel_id: int, user: discord.User, message_content: str = ""):
    if channel_id in dynamic_configs and dynamic_configs[channel_id].get("enable_afk"):
        msg_lower = message_content.lower()
        sleep_keywords = r'\b(sleep|goodnight|good night|goodbye|bye|night|cya)\b'
        is_sleep_intent = bool(re.search(sleep_keywords, msg_lower))

        if is_sleep_intent:
            min_h = int(os.getenv("SLEEP_AFK_MIN_HOURS", "7"))
            max_h = int(os.getenv("SLEEP_AFK_MAX_HOURS", "9"))
            delay_hours = random.randint(min_h, max_h)
            next_delay = timedelta(hours=delay_hours)
            logger.info(f"Sleep intent detected for {user.display_name}. Next ping in {delay_hours} hours.")
        else:
            min_m = int(os.getenv("AFK_MIN_MINUTES", "15"))
            max_m = int(os.getenv("AFK_MAX_MINUTES", "60"))
            next_delay = timedelta(minutes=random.randint(min_m, max_m))

        afk_tracker[channel_id] = {
            "last_active": datetime.now(),
            "target_user": user,
            "current_pings": 0,
            "next_delay": next_delay,
            "is_sleep": is_sleep_intent
        }

@tasks.loop(minutes=1)
async def presence_monitor_task():
    global global_last_active, current_bot_status
    now = datetime.now()
    idle_threshold = timedelta(minutes=5)
    
    activity = get_current_activity()
    new_status = discord.Status.idle if (now - global_last_active > idle_threshold) else discord.Status.online
    
    if current_bot_status != new_status:
        await bot.change_presence(status=new_status, activity=activity)
        current_bot_status = new_status

@tasks.loop(minutes=1)
async def afk_brain_task():
    global global_last_active, current_bot_status
    now = datetime.now()
    for channel_id, config_data in list(dynamic_configs.items()):
        if not config_data.get("enable_afk"):
            continue
            
        tracker = afk_tracker.get(channel_id)
        if not tracker:
            continue

        if tracker["current_pings"] >= config_data["max_pings"]:
            continue

        if now - tracker["last_active"] >= tracker["next_delay"]:
            tracker["current_pings"] += 1
            
            was_sleep = tracker.get("is_sleep", False)
            hours_asleep = int((now - tracker["last_active"]).total_seconds() // 3600)
            
            tracker["is_sleep"] = False
            
            min_followup = int(os.getenv("AFK_FOLLOWUP_MIN_MINUTES", "20"))
            max_followup = int(os.getenv("AFK_FOLLOWUP_MAX_MINUTES", "180"))
            new_delay_minutes = random.randint(min_followup, max_followup)
            tracker["next_delay"] = timedelta(minutes=new_delay_minutes)
            tracker["last_active"] = now

            channel = bot.get_channel(channel_id) or await bot.fetch_user(channel_id)
            if not channel:
                continue

            guild_id = channel.guild.id if hasattr(channel, "guild") else None
            guild_name = channel.guild.name if hasattr(channel, "guild") else None
            channel_name = channel.name if hasattr(channel, "name") else "direct_message"
            channel_topic = getattr(channel, 'topic', None)

            is_owner = tracker["target_user"].id in config.OWNER_IDS
            
            global_last_active = datetime.now()
            if current_bot_status != discord.Status.online:
                await bot.change_presence(status=discord.Status.online, activity=get_current_activity())
                current_bot_status = discord.Status.online

            lock_key = guild_id if guild_id else tracker["target_user"].id
            lock = bot.channel_locks.setdefault(lock_key, asyncio.Lock())
            
            async with lock:
                await process_ai_request(
                    query="[SYSTEM AFK TRIGGER]", 
                    user=tracker["target_user"], 
                    context_id=channel_id, 
                    is_owner=is_owner, 
                    guild_id=guild_id, 
                    guild_name=guild_name, 
                    channel_name=channel_name, 
                    channel_topic=channel_topic,
                    is_afk_ping=True,
                    ping_count=tracker["current_pings"],
                    is_sleep_wakeup=was_sleep,
                    hours_asleep=hours_asleep
                )

@bot.tree.command(name="dynamic_ai", description="ADMIN ONLY: Configure Context RAM Buffer & Proactive AFK Pings.")
@app_commands.describe(enable_context="Enable RAM buffer & Trigger Words", enable_afk="Enable AI proactively pinging inactive users", max_pings="Max times AI will ping before sleeping")
@app_commands.checks.has_permissions(administrator=True)
async def dynamic_ai(interaction: discord.Interaction, enable_context: bool, enable_afk: bool = False, max_pings: int = 5):
    if not enable_afk and max_pings != 5:
        await interaction.response.send_message("Configuration Error: You cannot set `max_pings` if `enable_afk` is set to False. Please set `enable_afk` to True to use this feature.", ephemeral=True)
        return

    channel_id = interaction.channel.id
    guild_id = interaction.guild.id if interaction.guild else None

    if not enable_context and not enable_afk:
        if channel_id in dynamic_configs:
            del dynamic_configs[channel_id]
        if channel_id in ram_buffers:
            ram_buffers[channel_id].clear()
        if channel_id in afk_tracker:
            del afk_tracker[channel_id]
        await db.remove_dynamic_config(channel_id)
        await interaction.response.send_message("Dynamic AI fully DISABLED. AI is now strictly reactive.", ephemeral=True)
        return

    dynamic_configs[channel_id] = {
        "enable_context": enable_context,
        "enable_afk": enable_afk,
        "max_pings": max_pings
    }
    await db.save_dynamic_config(channel_id, guild_id, enable_context, enable_afk, max_pings)
    
    if enable_afk:
        reset_afk_timer(channel_id, interaction.user, "")

    msg = f"Dynamic AI Configured:\n- Context RAM Buffer: {'ON' if enable_context else 'OFF'}\n- AFK Pings: {'ON' if enable_afk else 'OFF'} (Max {max_pings} pings)"
    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="history", description="View recent messages in this conversational scope.")
@app_commands.describe(user="Optional: Filter by specific user.")
async def history(interaction: discord.Interaction, user: Optional[discord.User] = None):
    await interaction.response.defer(ephemeral=True)
    bot_id = bot.user.id
    
    is_owner = interaction.user.id in config.OWNER_IDS
    context_id = interaction.user.id if not interaction.guild else interaction.channel.id
    guild_id = interaction.guild.id if interaction.guild else None
    
    pass_guild_id = guild_id if config.OMNIPRESENT_MEMORY else None

    if user:
        message_history = await db.load_user_history_in_channel(bot_id, context_id, user.id, limit=10)
        title = f"Recent History for {user.display_name}"
    else:
        message_history = await db.load_conversation_context(bot_id, context_id, limit=10, guild_id=pass_guild_id)
        title = "Recent Context History (Guild Scope)" if pass_guild_id else "Recent Context History (Channel Scope)"

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
        if interaction.channel.id in ram_buffers:
            ram_buffers[interaction.channel.id].clear()
        if interaction.channel.id in vision_cache:
            del vision_cache[interaction.channel.id]
        await interaction.followup.send(config.RESPONSE_TEMPLATES["memory_wiped_channel"])
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
        if interaction.user.id in ram_buffers:
            ram_buffers[interaction.user.id].clear()
        if interaction.user.id in vision_cache:
            del vision_cache[interaction.user.id]
        await interaction.followup.send(config.RESPONSE_TEMPLATES["memory_wiped_personal"], ephemeral=True)
    except Exception as e:
        logger.error(f"Failed to wipe personal memory: {e}")
        await interaction.followup.send("Failed to clear personal memory.", ephemeral=True)

@bot.tree.command(name="tts", description="Generate text-to-speech audio directly")
@app_commands.describe(text="The text you want the bot to say")
async def tts_command(interaction: discord.Interaction, text: str):
    await interaction.response.defer()
    
    try:
        audio_bytes = await audio_manager.synthesize(text)
        
        if audio_bytes:
            voice_file = discord.File(fp=io.BytesIO(audio_bytes), filename="tts_test.ogg")
            await interaction.followup.send(content=f'> **TTS:** {text}', file=voice_file)
        else:
            await interaction.followup.send("Failed to generate TTS audio.")
    except Exception as e:
        logger.error(f"TTS command error: {e}", exc_info=True)
        await interaction.followup.send("An unexpected error occurred while generating TTS.")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    original_error = getattr(error, 'original', error)
    await handle_error(original_error, interaction=interaction)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return

    global global_last_active, current_bot_status
    
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

    channel_config = dynamic_configs.get(context_id, {})
    is_dynamic_context = channel_config.get("enable_context", False)
    
    should_respond = is_reply_to_bot or is_mentioning_bot or is_dm
    include_ram = False

    if is_dynamic_context and not is_dm:
        ram_buffers[context_id].append({
            "author_id": message.author.id,
            "author_name": message.author.display_name,
            "content": message.content,
            "channel_name": message.channel.name,
            "message_id": message.id
        })

    if not should_respond and is_dynamic_context:
        env_triggers = [clean_text(w) for w in os.getenv("TRIGGER_WORDS", "bot,ai").split(',')]
        trigger_words = set(env_triggers)
        bot_name_clean = clean_text(bot.user.name)
        trigger_words.add(bot_name_clean)
        if bot_name_clean:
            trigger_words.add(bot_name_clean.split()[0])
            
        if message.guild and message.guild.me:
            bot_display_clean = clean_text(message.guild.me.display_name)
            trigger_words.add(bot_display_clean)
            if bot_display_clean:
                trigger_words.add(bot_display_clean.split()[0])
            
        msg_clean = clean_text(message.content)
        if any(re.search(rf'\b{re.escape(w)}\b', msg_clean) for w in trigger_words if w):
            should_respond = True
            include_ram = True

    if should_respond:
        reset_afk_timer(context_id, message.author, message.content)
        global_last_active = datetime.now()
        if current_bot_status != discord.Status.online:
            await bot.change_presence(status=discord.Status.online, activity=get_current_activity())
            current_bot_status = discord.Status.online
            
        reminder_delay = parse_reminder_intent(message.content)
        if reminder_delay > 0:
            guild_id = message.guild.id if message.guild else None
            guild_name = message.guild.name if message.guild else None
            channel_name = message.channel.name if message.guild else "direct_message"
            channel_topic = getattr(message.channel, 'topic', None) if message.guild else None
            
            bot.loop.create_task(schedule_smart_reminder(
                reminder_delay, message.author, context_id, is_owner, guild_id, guild_name, channel_name, channel_topic, message.content
            ))

    elif channel_config.get("enable_afk"):
        reset_afk_timer(context_id, message.author, message.content)

    if not should_respond:
        return

    text_query = message.content.replace(f'<@{bot.user.id}>', '').strip()
    
    file_attachment = None
    
    for attachment in message.attachments:
        if attachment.content_type and (attachment.content_type.startswith('image/') or attachment.content_type.startswith('audio/') or attachment.filename.endswith('.ogg')):
            file_attachment = attachment
            break
            
    if not text_query and not file_attachment and not include_ram: return

    lock_key = message.guild.id if message.guild else message.author.id
    lock = bot.channel_locks.setdefault(lock_key, asyncio.Lock())

    async with lock:
        async with message.channel.typing():
            final_query = text_query or "Process this."
            
            guild_id = message.guild.id if message.guild else None
            guild_name = message.guild.name if message.guild else None
            channel_name = message.channel.name if message.guild else "direct_message"
            channel_topic = getattr(message.channel, 'topic', None) if message.guild else None

            await process_ai_request(
                final_query, message.author, context_id, is_owner, guild_id, guild_name, channel_name, channel_topic,
                message=message, file_attachment=file_attachment, include_ram=include_ram
            )

@bot.event
async def on_guild_channel_delete(channel):
    await db.delete_channel_records(bot.user.id, channel.id)
    if channel.id in ram_buffers: del ram_buffers[channel.id]
    if channel.id in dynamic_configs: del dynamic_configs[channel.id]
    if channel.id in afk_tracker: del afk_tracker[channel.id]
    if channel.id in vision_cache: del vision_cache[channel.id]

@bot.event
async def on_guild_remove(guild):
    for channel in guild.channels:
        await db.delete_channel_records(bot.user.id, channel.id)
        if channel.id in ram_buffers: del ram_buffers[channel.id]
        if channel.id in dynamic_configs: del dynamic_configs[channel.id]
        if channel.id in afk_tracker: del afk_tracker[channel.id]
        if channel.id in vision_cache: del vision_cache[channel.id]

async def setup_hook():
    logger.info("Initializing Database...")
    await db.init_db()
    
    global dynamic_configs
    dynamic_configs = await db.get_all_dynamic_configs()
    logger.info(f"Loaded {len(dynamic_configs)} dynamic channel configurations.")

    logger.info("Initializing Native Audio Systems...")
    await audio_manager.init_models()

    logger.info("Loading Cogs...")
    await bot.load_extension("music_cog")
    
async def on_bot_ready():
    await bot.wait_until_ready()
    logger.info("Syncing slash commands...")
    await bot.tree.sync()
    
    if not afk_brain_task.is_running():
        afk_brain_task.start()
        logger.info("Cron-Brain (AFK Monitor) started.")
        
    if not presence_monitor_task.is_running():
        presence_monitor_task.start()
        logger.info("Presence Monitor started.")

@bot.event
async def on_ready():
    activity = get_current_activity()
    if activity:
        await bot.change_presence(status=discord.Status.online, activity=activity)

    logger.info(f"Bot '{bot.user}' is ready.")
    bot.loop.create_task(on_bot_ready())

bot.setup_hook = setup_hook

if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        raise SystemExit("FATAL: DISCORD_TOKEN missing in .env.")
    bot.run(config.DISCORD_TOKEN)