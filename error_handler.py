import discord
import asyncio
import logging
from typing import Optional
from image_client import ImageGenerationError

logger = logging.getLogger("error_handler")

async def handle_error(error: Exception, interaction: Optional[discord.Interaction] = None, message: Optional[discord.Message] = None):
    error_msg = "⚠️ An unexpected error occurred. The developers have been notified."
    ephemeral = True 

    if isinstance(error, ImageGenerationError):
        error_msg = f"🎨 Image generation failed: {error}"
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        error_msg = f"⏳ This command is on cooldown. Please try again in {error.retry_after:.2f} seconds."
    elif isinstance(error, discord.app_commands.MissingPermissions):
        error_msg = "🚫 You do not have the required permissions to use this command."
    elif isinstance(error, discord.errors.HTTPException):
        error_msg = "⚠️ A Discord API error occurred. Please try again later."
    elif isinstance(error, asyncio.TimeoutError):
        error_msg = "⚠️ The request timed out. Please try again."
    
    logger.error(f"An error occurred: {error}", exc_info=True)

    try:
        if interaction:
            if interaction.response.is_done():
                await interaction.followup.send(error_msg, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(error_msg, ephemeral=ephemeral)
        elif message:
            await message.channel.send(error_msg, reference=message, delete_after=20)
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")