import discord
import asyncio
from services.audio_service import AudioService
from models.database import SessionLocal
from services.settings_service import SettingsService

async def voice_rejoin_task(bot, audio_service: AudioService):
    """Background task to automatically rejoin the last active voice channel for each guild on bot startup."""
    # Wait for the bot to be ready
    await bot.wait_until_ready()
    
    # Give it a few seconds more just in case
    await asyncio.sleep(5)
    
    db = SessionLocal()
    try:
        # Fetch all guilds with a non-null last_voice_channel_id from the database
        results = SettingsService.get_all_guild_settings(db, "last_voice_channel_id")
        
        for guild_id_str, channel_id_str in results.items():
            if not channel_id_str:
                continue
                
            try:
                guild_id = int(guild_id_str)
                channel_id = int(channel_id_str)
            except (ValueError, TypeError):
                continue
                
            guild = bot.get_guild(guild_id)
            if not guild:
                continue
                
            # Skip if already connected to a voice channel in this guild
            if guild.voice_client and guild.voice_client.is_connected():
                continue
                
            print(f"[VoiceMonitor] Attempting to rejoin voice channel {channel_id} in guild {guild.name} ({guild.id})...")
            
            # Attempt to join the channel via AudioService.connect_to_voice
            # Note: connect_to_voice is a classmethod, so we can call it on the class or instance
            voice_client, error = await audio_service.connect_to_voice(guild, channel_id)
            
            if error:
                print(f"[VoiceMonitor] Failed to rejoin voice channel {channel_id} in guild {guild.name}: {error}")
            else:
                print(f"[VoiceMonitor] Successfully rejoined voice channel {channel_id} in guild {guild.name}.")
                
            # Introduce a 5-second delay between rejoin attempts to handle rate limiting
            await asyncio.sleep(5)
            
    finally:
        db.close()
