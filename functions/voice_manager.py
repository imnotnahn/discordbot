import discord
from discord.ext import commands, tasks
import asyncio
import logging
from typing import Dict, List, Set, Optional, Union

logger = logging.getLogger('discord_bot')

class VoiceChannelManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_channels: Dict[int, Dict] = {}
        
        self.config = bot.config.get('voice_manager', {})
        self.create_channel_name = self.config.get('create_channel_name', 'tạo phòng')
        self.auto_cleanup = self.config.get('auto_cleanup', True)
        self.cleanup_delay = self.config.get('cleanup_delay_seconds', 5)
        
        if self.auto_cleanup:
            self.check_empty_channels.start()
        
        logger.info(f"🔊 Voice Manager initialized - Create channel: '{self.create_channel_name}'")
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        if hasattr(self, 'check_empty_channels'):
            self.check_empty_channels.cancel()
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle voice state changes for auto-creation and cleanup"""
        try:
            if after.channel and after.channel.name.lower() == self.create_channel_name.lower():
                await self.create_voice_channel(member)
                return
            
            if before.channel and before.channel.id in self.voice_channels:
                await asyncio.sleep(self.cleanup_delay)
                await self.check_channel_empty(before.channel)
        
        except Exception as e:
            logger.error(f"Error in voice state update handler: {e}")
    
    async def create_voice_channel(self, member: discord.Member):
        """Create a private voice channel for the user"""
        try:
            guild = member.guild
            category = None
            
            for channel in guild.channels:
                if channel.name.lower() == self.create_channel_name.lower():
                    category = channel.category
                    break
            
            channel_name = f"🔊 {member.display_name}'s Room"
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=True, speak=True),
                member: discord.PermissionOverwrite(
                    manage_channels=True,
                    manage_permissions=True,
                    move_members=True,
                    mute_members=True,
                    deafen_members=True,
                    priority_speaker=True
                )
            }
            
            new_channel = await guild.create_voice_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"Auto-created voice room for {member.display_name}"
            )
            
            self.voice_channels[new_channel.id] = {
                'owner_id': member.id,
                'co_owners': set(),
                'created_at': discord.utils.utcnow()
            }
            
            await member.move_to(new_channel)
            
            # Send a welcome message
            embed = discord.Embed(
                title="🎉 Voice Room Created!",
                description=f"**{member.display_name}** created a private voice room!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="🛡️ Your Permissions",
                value=(
                    "• **Full control** over this channel\n"
                    "• **Move, mute, deafen** other users\n"
                    "• **Manage permissions** for specific users\n"
                    "• **Rename** the channel\n"
                    "• **Add co-owners** with `/voice_add_owner`"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🔧 Useful Commands",
                value=(
                    "• `/voice_rename <name>` - Rename your channel\n"
                    "• `/voice_limit <number>` - Set user limit (0 = unlimited)\n"
                    "• `/voice_add_owner @user` - Add co-owner\n"
                    "• `/voice_remove_owner @user` - Remove co-owner\n"
                    "• `/voice_lock` - Lock channel (only you can join)\n"
                    "• `/voice_unlock` - Unlock channel"
                ),
                inline=False
            )
            
            embed.set_footer(text="🗑️ Channel will be deleted when empty")
            
            # Try to send to the user's DM first, then to the channel
            try:
                await member.send(embed=embed)
            except discord.Forbidden:
                # If DM fails, send to the voice channel's text equivalent or guild
                text_channels = [ch for ch in guild.text_channels if ch.category == category]
                if text_channels:
                    await text_channels[0].send(f"{member.mention}", embed=embed, delete_after=60)
            
            logger.info(f"Created voice channel '{channel_name}' for {member.display_name}")
        
        except Exception as e:
            logger.error(f"Error creating voice channel for {member.display_name}: {e}")
            try:
                await member.send(f"❌ Failed to create voice room: {str(e)}")
            except:
                pass
    
    async def check_channel_empty(self, channel: discord.VoiceChannel):
        """Check if a managed channel is empty and delete if so"""
        try:
            if channel.id not in self.voice_channels:
                return
            
            if len(channel.members) == 0:
                await channel.delete(reason="Voice room empty - auto cleanup")
                del self.voice_channels[channel.id]
                logger.info(f"Deleted empty voice channel: {channel.name}")
        
        except discord.NotFound:
            # Channel already deleted
            if channel.id in self.voice_channels:
                del self.voice_channels[channel.id]
        except Exception as e:
            logger.error(f"Error checking empty channel {channel.name}: {e}")
    
    @tasks.loop(minutes=5)
    async def check_empty_channels(self):
        """Periodic task to clean up empty channels"""
        try:
            channels_to_remove = []
            
            for channel_id in list(self.voice_channels.keys()):
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    # Channel doesn't exist anymore
                    channels_to_remove.append(channel_id)
                elif len(channel.members) == 0:
                    # Channel is empty
                    try:
                        await channel.delete(reason="Periodic cleanup - empty voice room")
                        channels_to_remove.append(channel_id)
                        logger.info(f"Periodic cleanup: deleted {channel.name}")
                    except Exception as e:
                        logger.error(f"Error deleting channel {channel.name}: {e}")
            
            # Remove from tracking
            for channel_id in channels_to_remove:
                if channel_id in self.voice_channels:
                    del self.voice_channels[channel_id]
        
        except Exception as e:
            logger.error(f"Error in periodic channel cleanup: {e}")
    
    @check_empty_channels.before_loop
    async def before_check_empty_channels(self):
        """Wait for bot to be ready before starting the loop"""
        await self.bot.wait_until_ready()
    
    def is_channel_owner_or_admin(self, channel_id: int, user: discord.Member) -> bool:
        """Check if user is channel owner, co-owner, or admin"""
        if user.guild_permissions.administrator:
            return True
        
        if channel_id not in self.voice_channels:
            return False
        
        channel_info = self.voice_channels[channel_id]
        return (user.id == channel_info['owner_id'] or 
                user.id in channel_info.get('co_owners', set()))
    
    @commands.hybrid_command(name="voice_rename", description="Rename your voice channel")
    async def rename_voice_channel(self, ctx: commands.Context, *, new_name: str):
        """Rename a voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ You must be in a voice channel to use this command.")
        
        channel = ctx.author.voice.channel
        
        if not self.is_channel_owner_or_admin(channel.id, ctx.author):
            return await ctx.send("❌ You don't have permission to rename this channel.")
        
        if len(new_name) > 50:
            return await ctx.send("❌ Channel name must be 50 characters or less.")
        
        try:
            old_name = channel.name
            await channel.edit(name=new_name, reason=f"Renamed by {ctx.author}")
            
            embed = discord.Embed(
                title="✅ Channel Renamed",
                description=f"**{old_name}** → **{new_name}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to rename channel: {str(e)}")
    
    @commands.hybrid_command(name="voice_limit", description="Set user limit for your voice channel")
    async def set_voice_limit(self, ctx: commands.Context, limit: int):
        """Set user limit for a voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ You must be in a voice channel to use this command.")
        
        channel = ctx.author.voice.channel
        
        if not self.is_channel_owner_or_admin(channel.id, ctx.author):
            return await ctx.send("❌ You don't have permission to modify this channel.")
        
        if limit < 0 or limit > 99:
            return await ctx.send("❌ User limit must be between 0 (unlimited) and 99.")
        
        try:
            await channel.edit(user_limit=limit, reason=f"Limit set by {ctx.author}")
            
            limit_text = f"{limit} users" if limit > 0 else "unlimited"
            
            embed = discord.Embed(
                title="✅ User Limit Updated",
                description=f"Channel limit set to **{limit_text}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to set user limit: {str(e)}")
    
    @commands.hybrid_command(name="voice_add_owner", description="Add a co-owner to your voice channel")
    async def add_voice_owner(self, ctx: commands.Context, user: discord.Member):
        """Add a co-owner to a voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ You must be in a voice channel to use this command.")
        
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("❌ This is not a managed voice channel.")
        
        if ctx.author.id != self.voice_channels[channel.id]['owner_id'] and not ctx.author.guild_permissions.administrator:
            return await ctx.send("❌ Only the channel owner can add co-owners.")
        
        if user.id == self.voice_channels[channel.id]['owner_id']:
            return await ctx.send("❌ That user is already the channel owner.")
        
        if ctx.interaction:
            await ctx.defer()
        
        self.voice_channels[channel.id]['co_owners'].add(user.id)
        overwrites = channel.overwrites_for(user)
        overwrites.manage_channels = True
        overwrites.manage_permissions = True
        overwrites.move_members = True
        overwrites.mute_members = True
        overwrites.deafen_members = True
        
        try:
            await channel.set_permissions(user, overwrite=overwrites, reason=f"Co-owner added by {ctx.author}")
            
            embed = discord.Embed(
                title="✅ Co-Owner Added",
                description=f"**{user.display_name}** is now a co-owner of this channel",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to add co-owner: {str(e)}")
    
    @commands.hybrid_command(name="voice_remove_owner", description="Remove a co-owner from your voice channel")
    async def remove_voice_owner(self, ctx: commands.Context, user: discord.Member):
        """Remove a co-owner from a voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ You must be in a voice channel to use this command.")
        
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("❌ This is not a managed voice channel.")
        
        if ctx.author.id != self.voice_channels[channel.id]['owner_id'] and not ctx.author.guild_permissions.administrator:
            return await ctx.send("❌ Only the channel owner can remove co-owners.")
        
        if user.id not in self.voice_channels[channel.id]['co_owners']:
            return await ctx.send("❌ That user is not a co-owner of this channel.")
        
        if ctx.interaction:
            await ctx.defer()
        
        self.voice_channels[channel.id]['co_owners'].remove(user.id)
        overwrites = channel.overwrites_for(user)
        overwrites.manage_channels = None
        overwrites.manage_permissions = None
        overwrites.move_members = None
        overwrites.mute_members = None
        overwrites.deafen_members = None
        
        try:
            await channel.set_permissions(user, overwrite=overwrites, reason=f"Co-owner removed by {ctx.author}")
            
            embed = discord.Embed(
                title="✅ Co-Owner Removed",
                description=f"**{user.display_name}** is no longer a co-owner of this channel",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to remove co-owner: {str(e)}")
    
    @commands.hybrid_command(name="voice_lock", description="Lock your voice channel")
    async def lock_voice_channel(self, ctx: commands.Context):
        """Lock a voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ You must be in a voice channel to use this command.")
        
        channel = ctx.author.voice.channel
        
        if not self.is_channel_owner_or_admin(channel.id, ctx.author):
            return await ctx.send("❌ You don't have permission to lock this channel.")
        
        try:
            overwrites = channel.overwrites_for(ctx.guild.default_role)
            overwrites.connect = False
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrites, reason=f"Locked by {ctx.author}")
            
            embed = discord.Embed(
                title="🔒 Channel Locked",
                description="This voice channel is now locked. Only current members can stay.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to lock channel: {str(e)}")
    
    @commands.hybrid_command(name="voice_unlock", description="Unlock your voice channel")
    async def unlock_voice_channel(self, ctx: commands.Context):
        """Unlock a voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ You must be in a voice channel to use this command.")
        
        channel = ctx.author.voice.channel
        
        if not self.is_channel_owner_or_admin(channel.id, ctx.author):
            return await ctx.send("❌ You don't have permission to unlock this channel.")
        
        try:
            overwrites = channel.overwrites_for(ctx.guild.default_role)
            overwrites.connect = True
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrites, reason=f"Unlocked by {ctx.author}")
            
            embed = discord.Embed(
                title="🔓 Channel Unlocked",
                description="This voice channel is now unlocked. Anyone can join!",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to unlock channel: {str(e)}")
    
    @commands.hybrid_command(name="voice_info", description="Show information about the current voice channel")
    async def voice_info(self, ctx: commands.Context):
        """Show information about a voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ You must be in a voice channel to use this command.")
        
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("❌ This is not a managed voice channel.")
        
        channel_info = self.voice_channels[channel.id]
        owner = ctx.guild.get_member(channel_info['owner_id'])
        
        embed = discord.Embed(
            title=f"🔊 {channel.name}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="👑 Owner",
            value=owner.display_name if owner else "Unknown",
            inline=True
        )
        
        embed.add_field(
            name="👥 Members",
            value=f"{len(channel.members)}/{channel.user_limit or '∞'}",
            inline=True
        )
        
        embed.add_field(
            name="🕐 Created",
            value=f"<t:{int(channel_info['created_at'].timestamp())}:R>",
            inline=True
        )
        
        co_owners = []
        for user_id in channel_info.get('co_owners', set()):
            user = ctx.guild.get_member(user_id)
            if user:
                co_owners.append(user.display_name)
        
        if co_owners:
            embed.add_field(
                name="🤝 Co-Owners",
                value="\n".join(co_owners) if co_owners else "None",
                inline=False
            )
        
        default_perms = channel.overwrites_for(ctx.guild.default_role)
        locked_status = "🔒 Locked" if default_perms.connect == False else "🔓 Unlocked"
        
        embed.add_field(
            name="🛡️ Status",
            value=locked_status,
            inline=True
        )
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    await bot.add_cog(VoiceChannelManager(bot))
    logger.info("Voice Manager module loaded")