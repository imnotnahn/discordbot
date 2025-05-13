import discord
from discord.ext import commands, tasks
import json
import random
import logging
import os
import datetime
from typing import Dict, List, Optional

logger = logging.getLogger('discord_bot')

# Constants
VOCAB_FOLDER = "./resources/vocabulary"
USER_DATA_FILE = "./resources/language_learners.json"
DEFAULT_SEND_TIME = 8  # 8 AM
VOCAB_COUNT = 20

# Language emojis and colors
LANG_SETTINGS = {
    "chinese": {
        "emoji": "🇨🇳",
        "color": 0xED1C24,  # Red color
        "thumbnail": "https://i.imgur.com/Q6ZX2Mw.png"  # Chinese flag or language icon
    },
    "english": {
        "emoji": "🇬🇧",
        "color": 0x00247D,  # Blue color
        "thumbnail": "https://i.imgur.com/JOKsECQ.png"  # English flag or language icon
    }
}

# Level emojis
LEVEL_EMOJIS = {
    "beginner": "🔰",
    "intermediate": "🔷",
    "advanced": "⭐",
    "hsk1": "1️⃣",
    "hsk2": "2️⃣",
    "hsk3": "3️⃣",
    "hsk4": "4️⃣"
}

# Languages and levels
LANGUAGES = {
    "chinese": {
        "name": "Chinese",
        "levels": ["hsk1", "hsk2", "hsk3", "hsk4",],
        # Predefined channels and roles per server - you need to fill these in
        "channels": {
            "1357038772528746656": {  # Replace with actual server ID
                "hsk1": {
                    "channel_id": 1361298919090421832,  # Replace with actual channel ID
                    "role_id": 1361299067757527190      # Replace with actual role ID
                },
                "hsk2": {
                    "channel_id": 1361298940422782996,  # Replace with actual channel ID
                    "role_id": 1361299176251457676      # Replace with actual role ID
                },
                "hsk3": {
                    "channel_id": 1361298953299038370,  # Replace with actual channel ID
                    "role_id": 1361299216902652026      # Replace with actual role ID
                },
                "hsk4": {
                    "channel_id": 1361298968709169232,  # Replace with actual channel ID
                    "role_id": 1361299257897783307      # Replace with actual role ID
                }
            }
            # Add more servers as needed
        }
    },
    "english": {
        "name": "English",
        "levels": ["beginner", "intermediate", "advanced"],
        # Predefined channels and roles per server - you need to fill these in
        "channels": {
            "1357038772528746656": {  # Replace with actual server ID
                "beginner": {
                    "channel_id": 1361298999839166514,  # Replace with actual channel ID
                    "role_id": 1361351224678682656      # Replace with actual role ID
                },
                "intermediate": {
                    "channel_id": 1361351565444780153,  # Replace with actual channel ID
                    "role_id": 1361351684801953995      # Replace with actual role ID
                },
                "advanced": {
                    "channel_id": 1361351597539459143,  # Replace with actual channel ID
                    "role_id": 1361351757602492466      # Replace with actual role ID
                }
            }
            # Add more servers as needed
        }
    }
}

