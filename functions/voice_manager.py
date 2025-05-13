import discord
from discord.ext import commands, tasks
import asyncio
import logging
from typing import Dict, List, Set, Optional, Union

logger = logging.getLogger('discord_bot')

# Constant for the creation channel name
CREATE_CHANNEL_NAME = "tạo phòng"

class VoiceChannelManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Store channel info: {channel_id: {owner_id: id, co_owners: set(), created_at: timestamp}}
        self.voice_channels: Dict[int, Dict] = {}
        # Start background task to check empty channels
        self.check_empty_channels.start()
    
    def cog_unload(self):
        # Stop background tasks when cog is unloaded
        self.check_empty_channels.cancel()
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle voice state changes for auto-creation and cleanup"""
        # Handle channel creation when joining the "create channel"
        if after.channel and after.channel.name.lower() == CREATE_CHANNEL_NAME:
            await self.create_voice_channel(member)
            return
            
        # Handle user leaving a managed channel
        if before.channel and before.channel.id in self.voice_channels:
            # Wait a moment to see if the channel is empty
            await asyncio.sleep(0.5)
            await self.check_channel_empty(before.channel)
    
    async def create_voice_channel(self, member: discord.Member):
        """Create a new voice channel and move the member there"""
        try:
            # Get or create the voice category
            category_name = "Kênh thoại"
            category = discord.utils.get(member.guild.categories, name=category_name)
            
            # If category doesn't exist, create it
            if not category:
                category = await self.setup_voice_category(member.guild)
                if not category:
                    # If we couldn't create the category, use the same category as the create channel
                    create_channel = discord.utils.get(member.guild.voice_channels, name=CREATE_CHANNEL_NAME)
                    category = create_channel.category if create_channel else None
            
            # Create channel name based on the member's name
            channel_name = f"{member.display_name}'s Channel"
            
            # Create the new channel
            new_channel = await member.guild.create_voice_channel(
                name=channel_name,
                category=category,
                reason=f"Auto-created for {member.display_name}"
            )
            
            # Update permissions for the owner
            await new_channel.set_permissions(member, 
                connect=True, 
                speak=True,
                stream=True,
                priority_speaker=True,
                use_voice_activation=True,
                manage_channels=True
            )
            
            # Move the member to the new channel
            await member.move_to(new_channel)
            
            # Register the channel
            self.voice_channels[new_channel.id] = {
                "owner_id": member.id,
                "co_owners": set(),
                "created_at": discord.utils.utcnow(),
                "guild_id": member.guild.id
            }
            
            # Send a welcome message to the user's DM
            try:
                embed = discord.Embed(
                    title="🎉 Voice Channel Created!",
                    description=f"You've created a new voice channel: **{channel_name}**",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Available Commands",
                    value=(
                        "`/kick` - Remove users\n"
                        "`/limit` - Set user limit\n"
                        "`/hide` - Make channel private\n"
                        "`/show` - Make channel visible\n"
                        "`/public` - Open to everyone\n"
                        "`/private` - Require permissions\n"
                        "`/rename` - Change channel name\n"
                        "`/add_owner` - Add co-owner\n"
                        "`/lock` - Prevent joining\n"
                        "`/unlock` - Allow joining"
                    ),
                    inline=False
                )
                await member.send(embed=embed)
            except discord.Forbidden:
                # If user has DMs closed, ignore
                pass
                
            logger.info(f"Created voice channel {new_channel.name} ({new_channel.id}) for {member.display_name}")
            
        except Exception as e:
            logger.error(f"Error creating voice channel: {e}")
    
    async def check_channel_empty(self, channel: discord.VoiceChannel):
        """Check if a channel is empty and delete if needed"""
        if channel.id not in self.voice_channels:
            return
            
        if len(channel.members) == 0:
            try:
                await channel.delete(reason="Auto-deleted empty voice channel")
                # Remove from tracking
                del self.voice_channels[channel.id]
                logger.info(f"Deleted empty voice channel: {channel.name} ({channel.id})")
            except Exception as e:
                logger.error(f"Failed to delete empty channel {channel.id}: {e}")
    
    @tasks.loop(minutes=5)
    async def check_empty_channels(self):
        """Periodically check and clean up empty voice channels"""
        for channel_id in list(self.voice_channels.keys()):
            channel_data = self.voice_channels[channel_id]
            guild = self.bot.get_guild(channel_data["guild_id"])
            if not guild:
                continue
                
            channel = guild.get_channel(channel_id)
            if not channel:
                # Channel no longer exists, remove from tracking
                del self.voice_channels[channel_id]
                continue
                
            if len(channel.members) == 0:
                try:
                    await channel.delete(reason="Auto-deleted empty voice channel")
                    del self.voice_channels[channel_id]
                    logger.info(f"Periodic cleanup: Deleted empty channel {channel.name} ({channel_id})")
                except Exception as e:
                    logger.error(f"Failed to delete empty channel {channel_id}: {e}")
    
    @check_empty_channels.before_loop
    async def before_check_empty_channels(self):
        """Wait until bot is ready before starting the task"""
        await self.bot.wait_until_ready()
    
    def is_channel_owner(self, channel_id: int, user_id: int) -> bool:
        """Check if a user is the owner or co-owner of a channel"""
        if channel_id not in self.voice_channels:
            return False
            
        channel_data = self.voice_channels[channel_id]
        return user_id == channel_data["owner_id"] or user_id in channel_data["co_owners"]
    
    # --- Channel Management Commands ---
    
    @commands.hybrid_command(
        name="voice_kick",
        description="Kick a user from your voice channel"
    )
    async def kick_user(self, ctx: commands.Context, user: discord.Member):
        """Kick a user from your voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        if not self.is_channel_owner(channel.id, ctx.author.id):
            return await ctx.send("Only the channel owner can use this command.")
            
        if user not in channel.members:
            return await ctx.send(f"{user.display_name} is not in this voice channel.")
            
        try:
            # Disconnect the user from voice
            await user.move_to(None)
            await ctx.send(f"Kicked {user.mention} from the voice channel.")
        except discord.Forbidden:
            await ctx.send("I don't have permission to disconnect that user.")
        except Exception as e:
            logger.error(f"Error kicking user: {e}")
            await ctx.send("An error occurred while trying to kick the user.")
    
    @commands.hybrid_command(
        name="voice_limit",
        description="Set a user limit for your voice channel"
    )
    async def set_limit(self, ctx: commands.Context, limit: int):
        """Set a user limit for the voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        if not self.is_channel_owner(channel.id, ctx.author.id):
            return await ctx.send("Only the channel owner can use this command.")
            
        if limit < 0 or limit > 99:
            return await ctx.send("User limit must be between 0 and 99 (0 means no limit).")
            
        try:
            await channel.edit(user_limit=limit)
            if limit == 0:
                await ctx.send("User limit removed from the channel.")
            else:
                await ctx.send(f"User limit set to {limit}.")
        except Exception as e:
            logger.error(f"Error setting user limit: {e}")
            await ctx.send("An error occurred while setting the user limit.")
    
    @commands.hybrid_command(
        name="voice_hide",
        description="Hide your voice channel from the server"
    )
    async def hide_channel(self, ctx: commands.Context):
        """Hide the voice channel from everyone except current members"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        if not self.is_channel_owner(channel.id, ctx.author.id):
            return await ctx.send("Only the channel owner can use this command.")
            
        try:
            # Hide the channel from @everyone
            await channel.set_permissions(ctx.guild.default_role, view_channel=False, connect=False)
            
            # Ensure current members can still see and connect
            for member in channel.members:
                await channel.set_permissions(member, view_channel=True, connect=True)
                
            await ctx.send("Voice channel is now hidden from others.")
        except Exception as e:
            logger.error(f"Error hiding channel: {e}")
            await ctx.send("An error occurred while hiding the channel.")
    
    @commands.hybrid_command(
        name="voice_show",
        description="Make your voice channel visible to everyone"
    )
    async def show_channel(self, ctx: commands.Context):
        """Make the voice channel visible to everyone"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        if not self.is_channel_owner(channel.id, ctx.author.id):
            return await ctx.send("Only the channel owner can use this command.")
            
        try:
            # Make the channel visible to everyone
            await channel.set_permissions(ctx.guild.default_role, view_channel=True)
            await ctx.send("Voice channel is now visible to everyone.")
        except Exception as e:
            logger.error(f"Error showing channel: {e}")
            await ctx.send("An error occurred while making the channel visible.")
    
    @commands.hybrid_command(
        name="voice_public",
        description="Make your voice channel open to everyone"
    )
    async def public_channel(self, ctx: commands.Context):
        """Make the voice channel public for everyone to join"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        if not self.is_channel_owner(channel.id, ctx.author.id):
            return await ctx.send("Only the channel owner can use this command.")
            
        try:
            # Make the channel public
            await channel.set_permissions(ctx.guild.default_role, view_channel=True, connect=True)
            await ctx.send("Voice channel is now public. Anyone can join.")
        except Exception as e:
            logger.error(f"Error making channel public: {e}")
            await ctx.send("An error occurred while making the channel public.")
    
    @commands.hybrid_command(
        name="voice_private",
        description="Make your voice channel private"
    )
    async def private_channel(self, ctx: commands.Context):
        """Make the voice channel private (visible but requiring permission to join)"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        if not self.is_channel_owner(channel.id, ctx.author.id):
            return await ctx.send("Only the channel owner can use this command.")
            
        try:
            # Make the channel private (visible but not joinable)
            await channel.set_permissions(ctx.guild.default_role, view_channel=True, connect=False)
            await ctx.send("Voice channel is now private. Only users with permission can join.")
        except Exception as e:
            logger.error(f"Error making channel private: {e}")
            await ctx.send("An error occurred while making the channel private.")
    
    @commands.hybrid_command(
        name="voice_rename",
        description="Rename your voice channel"
    )
    async def rename_channel(self, ctx: commands.Context, *, new_name: str):
        """Rename the voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        if not self.is_channel_owner(channel.id, ctx.author.id):
            return await ctx.send("Only the channel owner can use this command.")
            
        if len(new_name) > 100:
            return await ctx.send("Channel name must be 100 characters or less.")
            
        try:
            await channel.edit(name=new_name)
            await ctx.send(f"Channel renamed to: **{new_name}**")
        except Exception as e:
            logger.error(f"Error renaming channel: {e}")
            await ctx.send("An error occurred while renaming the channel.")
    
    @commands.hybrid_command(
        name="voice_addowner",
        description="Add a co-owner to your voice channel"
    )
    async def add_owner(self, ctx: commands.Context, user: discord.Member):
        """Add another user as co-owner of the channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        if not self.is_channel_owner(channel.id, ctx.author.id):
            return await ctx.send("Only the channel owner can use this command.")
            
        if user.id == ctx.author.id:
            return await ctx.send("You're already the owner of this channel.")
            
        # Add to co-owners
        channel_data = self.voice_channels[channel.id]
        if user.id in channel_data["co_owners"]:
            return await ctx.send(f"{user.display_name} is already a co-owner of this channel.")
            
        try:
            # Add to co-owners list
            channel_data["co_owners"].add(user.id)
            
            # Update permissions
            await channel.set_permissions(user, 
                connect=True, 
                speak=True, 
                stream=True,
                priority_speaker=True,
                use_voice_activation=True,
                manage_channels=True
            )
            
            await ctx.send(f"{user.mention} is now a co-owner of this channel.")
        except Exception as e:
            logger.error(f"Error adding co-owner: {e}")
            await ctx.send("An error occurred while adding the co-owner.")
    
    @commands.hybrid_command(
        name="voice_removeowner",
        description="Remove a co-owner from your voice channel"
    )
    async def remove_owner(self, ctx: commands.Context, user: discord.Member):
        """Remove a co-owner from the channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        channel_data = self.voice_channels[channel.id]
        if ctx.author.id != channel_data["owner_id"]:
            return await ctx.send("Only the main owner can remove co-owners.")
            
        if user.id not in channel_data["co_owners"]:
            return await ctx.send(f"{user.display_name} is not a co-owner of this channel.")
            
        try:
            # Remove from co-owners list
            channel_data["co_owners"].remove(user.id)
            
            # Reset permissions to default member
            await channel.set_permissions(user, overwrite=None)
            
            await ctx.send(f"{user.mention} is no longer a co-owner of this channel.")
        except Exception as e:
            logger.error(f"Error removing co-owner: {e}")
            await ctx.send("An error occurred while removing the co-owner.")
    
    @commands.hybrid_command(
        name="voice_lock",
        description="Lock your voice channel to prevent new users from joining"
    )
    async def lock_channel(self, ctx: commands.Context):
        """Lock the channel to prevent new users from joining"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        if not self.is_channel_owner(channel.id, ctx.author.id):
            return await ctx.send("Only the channel owner can use this command.")
            
        try:
            # Lock the channel - everyone except current members can't join
            await channel.set_permissions(ctx.guild.default_role, connect=False)
            
            # Ensure current members can still connect if they disconnect
            for member in channel.members:
                await channel.set_permissions(member, connect=True)
                
            await ctx.send("Voice channel is now locked. No new users can join.")
        except Exception as e:
            logger.error(f"Error locking channel: {e}")
            await ctx.send("An error occurred while locking the channel.")
    
    @commands.hybrid_command(
        name="voice_unlock",
        description="Unlock your voice channel to allow users to join"
    )
    async def unlock_channel(self, ctx: commands.Context):
        """Unlock the channel to allow users to join again"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        if not self.is_channel_owner(channel.id, ctx.author.id):
            return await ctx.send("Only the channel owner can use this command.")
            
        try:
            # Unlock the channel
            await channel.set_permissions(ctx.guild.default_role, connect=True)
            await ctx.send("Voice channel is now unlocked. Users can join again.")
        except Exception as e:
            logger.error(f"Error unlocking channel: {e}")
            await ctx.send("An error occurred while unlocking the channel.")
    
    @commands.hybrid_command(
        name="voice_transfer",
        description="Transfer ownership of your voice channel"
    )
    async def transfer_ownership(self, ctx: commands.Context, new_owner: discord.Member):
        """Transfer ownership of the channel to another user"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        channel_data = self.voice_channels[channel.id]
        if ctx.author.id != channel_data["owner_id"]:
            return await ctx.send("Only the main owner can transfer ownership.")
            
        if new_owner not in channel.members:
            return await ctx.send(f"{new_owner.display_name} must be in the voice channel.")
            
        try:
            # Make current owner a co-owner
            channel_data["co_owners"].add(ctx.author.id)
            
            # Remove new owner from co-owners if they were there
            if new_owner.id in channel_data["co_owners"]:
                channel_data["co_owners"].remove(new_owner.id)
                
            # Set new owner
            channel_data["owner_id"] = new_owner.id
            
            await ctx.send(f"Ownership transferred to {new_owner.mention}.")
        except Exception as e:
            logger.error(f"Error transferring ownership: {e}")
            await ctx.send("An error occurred while transferring ownership.")
    
    @commands.hybrid_command(
        name="voice_muteall",
        description="Mute all users in your voice channel except you and co-owners"
    )
    async def mute_all(self, ctx: commands.Context):
        """Server mute all users except owners"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        if not self.is_channel_owner(channel.id, ctx.author.id):
            return await ctx.send("Only the channel owner can use this command.")
            
        channel_data = self.voice_channels[channel.id]
        
        try:
            muted_count = 0
            for member in channel.members:
                # Don't mute the owner or co-owners
                if member.id == channel_data["owner_id"] or member.id in channel_data["co_owners"]:
                    continue
                    
                await member.edit(mute=True)
                muted_count += 1
                
            await ctx.send(f"Muted {muted_count} members in the voice channel.")
        except Exception as e:
            logger.error(f"Error muting members: {e}")
            await ctx.send("An error occurred while muting members.")
    
    @commands.hybrid_command(
        name="voice_unmuteall",
        description="Unmute all users in your voice channel"
    )
    async def unmute_all(self, ctx: commands.Context):
        """Unmute all users in the channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        if not self.is_channel_owner(channel.id, ctx.author.id):
            return await ctx.send("Only the channel owner can use this command.")
            
        try:
            unmuted_count = 0
            for member in channel.members:
                if member.voice.mute:
                    await member.edit(mute=False)
                    unmuted_count += 1
                    
            await ctx.send(f"Unmuted {unmuted_count} members in the voice channel.")
        except Exception as e:
            logger.error(f"Error unmuting members: {e}")
            await ctx.send("An error occurred while unmuting members.")
    
    @commands.hybrid_command(
        name="voice_claim",
        description="Claim ownership of a voice channel if the owner has left"
    )
    async def claim_channel(self, ctx: commands.Context):
        """Claim ownership of a voice channel if the owner has left"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This command only works in custom voice channels.")
            
        channel_data = self.voice_channels[channel.id]
        owner_id = channel_data["owner_id"]
        
        # Check if current owner is in the channel
        owner_in_channel = False
        for member in channel.members:
            if member.id == owner_id:
                owner_in_channel = True
                break
                
        if owner_in_channel:
            return await ctx.send("The channel owner is still in the channel. You cannot claim ownership.")
            
        # Transfer ownership to the claimer
        try:
            # Remove from co-owners if they were there
            if ctx.author.id in channel_data["co_owners"]:
                channel_data["co_owners"].remove(ctx.author.id)
                
            # Set new owner
            channel_data["owner_id"] = ctx.author.id
            
            # Update permissions
            await channel.set_permissions(ctx.author, 
                connect=True, 
                speak=True, 
                stream=True,
                priority_speaker=True,
                use_voice_activation=True,
                manage_channels=True
            )
            
            await ctx.send(f"{ctx.author.mention} is now the owner of this channel.")
        except Exception as e:
            logger.error(f"Error claiming ownership: {e}")
            await ctx.send("An error occurred while claiming ownership.")
    
    @commands.hybrid_command(
        name="voice_info",
        description="Show information about the current voice channel"
    )
    async def voice_info(self, ctx: commands.Context):
        """Display information about the current voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel to use this command.")
            
        channel = ctx.author.voice.channel
        
        if channel.id not in self.voice_channels:
            return await ctx.send("This is not a managed voice channel.")
            
        channel_data = self.voice_channels[channel.id]
        
        # Get owner and co-owners
        owner = ctx.guild.get_member(channel_data["owner_id"])
        co_owners = []
        for co_owner_id in channel_data["co_owners"]:
            member = ctx.guild.get_member(co_owner_id)
            if member:
                co_owners.append(member.mention)
                
        created_at = discord.utils.format_dt(channel_data["created_at"], style='R')
        
        embed = discord.Embed(
            title=f"Voice Channel: {channel.name}",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Owner", value=owner.mention if owner else "Unknown", inline=False)
        
        if co_owners:
            embed.add_field(name="Co-owners", value=", ".join(co_owners), inline=False)
        else:
            embed.add_field(name="Co-owners", value="None", inline=False)
            
        embed.add_field(name="Created", value=created_at, inline=True)
        embed.add_field(name="User Limit", value=str(channel.user_limit) if channel.user_limit else "None", inline=True)
        embed.add_field(name="Members", value=str(len(channel.members)), inline=True)
        
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        """Set up voice categories and create channels in all guilds when bot starts"""
        for guild in self.bot.guilds:
            await self.setup_voice_category(guild)
        logger.info("Voice categories and creation channels have been set up")
    
    async def setup_voice_category(self, guild: discord.Guild):
        """Create the voice category and 'create channel' if they don't exist"""
        # Check if the category exists
        category_name = "Kênh thoại"
        category = discord.utils.get(guild.categories, name=category_name)
        
        # If category doesn't exist, create it
        if not category:
            try:
                category = await guild.create_category(
                    name=category_name,
                    reason="Setting up voice channel management"
                )
                logger.info(f"Created voice category '{category_name}' in {guild.name}")
            except Exception as e:
                logger.error(f"Failed to create voice category in {guild.name}: {e}")
                return None
        
        # Check if the creation channel exists in the category
        creation_channel = discord.utils.get(
            category.voice_channels, 
            name=CREATE_CHANNEL_NAME
        )
        
        # If creation channel doesn't exist, create it
        if not creation_channel:
            try:
                creation_channel = await guild.create_voice_channel(
                    name=CREATE_CHANNEL_NAME,
                    category=category,
                    reason="Setting up voice channel creation system"
                )
                logger.info(f"Created voice channel '{CREATE_CHANNEL_NAME}' in {guild.name}")
            except Exception as e:
                logger.error(f"Failed to create voice channel in {guild.name}: {e}")
        
        return category
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Set up voice category when the bot joins a new guild"""
        await self.setup_voice_category(guild)
        logger.info(f"Set up voice category in newly joined guild: {guild.name}")

async def setup(bot: commands.Bot):
    from discord.ext import tasks
    await bot.add_cog(VoiceChannelManager(bot))
    logger.info("Voice Channel Manager cog loaded successfully")