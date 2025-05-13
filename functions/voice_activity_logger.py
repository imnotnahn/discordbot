import discord
from discord.ext import commands
import logging
import datetime
import os

# Setup logger
logger = logging.getLogger('discord_bot.voice_logger')

class VoiceActivityLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_dir = './logs'
        
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Log when users join or leave voice channels"""
        
        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            self._log_voice_activity(member, after.channel, "joined")
            
        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            self._log_voice_activity(member, before.channel, "left")
            
        # User switched voice channels
        elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            self._log_voice_activity(member, before.channel, "left")
            self._log_voice_activity(member, after.channel, "joined")
    
    def _log_voice_activity(self, member: discord.Member, channel: discord.VoiceChannel, action: str):
        """Write voice activity to log file"""
        # Get current time
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format log message
        log_message = f"{timestamp} | {member.name} ({member.id}) {action} voice channel '{channel.name}' in guild '{channel.guild.name}'\n"
        
        # Create log file with guild ID to separate logs by server
        log_file_path = os.path.join(self.log_dir, f"voice_activity_{channel.guild.id}.log")
        
        # Write to log file
        try:
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(log_message)
            logger.info(f"Voice activity logged: {member.name} {action} {channel.name}")
        except Exception as e:
            logger.error(f"Failed to log voice activity: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceActivityLogger(bot))