class LanguageLearningCog(commands.Cog):
    """Cog for language learning features."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.learners = {}
        self.vocabulary = {}
        self.load_data()
        self.ensure_resources()
        self.daily_vocabulary.start()
    
    def cog_unload(self):
        self.daily_vocabulary.cancel()
        self.save_data()
    
    def ensure_resources(self):
        """Make sure all necessary resource folders and files exist."""
        os.makedirs(VOCAB_FOLDER, exist_ok=True)
        os.makedirs(os.path.dirname(USER_DATA_FILE), exist_ok=True)
        
        # Create example vocabulary files if they don't exist
        for lang in LANGUAGES.keys():
            for level in LANGUAGES[lang]["levels"]:
                vocab_file = f"{VOCAB_FOLDER}/{lang}_{level}.json"
                if not os.path.exists(vocab_file):
                    example_vocab = []
                    if lang == "chinese":
                        example_vocab = [
                            {"word": "你好", "pinyin": "nǐ hǎo", "tuloai": "kết cấu", "meaning": "Xin chào", 
                             "vidu": "你好，早上好！", "phienam": "nǐ hǎo, zǎo shang hǎo!", "dich": "Xin chào, chào buổi sáng!"},
                            {"word": "谢谢", "pinyin": "xiè xiè", "tuloai": "kết cấu", "meaning": "Cảm ơn",
                             "vidu": "谢谢你的帮助！", "phienam": "xiè xiè nǐ de bāng zhù!", "dich": "Cảm ơn bạn đã giúp đỡ!"}
                        ]
                    elif lang == "english":
                        example_vocab = [
                            {"word": "hello", "pronunciation": "/həˈloʊ/", "tuloai": "exclamation", "meaning": "Xin chào"},
                            {"word": "thank you", "pronunciation": "/ˈθæŋk juː/", "tuloai": "phrase", "meaning": "Cảm ơn"}
                        ]
                    
                    with open(vocab_file, 'w', encoding='utf-8') as f:
                        json.dump(example_vocab, f, ensure_ascii=False, indent=2)
    
    def load_data(self):
        """Load user registrations and vocabulary."""
        # Load user data
        if os.path.exists(USER_DATA_FILE):
            try:
                with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                    self.learners = json.load(f)
            except Exception as e:
                logger.error(f"Error loading language learners data: {e}")
                self.learners = {}
        
        # Load vocabulary data
        for lang in LANGUAGES.keys():
            for level in LANGUAGES[lang]["levels"]:
                vocab_file = f"{VOCAB_FOLDER}/{lang}_{level}.json"
                if os.path.exists(vocab_file):
                    try:
                        with open(vocab_file, 'r', encoding='utf-8') as f:
                            self.vocabulary[f"{lang}_{level}"] = json.load(f)
                    except Exception as e:
                        logger.error(f"Error loading vocabulary for {lang} {level}: {e}")
                        self.vocabulary[f"{lang}_{level}"] = []
    
    def save_data(self):
        """Save user registrations."""
        try:
            os.makedirs(os.path.dirname(USER_DATA_FILE), exist_ok=True)
            with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.learners, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving language learners data: {e}")
    
    @tasks.loop(hours=24)
    async def daily_vocabulary(self):
        """Send daily vocabulary to registered channels."""
        now = datetime.datetime.now()
        if now.hour == DEFAULT_SEND_TIME:
            await self.send_vocabulary()
    
    @daily_vocabulary.before_loop
    async def before_daily_vocabulary(self):
        """Wait until bot is ready and then wait until the next scheduled time."""
        await self.bot.wait_until_ready()
        
        now = datetime.datetime.now()
        next_run = now.replace(hour=DEFAULT_SEND_TIME, minute=0, second=0)
        
        if now.hour >= DEFAULT_SEND_TIME:
            next_run = next_run + datetime.timedelta(days=1)
        
        await discord.utils.sleep_until(next_run)
    
    async def send_vocabulary(self):
        """Send vocabulary to all registered channels."""
        now = datetime.datetime.now()
        
        for guild_id, guild_data in self.learners.items():
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue
                
            for lang, users_by_level in guild_data.items():
                if lang not in LANGUAGES or guild_id not in LANGUAGES[lang].get("channels", {}):
                    continue
                    
                for level, users in users_by_level.items():
                    if not users or level not in LANGUAGES[lang]["levels"]:
                        continue
                        
                    # Get channel and role from predefined config
                    channel_data = LANGUAGES[lang]["channels"][guild_id].get(level)
                    if not channel_data:
                        continue
                        
                    channel_id = channel_data["channel_id"]
                    role_id = channel_data["role_id"]
                    
                    channel = guild.get_channel(channel_id)
                    role = guild.get_role(role_id)
                    
                    if not channel or not role:
                        logger.error(f"Channel or role not found for {lang} {level} in guild {guild.name}")
                        continue
                    
                    # Get random vocabulary
                    vocab_key = f"{lang}_{level}"
                    if vocab_key not in self.vocabulary or not self.vocabulary[vocab_key]:
                        logger.error(f"No vocabulary found for {lang} {level}")
                        continue
                    
                    # Select random words
                    words = random.sample(
                        self.vocabulary[vocab_key],
                        min(VOCAB_COUNT, len(self.vocabulary[vocab_key]))
                    )
                    
                    # Create embed
                    lang_emoji = LANG_SETTINGS[lang]["emoji"]
                    level_emoji = LEVEL_EMOJIS.get(level, "📚")
                    
                    embed = discord.Embed(
                        title=f"{lang_emoji} {level_emoji} Daily {LANGUAGES[lang]['name']} Vocabulary ({level.capitalize()})",
                        description=f"✨ Here are your {len(words)} vocabulary words for today! ✨",
                        color=LANG_SETTINGS[lang]["color"]
                    )
                    
                    embed.set_thumbnail(url=LANG_SETTINGS[lang]["thumbnail"])
                    
                    # Format words based on language
                    for i, word_data in enumerate(words, 1):
                        if lang == "chinese":
                            # Create a visually appealing header with emoji
                            word_header = f"**{i}. {word_data['word']}**"
                            
                            # Format content with better spacing and visual elements
                            value_parts = [
                                f"🔊 **Pinyin:** {word_data.get('pinyin', 'N/A')}",
                                f"🏷️ **Từ loại:** {word_data.get('tuloai', 'N/A')}",
                                f"🔤 **Nghĩa:** {word_data.get('meaning', 'N/A')}",
                                "",  # Empty line for spacing
                            ]
                            
                            # Add example section with proper formatting if available
                            if "vidu" in word_data:
                                value_parts.append("📝 **Ví dụ:**")
                                value_parts.append(f"```{word_data['vidu']}```")
                                
                                if "phienam" in word_data:
                                    value_parts.append(f"🔉 **Phiên âm:** {word_data['phienam']}")
                                
                                if "dich" in word_data:
                                    value_parts.append(f"🔄 **Dịch:** {word_data['dich']}")
                            
                            # Add separator between words
                            value_parts.append("\n─────────────────────────")
                            
                            embed.add_field(
                                name=word_header,
                                value="\n".join(value_parts),
                                inline=False
                            )
                        elif lang == "english":
                            # Create a visually appealing header with emoji
                            word_header = f"**{i}. {word_data['word']}**"
                            
                            # Format content with better spacing and visual elements
                            value_parts = [
                                f"🔊 **Phát âm:** {word_data.get('pronunciation', 'N/A')}",
                                f"🏷️ **Từ loại:** {word_data.get('part_of_speech', 'N/A')}",
                                f"🔤 **Nghĩa:** {word_data.get('meaning', 'N/A')}",
                                "",  # Empty line for spacing
                            ]
                            
                            # Add example section if available
                            if "vidu" in word_data:
                                value_parts.append("📝 **Ví dụ:**")
                                value_parts.append(f"```{word_data['example']}```")
                                
                                if "example_pronunciation" in word_data:
                                    value_parts.append(f"🔉 **IPA example:** {word_data['example_pronunciation']}")
                                if "example_translation" in word_data:
                                    value_parts.append(f"🔄 **Dịch:** {word_data['example_translation']}")
                            
                            # Add separator between words
                            value_parts.append("\n─────────────────────────")
                            
                            embed.add_field(
                                name=word_header,
                                value="\n".join(value_parts),
                                inline=False
                            )
                    
                    embed.set_footer(text=f"📅 Ngày {now.strftime('%d/%m/%Y')} | 🕗 Được gửi lúc {now.strftime('%H:%M')}")
                    
                    try:
                        await channel.send(
                            content=f"📣 {role.mention} - Từ vựng hàng ngày đã sẵn sàng!",
                            embed=embed
                        )
                        logger.info(f"Sent vocabulary to channel {channel.name} in {guild.name}")
                    except Exception as e:
                        logger.error(f"Error sending vocabulary to channel {channel.name} in {guild.name}: {e}")
    
    @commands.hybrid_command(
        name="lang_register", 
        description="Register for daily language learning vocabulary"
    )
    async def register_language(self, ctx: commands.Context, language: str, level: str):
        """
        Register for daily language vocabulary.
        
        Parameters:
        -----------
        language: str
            The language to learn (chinese or english)
        level: str
            The difficulty level (beginner, intermediate, advanced)
        """
        language = language.lower()
        level = level.lower()
        
        # Validate language and level
        if language not in LANGUAGES:
            return await ctx.send(f"❌ Invalid language. Supported languages: {', '.join(LANGUAGES.keys())}")
        
        if level not in LANGUAGES[language]["levels"]:
            return await ctx.send(
                f"❌ Invalid level for {language}. Supported levels: {', '.join(LANGUAGES[language]['levels'])}"
            )
        
        # Verify if this language is configured for this server
        guild_id = str(ctx.guild.id)
        if guild_id not in LANGUAGES[language].get("channels", {}):
            return await ctx.send(f"⚠️ Language {language} is not configured for this server yet.")
            
        if level not in LANGUAGES[language]["channels"][guild_id]:
            return await ctx.send(f"⚠️ Level {level} for language {language} is not configured for this server yet.")
        
        # Save registration
        user_id = str(ctx.author.id)
        
        if guild_id not in self.learners:
            self.learners[guild_id] = {}
        
        if language not in self.learners[guild_id]:
            self.learners[guild_id][language] = {}
        
        if level not in self.learners[guild_id][language]:
            self.learners[guild_id][language][level] = []
            
        # Add user if not already registered
        if user_id not in self.learners[guild_id][language][level]:
            self.learners[guild_id][language][level].append(user_id)
            self.save_data()
            
            # Get channel and role info for display
            channel_id = LANGUAGES[language]["channels"][guild_id][level]["channel_id"]
            role_id = LANGUAGES[language]["channels"][guild_id][level]["role_id"]
            
            channel = ctx.guild.get_channel(channel_id)
            role = ctx.guild.get_role(role_id)
            
            # Assign the role to the user
            if role:
                try:
                    await ctx.author.add_roles(role)
                    logger.info(f"Added role {role.name} to user {ctx.author.name}")
                except Exception as e:
                    logger.error(f"Failed to add role {role.name} to user {ctx.author.name}: {e}")
            
            channel_mention = channel.mention if channel else "configured channel"
            role_mention = role.mention if role else "configured role"
            
            # Get language and level emojis
            lang_emoji = LANG_SETTINGS[language]["emoji"]
            level_emoji = LEVEL_EMOJIS.get(level, "📚")
            
            embed = discord.Embed(
                title=f"{lang_emoji} Language Learning Registration {level_emoji}",
                description=f"✅ **Successfully registered for daily vocabulary!**\nYou've been assigned the {role_mention} role.",
                color=LANG_SETTINGS[language]["color"]
            )
            
            embed.set_thumbnail(url=LANG_SETTINGS[language]["thumbnail"])
            
            embed.add_field(
                name="🗣️ Language", 
                value=f"{lang_emoji} **{LANGUAGES[language]['name']}**", 
                inline=True
            )
            embed.add_field(
                name="📊 Level", 
                value=f"{level_emoji} **{level.capitalize()}**", 
                inline=True
            )
            embed.add_field(
                name="📢 Channel", 
                value=channel_mention, 
                inline=True
            )
            embed.add_field(
                name="⏰ Schedule",
                value=f"📆 Vocabulary will be sent daily at **{DEFAULT_SEND_TIME}:00**",
                inline=False
            )
            
            embed.set_footer(text="✨ Happy learning! Remember to practice daily for best results.")
            
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"⚠️ You are already registered for {language} {level} vocabulary.")
    
    @commands.hybrid_command(
        name="lang_unregister", 
        description="Unregister from daily language learning vocabulary"
    )
    async def unregister_language(self, ctx: commands.Context, language: str, level: str):
        """
        Unregister from daily language vocabulary.
        
        Parameters:
        -----------
        language: str
            The language to unregister from (chinese or english)
        level: str
            The difficulty level to unregister from
        """
        language = language.lower()
        level = level.lower()
        
        # Validate language and level
        if language not in LANGUAGES:
            return await ctx.send(f"❌ Invalid language. Supported languages: {', '.join(LANGUAGES.keys())}")
        
        if level not in LANGUAGES[language]["levels"]:
            return await ctx.send(
                f"❌ Invalid level for {language}. Supported levels: {', '.join(LANGUAGES[language]['levels'])}"
            )
        
        # Remove registration
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if (guild_id in self.learners and 
            language in self.learners[guild_id] and 
            level in self.learners[guild_id][language] and
            user_id in self.learners[guild_id][language][level]):
            
            self.learners[guild_id][language][level].remove(user_id)
            
            # Clean up empty lists
            if not self.learners[guild_id][language][level]:
                del self.learners[guild_id][language][level]
            
            # Clean up empty dictionaries
            if not self.learners[guild_id][language]:
                del self.learners[guild_id][language]
            
            if not self.learners[guild_id]:
                del self.learners[guild_id]
            
            self.save_data()
            
            # Remove the role from the user
            if guild_id in LANGUAGES[language].get("channels", {}) and level in LANGUAGES[language]["channels"][guild_id]:
                role_id = LANGUAGES[language]["channels"][guild_id][level]["role_id"]
                role = ctx.guild.get_role(role_id)
                
                if role and role in ctx.author.roles:
                    try:
                        await ctx.author.remove_roles(role)
                        logger.info(f"Removed role {role.name} from user {ctx.author.name}")
                    except Exception as e:
                        logger.error(f"Failed to remove role {role.name} from user {ctx.author.name}: {e}")
            
            # Get language emoji for better visuals
            lang_emoji = LANG_SETTINGS[language]["emoji"]
            level_emoji = LEVEL_EMOJIS.get(level, "📚")
            
            embed = discord.Embed(
                title=f"{lang_emoji} Language Learning Unregistration {level_emoji}",
                description=f"✅ Successfully unregistered from {language} {level} vocabulary.",
                color=discord.Color.orange()
            )
            
            embed.set_footer(text="You can register again anytime using the /lang_register command.")
            
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ You are not registered for {language} {level} vocabulary.")
    
    @commands.hybrid_command(
        name="lang_list", 
        description="List your language learning registrations"
    )
    async def list_registrations(self, ctx: commands.Context):
        """List your language learning registrations."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if guild_id not in self.learners:
            return await ctx.send("❌ You have no language learning registrations.")
        
        embed = discord.Embed(
            title="📚 Your Language Learning Registrations",
            description="👤 Here are the languages you are currently learning:",
            color=discord.Color.blue()
        )
        
        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url
        )
        
        registered = False
        
        for language, levels in self.learners[guild_id].items():
            for level, users in levels.items():
                if user_id in users:
                    registered = True
                    
                    # Get channel info
                    channel_id = LANGUAGES[language]["channels"][guild_id][level]["channel_id"]
                    channel = ctx.guild.get_channel(channel_id)
                    channel_mention = channel.mention if channel else "configured channel"
                    
                    # Get language and level emojis
                    lang_emoji = LANG_SETTINGS[language]["emoji"]
                    level_emoji = LEVEL_EMOJIS.get(level, "📚")
                    
                    embed.add_field(
                        name=f"{lang_emoji} {LANGUAGES[language]['name']} - {level_emoji} {level.capitalize()}",
                        value=f"📢 **Channel:** {channel_mention}\n⏰ **Daily delivery:** {DEFAULT_SEND_TIME}:00",
                        inline=False
                    )
        
        if not registered:
            return await ctx.send("❌ You have no language learning registrations.")
        
        embed.set_footer(text="Use /lang_register to add more languages or /lang_unregister to remove one.")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="lang_send_now", 
        description="Send vocabulary immediately"
    )
    @commands.has_permissions(administrator=True)
    async def send_now(self, ctx: commands.Context):
        """Manually trigger vocabulary sending for testing purposes."""
        embed = discord.Embed(
            title="🔄 Sending Vocabulary",
            description="Starting vocabulary delivery to all registered channels...",
            color=discord.Color.blue()
        )
        
        message = await ctx.send(embed=embed)
        
        await self.send_vocabulary()
        
        embed.description = "✅ **All vocabulary has been delivered successfully!**"
        embed.color = discord.Color.green()
        embed.set_footer(text=f"Completed at {datetime.datetime.now().strftime('%H:%M:%S')}")
        
        await message.edit(embed=embed)

async def setup(bot: commands.Bot):
    """Setup function required by discord.py to load the cog."""
    await bot.add_cog(LanguageLearningCog(bot))
    logger.info("Language Learning module loaded")