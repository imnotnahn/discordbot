import discord
from discord.ext import commands, tasks
import json
import logging
import os
import datetime
from typing import Dict, List, Optional, Tuple
import sqlite3
import asyncio

logger = logging.getLogger('discord_bot')


VOCAB_FOLDER = "./resources/vocabulary"
USER_DATA_FILE = "./resources/language_learners.json"
PROGRESS_DB = "./resources/progress.db"
DEFAULT_SEND_TIME = 4 
VOCAB_COUNT = 20

# Language configuration - will be dynamically loaded
LANGUAGES = {
    "chinese": {
        "name": "Chinese (中文)",
        "emoji": "🇨🇳",
        "color": 0xED1C24,
        "thumbnail": "https://i.imgur.com/Q6ZX2Mw.png",
        "levels": {
            "hsk1": {"name": "HSK 1", "emoji": "1️⃣", "description": "Beginner level"},
            "hsk2": {"name": "HSK 2", "emoji": "2️⃣", "description": "Elementary level"},
            "hsk3": {"name": "HSK 3", "emoji": "3️⃣", "description": "Intermediate level"},
            "hsk4": {"name": "HSK 4", "emoji": "4️⃣", "description": "Upper intermediate"}
        }
    },
    "english": {
        "name": "English",
        "emoji": "🇬🇧", 
        "color": 0x00247D,
        "thumbnail": "https://i.imgur.com/JOKsECQ.png",
        "levels": {
            "beginner": {"name": "Beginner", "emoji": "🔰", "description": "Basic English vocabulary"},
            "intermediate": {"name": "Intermediate", "emoji": "🔷", "description": "Everyday English"},
            "advanced": {"name": "Advanced", "emoji": "⭐", "description": "Advanced vocabulary"}
        }
    },
    "japanese": {
        "name": "Japanese (日本語)",
        "emoji": "🇯🇵",
        "color": 0xBC002D,
        "thumbnail": "https://i.imgur.com/XYZ.png",
        "levels": {
            "jlpt_n5": {"name": "JLPT N5", "emoji": "5️⃣", "description": "Basic Japanese "},
            "jlpt_n4": {"name": "JLPT N4", "emoji": "4️⃣", "description": "Elementary Japanese "},
            "jlpt_n3": {"name": "JLPT N3", "emoji": "3️⃣", "description": "Intermediate Japanese "},
            "jlpt_n2": {"name": "JLPT N2", "emoji": "2️⃣", "description": "Advanced Japanese "},
            "jlpt_n1": {"name": "JLPT N1", "emoji": "1️⃣", "description": "Proficient Japanese "}
        }
    }
}

class ProgressTracker:
    """Tracks individual user learning progress"""
    
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        """Initialize SQLite database for progress tracking"""
        os.makedirs(os.path.dirname(PROGRESS_DB), exist_ok=True)
        with sqlite3.connect(PROGRESS_DB) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_progress (
                    user_id INTEGER,
                    guild_id INTEGER,
                    language TEXT,
                    level TEXT,
                    current_word_index INTEGER DEFAULT 0,
                    words_learned INTEGER DEFAULT 0,
                    streak_days INTEGER DEFAULT 0,
                    last_study_date DATE,
                    total_points INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id, language, level)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS word_reviews (
                    user_id INTEGER,
                    language TEXT,
                    level TEXT,
                    word_index INTEGER,
                    correct_count INTEGER DEFAULT 0,
                    incorrect_count INTEGER DEFAULT 0,
                    last_reviewed DATE,
                    next_review_date DATE,
                    retention_strength REAL DEFAULT 1.0,
                    PRIMARY KEY (user_id, language, level, word_index)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_stats (
                    user_id INTEGER,
                    guild_id INTEGER,
                    date DATE,
                    words_studied INTEGER DEFAULT 0,
                    quizzes_completed INTEGER DEFAULT 0,
                    points_earned INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id, date)
                )
            ''')

class LanguageLearningV2Cog(commands.Cog):
    """Advanced Language Learning System with auto-management"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.learners = {}
        self.vocabulary = {}
        self.progress_tracker = ProgressTracker()
        self.server_configs = {}  # Store per-server language configurations
        self.load_data()
        self.ensure_resources()
        self.daily_vocabulary.start()
    
    def cog_unload(self):
        self.daily_vocabulary.cancel()
        self.save_data()
    
    def ensure_resources(self):
        """Ensure all resource directories exist"""
        os.makedirs(VOCAB_FOLDER, exist_ok=True)
        os.makedirs(os.path.dirname(USER_DATA_FILE), exist_ok=True)
    
    def load_data(self):
        """Load user registrations and vocabulary data"""
        if os.path.exists(USER_DATA_FILE):
            try:
                with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                    self.learners = json.load(f)
            except Exception as e:
                logger.error(f"Error loading language learners data: {e}")
                self.learners = {}
        
        for lang_code in LANGUAGES.keys():
            for level_code in LANGUAGES[lang_code]["levels"].keys():
                file_mapping = {
                    "jlpt_n5": "japan_jlpt_n5",
                    "jlpt_n4": "japan_jlpt_n4", 
                    "jlpt_n3": "japan_jlpt_n3",
                    "jlpt_n2": "japan_jlpt_n2",
                    "jlpt_n1": "japan_jlpt_n1"
                }
                
                filename = file_mapping.get(level_code, f"{lang_code}_{level_code}")
                vocab_file = f"{VOCAB_FOLDER}/{filename}.json"
                
                if os.path.exists(vocab_file):
                    try:
                        with open(vocab_file, 'r', encoding='utf-8') as f:
                            vocab_data = json.load(f)
                            
                            if lang_code == "japanese" and isinstance(vocab_data, dict) and "data" in vocab_data:
                                vocab_data = vocab_data["data"]
                                
                            self.vocabulary[f"{lang_code}_{level_code}"] = vocab_data
                            logger.info(f"Loaded {len(vocab_data)} words for {lang_code} {level_code}")
                    except Exception as e:
                        logger.error(f"Error loading vocabulary for {lang_code} {level_code}: {e}")
                        self.vocabulary[f"{lang_code}_{level_code}"] = []
    
    def save_data(self):
        """Save user registrations"""
        try:
            with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.learners, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving language learners data: {e}")
    
    async def setup_language_channels(self, guild: discord.Guild, language: str) -> bool:
        """Create category and channels for a language with proper permissions"""
        try:
            lang_config = LANGUAGES[language]
            
            # Create category
            category_name = f"📚 {lang_config['name']}"
            category = discord.utils.get(guild.categories, name=category_name)
            
            if not category:
                # Create category
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
                }
                category = await guild.create_category(category_name, overwrites=overwrites)
                logger.info(f"Created category: {category_name}")
            
            # Store server config
            guild_id = str(guild.id)
            if guild_id not in self.server_configs:
                self.server_configs[guild_id] = {}
            if language not in self.server_configs[guild_id]:
                self.server_configs[guild_id][language] = {"category_id": category.id, "channels": {}}
            
            # Create channels and roles for each level
            for level_code, level_info in lang_config["levels"].items():
                # Create role if doesn't exist
                role_name = f"{lang_config['name']} - {level_info['name']}"
                role = discord.utils.get(guild.roles, name=role_name)
                
                if not role:
                    role = await guild.create_role(
                        name=role_name,
                        color=discord.Color.default(),
                        mentionable=True,
                        reason=f"Language learning role for {language} {level_code}"
                    )
                    logger.info(f"Created role: {role_name}")
                
                # Create channel if doesn't exist
                channel_name = f"{level_info['emoji']}-{level_code.replace('_', '-')}"
                channel = discord.utils.get(category.channels, name=channel_name)
                
                if not channel:
                    # Channel overwrites: only users with the role can see it
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
                    }
                    
                    channel = await guild.create_text_channel(
                        channel_name,
                        category=category,
                        overwrites=overwrites,
                        topic=f"Daily vocabulary for {lang_config['name']} {level_info['name']} - {level_info['description']}"
                    )
                    logger.info(f"Created channel: {channel_name}")
                
                # Store channel and role info
                self.server_configs[guild_id][language]["channels"][level_code] = {
                    "channel_id": channel.id,
                    "role_id": role.id
                }
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting up channels for {language} in {guild.name}: {e}")
            return False
    
    async def get_next_words(self, user_id: int, guild_id: int, language: str, level: str, count: int = VOCAB_COUNT) -> List[dict]:
        """Get next words in sequence for user"""
        with sqlite3.connect(PROGRESS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT current_word_index FROM user_progress 
                WHERE user_id = ? AND guild_id = ? AND language = ? AND level = ?
            ''', (user_id, guild_id, language, level))
            
            result = cursor.fetchone()
            current_index = result[0] if result else 0
        
        vocab_key = f"{language}_{level}"
        if vocab_key not in self.vocabulary:
            return []
        
        vocab_list = self.vocabulary[vocab_key]
        if not vocab_list:
            return []
        
        # Get next words in sequence
        words = []
        for i in range(count):
            word_index = (current_index + i) % len(vocab_list)
            words.append(vocab_list[word_index])
        
        return words
    
    async def update_progress(self, user_id: int, guild_id: int, language: str, level: str, words_studied: int):
        """Update user learning progress"""
        today = datetime.date.today().isoformat()
        
        with sqlite3.connect(PROGRESS_DB) as conn:
            cursor = conn.cursor()
            
            # Get current progress
            cursor.execute('''
                SELECT current_word_index, words_learned, streak_days, last_study_date, total_points
                FROM user_progress 
                WHERE user_id = ? AND guild_id = ? AND language = ? AND level = ?
            ''', (user_id, guild_id, language, level))
            
            result = cursor.fetchone()
            if result:
                current_index, learned, streak, last_date, points = result
                
                # Calculate new streak
                yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
                if last_date == yesterday:
                    new_streak = streak + 1  # Continued streak
                elif last_date == today:
                    new_streak = streak  # Same day, keep streak
                else:
                    new_streak = 1  # Reset streak
                
                # Update existing record
                cursor.execute('''
                    UPDATE user_progress 
                    SET current_word_index = ?, words_learned = ?, 
                        streak_days = ?, last_study_date = ?, total_points = ?
                    WHERE user_id = ? AND guild_id = ? AND language = ? AND level = ?
                ''', (current_index + words_studied, learned + words_studied,
                      new_streak, today, points + (words_studied * 10),
                      user_id, guild_id, language, level))
            else:
                # Create new record
                cursor.execute('''
                    INSERT INTO user_progress 
                    (user_id, guild_id, language, level, current_word_index, words_learned, 
                     streak_days, last_study_date, total_points)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                ''', (user_id, guild_id, language, level, words_studied, words_studied, today, words_studied * 10))
            
            # Update daily stats
            cursor.execute('''
                SELECT words_studied, points_earned 
                FROM daily_stats 
                WHERE user_id = ? AND guild_id = ? AND date = ?
            ''', (user_id, guild_id, today))
            
            daily_result = cursor.fetchone()
            if daily_result:
                current_daily_words, current_daily_points = daily_result
                cursor.execute('''
                    UPDATE daily_stats 
                    SET words_studied = ?, points_earned = ?
                    WHERE user_id = ? AND guild_id = ? AND date = ?
                ''', (current_daily_words + words_studied, current_daily_points + (words_studied * 10),
                      user_id, guild_id, today))
            else:
                cursor.execute('''
                    INSERT INTO daily_stats (user_id, guild_id, date, words_studied, points_earned)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, guild_id, today, words_studied, words_studied * 10))

    @tasks.loop(hours=24)
    async def daily_vocabulary(self):
        """Send daily vocabulary to all registered channels"""
        now = datetime.datetime.now()
        if now.hour == DEFAULT_SEND_TIME:
            await self.send_daily_vocabulary()

    @daily_vocabulary.before_loop
    async def before_daily_vocabulary(self):
        """Wait until bot is ready"""
        await self.bot.wait_until_ready()
        
        now = datetime.datetime.now()
        next_run = now.replace(hour=DEFAULT_SEND_TIME, minute=0, second=0)
        
        if now.hour >= DEFAULT_SEND_TIME:
            next_run = next_run + datetime.timedelta(days=1)
        
        await discord.utils.sleep_until(next_run)

    async def send_daily_vocabulary(self):
        """Send vocabulary to all registered users"""
        today = datetime.date.today()
        
        for guild_id, guild_data in self.learners.items():
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue
            
            for language, levels_data in guild_data.items():
                if language not in LANGUAGES:
                    continue
                
                # Ensure channels are set up
                await self.setup_language_channels(guild, language)
                
                if guild_id not in self.server_configs or language not in self.server_configs[guild_id]:
                    continue
                
                for level, user_ids in levels_data.items():
                    if not user_ids or level not in LANGUAGES[language]["levels"]:
                        continue
                    
                    channel_info = self.server_configs[guild_id][language]["channels"].get(level)
                    if not channel_info:
                        continue
                    
                    channel = guild.get_channel(channel_info["channel_id"])
                    role = guild.get_role(channel_info["role_id"])
                    
                    if not channel:
                        continue
                    
                    # Send vocabulary to each user individually based on their progress
                    for user_id_str in user_ids:
                        user_id = int(user_id_str)
                        user = guild.get_member(user_id)
                        if not user:
                            continue
                        
                        words = await self.get_next_words(user_id, int(guild_id), language, level)
                        if not words:
                            continue
                        
                        embed = await self.create_vocabulary_embed(language, level, words, user.display_name)
                        
                        try:
                            await channel.send(
                                content=f"📖 **{user.mention}** - Your daily vocabulary is ready!",
                                embed=embed
                            )
                            
                            # Update progress
                            await self.update_progress(user_id, int(guild_id), language, level, len(words))
                            
                        except Exception as e:
                            logger.error(f"Error sending vocabulary to {user.display_name}: {e}")

    async def create_vocabulary_embed(self, language: str, level: str, words: List[dict], user_name: str) -> discord.Embed:
        """Create formatted vocabulary embed"""
        lang_config = LANGUAGES[language]
        level_config = lang_config["levels"][level]
        
        embed = discord.Embed(
            title=f"{lang_config['emoji']} {level_config['emoji']} Daily {lang_config['name']} - {level_config['name']}",
            description=f"✨ **{user_name}'s personal vocabulary for today!** ✨\n📚 {len(words)} words to learn",
            color=lang_config["color"]
        )
        
        embed.set_thumbnail(url=lang_config["thumbnail"])
        
        # Format words based on language
        for i, word_data in enumerate(words, 1):
            if language == "chinese":
                word_header = f"**{i}. {word_data.get('word', 'N/A')}**"
                value_parts = [
                    f"🔊 **Pinyin:** {word_data.get('pinyin', 'N/A')}",
                    f"🏷️ **Từ loại:** {word_data.get('tuloai', 'N/A')}",
                    f"🔤 **Nghĩa:** {word_data.get('meaning', 'N/A')}",
                    ""
                ]
                
                if word_data.get('vidu'):
                    value_parts.append("📝 **Ví dụ:**")
                    value_parts.append(f"```{word_data['vidu']}```")
                    if word_data.get('phienam'):
                        value_parts.append(f"🔉 **Phiên âm:** {word_data['phienam']}")
                    if word_data.get('dich'):
                        value_parts.append(f"🔄 **Dịch:** {word_data['dich']}")
                
            elif language == "english":
                word_header = f"**{i}. {word_data.get('word', 'N/A')}**"
                value_parts = [
                    f"🔊 **Phát âm:** {word_data.get('pronunciation', 'N/A')}",
                    f"🏷️ **Từ loại:** {word_data.get('part_of_speech', 'N/A')}",
                    f"🔤 **Nghĩa:** {word_data.get('meaning', 'N/A')}",
                    ""
                ]
                
                if word_data.get('example'):
                    value_parts.append("📝 **Ví dụ:**")
                    value_parts.append(f"```{word_data['example']}```")
                    if word_data.get('example_pronunciation'):
                        value_parts.append(f"🔉 **Phiên âm ví dụ:** {word_data['example_pronunciation']}")
                    if word_data.get('example_translation'):
                        value_parts.append(f"🔄 **Dịch:** {word_data['example_translation']}")
            
            elif language == "japanese":
                word = word_data.get('word', 'N/A')
                hiragana = word_data.get('hiragana', '')
                if word != hiragana and hiragana:
                    word_header = f"**{i}. {word}** ({hiragana})"
                else:
                    word_header = f"**{i}. {word}**"
                value_parts = [
                    f"🔊 **Romaji:** {word_data.get('romaji', 'N/A')}",
                    f"🏷️ **Loại từ:** {word_data.get('category', 'N/A')}",
                    f"🔤 **Nghĩa:** {word_data.get('meaning', 'N/A')}",
                    ""
                ]
            
            value_parts.append("─────────────────────────")
            
            embed.add_field(
                name=word_header,
                value="\n".join(value_parts),
                inline=False
            )
        
        embed.set_footer(text=f"📅 {datetime.datetime.now().strftime('%d/%m/%Y')} | 🎯 Sequential Learning System")
        
        return embed

    async def language_autocomplete(self, interaction: discord.Interaction, current: str) -> List[discord.app_commands.Choice[str]]:
        """Autocomplete for language parameter"""
        return [
            discord.app_commands.Choice(name=f"{info['emoji']} {info['name']}", value=code)
            for code, info in LANGUAGES.items()
            if current.lower() in code.lower() or current.lower() in info['name'].lower()
        ]
    
    async def level_autocomplete(self, interaction: discord.Interaction, current: str) -> List[discord.app_commands.Choice[str]]:
        """Autocomplete for level parameter"""
        choices = []
        
        language = None
        for option in interaction.namespace:
            if hasattr(interaction.namespace, 'language'):
                language = interaction.namespace.language
                break
        
        if language and language in LANGUAGES:
            for level_code, level_info in LANGUAGES[language]["levels"].items():
                if current.lower() in level_code.lower() or current.lower() in level_info['name'].lower():
                    choices.append(
                        discord.app_commands.Choice(
                            name=f"{level_info['emoji']} {level_info['name']} - {level_info['description']}", 
                            value=level_code
                        )
                    )
        else:
            for lang_info in LANGUAGES.values():
                for level_code, level_info in lang_info["levels"].items():
                    if current.lower() in level_code.lower() or current.lower() in level_info['name'].lower():
                        choices.append(
                            discord.app_commands.Choice(
                                name=f"{level_info['emoji']} {level_info['name']}", 
                                value=level_code
                            )
                        )
        
        return choices[:25]
    
    @commands.hybrid_command(name="lang_register", description="Register for daily language vocabulary with auto-setup")
    @discord.app_commands.autocomplete(language=language_autocomplete, level=level_autocomplete)
    async def register_language(self, ctx: commands.Context, language: str, level: str):
        """Register for daily language vocabulary"""
        if ctx.interaction:
            await ctx.defer()
        
        language = language.lower()
        level = level.lower()
        
        if language not in LANGUAGES:
            available_langs = "\n".join([f"• **{code}**: {info['name']}" for code, info in LANGUAGES.items()])
            return await ctx.send(f"❌ Invalid language. Available languages:\n{available_langs}")
        
        if level not in LANGUAGES[language]["levels"]:
            available_levels = "\n".join([f"• **{code}**: {info['name']}" for code, info in LANGUAGES[language]['levels'].items()])
            return await ctx.send(f"❌ Invalid level for {language}. Available levels:\n{available_levels}")
        
        status_msg = await ctx.send("🔄 Setting up your language learning registration...")
        
        try:
            setup_success = await self.setup_language_channels(ctx.guild, language)
            if not setup_success:
                return await status_msg.edit(content="❌ Failed to setup language channels. Please contact an administrator.")
            
            guild_id = str(ctx.guild.id)
            user_id = str(ctx.author.id)
            
            if guild_id not in self.learners:
                self.learners[guild_id] = {}
            if language not in self.learners[guild_id]:
                self.learners[guild_id][language] = {}
            if level not in self.learners[guild_id][language]:
                self.learners[guild_id][language][level] = []
            
            if user_id not in self.learners[guild_id][language][level]:
                self.learners[guild_id][language][level].append(user_id)
                self.save_data()
                
                if guild_id in self.server_configs and language in self.server_configs[guild_id]:
                    role_info = self.server_configs[guild_id][language]["channels"].get(level)
                    if role_info:
                        role_id = role_info["role_id"]
                        role = ctx.guild.get_role(role_id)
                        
                        if role:
                            try:
                                await ctx.author.add_roles(role)
                            except Exception as e:
                                logger.error(f"Failed to assign role: {e}")
                
                lang_config = LANGUAGES[language]
                level_config = lang_config["levels"][level]
                
                embed = discord.Embed(
                    title=f"{lang_config['emoji']} Registration Successful! {level_config['emoji']}",
                    description=f"✅ You're now registered for **{lang_config['name']} - {level_config['name']}**!",
                    color=lang_config["color"]
                )
                
                channel_mention = "Channel setup pending"
                if guild_id in self.server_configs and language in self.server_configs[guild_id]:
                    channel_info = self.server_configs[guild_id][language]["channels"].get(level)
                    if channel_info:
                        channel_id = channel_info["channel_id"]
                        channel = ctx.guild.get_channel(channel_id)
                        if channel:
                            channel_mention = channel.mention
                
                embed.add_field(name="📢 Your Channel", value=channel_mention, inline=True)
                embed.add_field(name="⏰ Daily Time", value=f"{DEFAULT_SEND_TIME}:00", inline=True)
                embed.add_field(name="📚 Learning Mode", value="Sequential (no random)", inline=True)
                
                embed.add_field(
                    name="🎯 What's New?",
                    value="• **Sequential learning** - words in order, no random!\n• **Personal progress tracking**\n• **Streak system & rewards**\n• **Auto-created channels & roles**",
                    inline=False
                )
                
                embed.set_footer(text="Use /lang_progress to check your learning progress!")
                
                await status_msg.edit(content=None, embed=embed)
            else:
                await status_msg.edit(content=f"⚠️ You're already registered for {language} {level}!")
                
        except Exception as e:
            logger.error(f"Error in lang_register: {e}")
            try:
                await status_msg.edit(content=f"❌ An error occurred during registration: {str(e)}")
            except:
                await ctx.send(f"❌ An error occurred during registration: {str(e)}")

    @commands.hybrid_command(name="lang_progress", description="Check your learning progress")
    async def check_progress(self, ctx: commands.Context):
        """Show user's learning progress across all languages"""
        if ctx.interaction:
            await ctx.defer()
            
        user_id = ctx.author.id
        guild_id = ctx.guild.id
        
        with sqlite3.connect(PROGRESS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT language, level, current_word_index, words_learned, 
                       streak_days, total_points, last_study_date
                FROM user_progress 
                WHERE user_id = ? AND guild_id = ?
                ORDER BY language, level
            ''', (user_id, guild_id))
            
            progress_data = cursor.fetchall()
        
        if not progress_data:
            return await ctx.send("📊 You haven't started learning any languages yet! Use `/lang_register` to begin.")
        
        embed = discord.Embed(
            title="📊 Your Learning Progress",
            description=f"**{ctx.author.display_name}**'s language learning journey",
            color=discord.Color.blue()
        )
        
        total_points = 0
        total_streak = 0
        
        for language, level, word_index, words_learned, streak, points, last_date in progress_data:
            if language in LANGUAGES and level in LANGUAGES[language]["levels"]:
                lang_config = LANGUAGES[language]
                level_config = lang_config["levels"][level]
                
                # Calculate progress percentage
                vocab_key = f"{language}_{level}"
                total_words = len(self.vocabulary.get(vocab_key, []))
                progress_pct = (word_index / total_words * 100) if total_words > 0 else 0
                
                field_value = [
                    f"📍 **Current Position:** {word_index}/{total_words} ({progress_pct:.1f}%)",
                    f"📚 **Words Studied:** {words_learned}",
                    f"🔥 **Streak:** {streak} days",
                    f"⭐ **Points:** {points}",
                    f"📅 **Last Study:** {last_date}"
                ]
                
                embed.add_field(
                    name=f"{lang_config['emoji']} {lang_config['name']} - {level_config['emoji']} {level_config['name']}",
                    value="\n".join(field_value),
                    inline=False
                )
                
                total_points += points
                total_streak = max(total_streak, streak)
        
        embed.add_field(
            name="🏆 Overall Stats",
            value=f"**Total Points:** {total_points}\n**Best Streak:** {total_streak} days",
            inline=False
        )
        
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="Keep up the great work! 頑張って! | Try /lang_quiz to test your knowledge")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="lang_quiz", description="Take a vocabulary quiz to test your knowledge")
    @discord.app_commands.autocomplete(language=language_autocomplete, level=level_autocomplete)
    async def vocabulary_quiz(self, ctx: commands.Context, language: str, level: str, question_count: int = 10):
        """Start a vocabulary quiz"""
        if ctx.interaction:
            await ctx.defer()
            
        language = language.lower()
        level = level.lower()
        
        if language not in LANGUAGES:
            available_langs = "\n".join([f"• **{code}**: {info['name']}" for code, info in LANGUAGES.items()])
            return await ctx.send(f"❌ Invalid language. Available languages:\n{available_langs}")
        
        if level not in LANGUAGES[language]["levels"]:
            available_levels = "\n".join([f"• **{code}**: {info['name']}" for code, info in LANGUAGES[language]['levels'].items()])
            return await ctx.send(f"❌ Invalid level for {language}. Available levels:\n{available_levels}")
        
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if (guild_id not in self.learners or 
            language not in self.learners[guild_id] or
            level not in self.learners[guild_id][language] or
            user_id not in self.learners[guild_id][language][level]):
            return await ctx.send(f"❌ You must be registered for {language} {level} to take quizzes. Use `/lang_register {language} {level}` first.")
        
        vocab_key = f"{language}_{level}"
        if vocab_key not in self.vocabulary or not self.vocabulary[vocab_key]:
            return await ctx.send(f"❌ No vocabulary available for {language} {level}")
        
        prep_msg = await ctx.send("🎯 Preparing your vocabulary quiz...")
        
        try:
            question_count = min(question_count, 20)
            question_count = max(question_count, 5)
            
            with sqlite3.connect(PROGRESS_DB) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT current_word_index FROM user_progress 
                    WHERE user_id = ? AND guild_id = ? AND language = ? AND level = ?
                ''', (int(user_id), int(guild_id), language, level))
                
                result = cursor.fetchone()
                current_index = result[0] if result else 0
            
            vocab_list = self.vocabulary[vocab_key]
            
            max_index = min(current_index + 20, len(vocab_list))
            min_index = max(0, current_index - 50)
            
            if max_index <= min_index:
                available_words = vocab_list[:question_count]
            else:
                available_words = vocab_list[min_index:max_index]
            
            if len(available_words) < question_count:
                question_count = len(available_words)
            
            import random
            selected_words = random.sample(available_words, question_count)
            
            await prep_msg.delete()
            await self.start_quiz(ctx, language, level, selected_words)
            
        except Exception as e:
            logger.error(f"Error in vocabulary_quiz: {e}")
            await prep_msg.edit(content=f"❌ An error occurred while preparing the quiz: {str(e)}")
    
    async def start_quiz(self, ctx: commands.Context, language: str, level: str, words: List[dict]):
        """Start an interactive vocabulary quiz"""
        lang_config = LANGUAGES[language]
        level_config = lang_config["levels"][level]
        
        quiz_embed = discord.Embed(
            title=f"🎯 {lang_config['name']} Quiz - {level_config['name']}",
            description=f"**{len(words)} questions** | Answer by typing the number (1-4)",
            color=lang_config["color"]
        )
        
        quiz_embed.set_thumbnail(url=lang_config["thumbnail"])
        quiz_embed.set_footer(text=f"Quiz for {ctx.author.display_name} | Type 'quit' to exit")
        
        correct_answers = 0
        
        for i, word_data in enumerate(words, 1):
            # Create multiple choice question
            correct_answer = word_data.get('meaning', 'Unknown')
            
            # Get other wrong answers from the same vocabulary set
            vocab_key = f"{language}_{level}"
            all_meanings = [w.get('meaning', 'Unknown') for w in self.vocabulary[vocab_key] if w != word_data]
            
            import random
            wrong_answers = random.sample(all_meanings, min(3, len(all_meanings)))
            
            # Ensure we have 4 choices
            while len(wrong_answers) < 3:
                wrong_answers.append("Unknown option")
            
            choices = [correct_answer] + wrong_answers[:3]
            random.shuffle(choices)
            correct_index = choices.index(correct_answer) + 1
            
            # Create question embed
            question_embed = discord.Embed(
                title=f"Question {i}/{len(words)}",
                color=lang_config["color"]
            )
            
            if language == "chinese":
                question_embed.add_field(
                    name="Word",
                    value=f"**{word_data.get('word', 'N/A')}**\n🔊 **Pinyin:** {word_data.get('pinyin', 'N/A')}",
                    inline=False
                )
            elif language == "english":
                question_embed.add_field(
                    name="Word",
                    value=f"**{word_data.get('word', 'N/A')}**\n🔊 **Pronunciation:** {word_data.get('pronunciation', 'N/A')}",
                    inline=False
                )
            elif language == "japanese":
                word_display = word_data.get('word', 'N/A')
                hiragana_display = word_data.get('hiragana', '')
                if word_display != hiragana_display and hiragana_display:
                    word_text = f"**{word_display}** ({hiragana_display})"
                else:
                    word_text = f"**{word_display}**"
                question_embed.add_field(
                    name="Word", 
                    value=f"{word_text}\n🔊 **Romaji:** {word_data.get('romaji', 'N/A')}",
                    inline=False
                )
            
            choices_text = "\n".join([f"**{j}.** {choice}" for j, choice in enumerate(choices, 1)])
            question_embed.add_field(
                name="What does this word mean?",
                value=choices_text,
                inline=False
            )
            
            question_embed.set_footer(text=f"Score: {correct_answers}/{i-1} | Type 1-4 or 'quit'")
            
            await ctx.send(embed=question_embed)
            
            # Wait for user answer
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel
            
            try:
                answer_msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                
                if answer_msg.content.lower() == 'quit':
                    await ctx.send("🚪 Quiz ended early. Thanks for playing!")
                    return
                
                try:
                    user_choice = int(answer_msg.content)
                    if user_choice == correct_index:
                        correct_answers += 1
                        await answer_msg.add_reaction("✅")
                    else:
                        await answer_msg.add_reaction("❌")
                        await ctx.send(f"❌ Incorrect! The right answer was **{correct_index}. {correct_answer}**")
                except ValueError:
                    await ctx.send("❌ Please enter a number between 1-4")
                    i -= 1  # Retry this question
                    continue
                    
            except asyncio.TimeoutError:
                await ctx.send("⏰ Quiz timed out. Moving to next question...")
        
        # Quiz finished - show results
        score_percentage = (correct_answers / len(words)) * 100
        
        result_embed = discord.Embed(
            title="🎉 Quiz Complete!",
            description=f"**Final Score: {correct_answers}/{len(words)} ({score_percentage:.1f}%)**",
            color=discord.Color.green() if score_percentage >= 80 else discord.Color.orange() if score_percentage >= 60 else discord.Color.red()
        )
        
        # Award points based on performance
        base_points = correct_answers * 5
        bonus_points = 0
        
        if score_percentage >= 90:
            bonus_points = 20
            result_embed.add_field(name="🏆 Perfect!", value="+20 bonus points", inline=False)
        elif score_percentage >= 80:
            bonus_points = 10
            result_embed.add_field(name="🎯 Excellent!", value="+10 bonus points", inline=False)
        elif score_percentage >= 70:
            bonus_points = 5
            result_embed.add_field(name="👍 Good job!", value="+5 bonus points", inline=False)
        
        total_points = base_points + bonus_points
        
        result_embed.add_field(
            name="Points Earned",
            value=f"**{base_points}** (base) + **{bonus_points}** (bonus) = **{total_points}** total",
            inline=False
        )
        
        # Update user stats
        await self.update_quiz_stats(int(ctx.author.id), int(ctx.guild.id), language, level, correct_answers, len(words), total_points)
        
        result_embed.set_footer(text="Keep practicing with /lang_quiz to improve your score!")
        
        await ctx.send(embed=result_embed)
    
    async def update_quiz_stats(self, user_id: int, guild_id: int, language: str, level: str, correct: int, total: int, points_earned: int):
        """Update quiz statistics"""
        today = datetime.date.today().isoformat()
        
        with sqlite3.connect(PROGRESS_DB) as conn:
            cursor = conn.cursor()
            
            # Update user progress with quiz points
            cursor.execute('''
                UPDATE user_progress 
                SET total_points = total_points + ?
                WHERE user_id = ? AND guild_id = ? AND language = ? AND level = ?
            ''', (points_earned, user_id, guild_id, language, level))
            
            # Update daily stats
            cursor.execute('''
                UPDATE daily_stats 
                SET quizzes_completed = quizzes_completed + 1, points_earned = points_earned + ?
                WHERE user_id = ? AND guild_id = ? AND date = ?
            ''', (points_earned, user_id, guild_id, today))
            
            # If no daily stats exist, create them
            if cursor.rowcount == 0:
                cursor.execute('''
                    INSERT INTO daily_stats (user_id, guild_id, date, quizzes_completed, points_earned)
                    VALUES (?, ?, ?, 1, ?)
                ''', (user_id, guild_id, today, points_earned))

    @commands.hybrid_command(name="lang_leaderboard", description="Show the server leaderboard for language learning") 
    @discord.app_commands.autocomplete(language=language_autocomplete, level=level_autocomplete)
    async def leaderboard(self, ctx: commands.Context, language: str = None, level: str = None):
        """Show leaderboard for language learning"""
        if ctx.interaction:
            await ctx.defer()
            
        guild_id = ctx.guild.id
        
        with sqlite3.connect(PROGRESS_DB) as conn:
            cursor = conn.cursor()
            
            if language and level:
                # Specific language/level leaderboard
                cursor.execute('''
                    SELECT user_id, total_points, words_learned, streak_days
                    FROM user_progress 
                    WHERE guild_id = ? AND language = ? AND level = ?
                    ORDER BY total_points DESC
                    LIMIT 10
                ''', (guild_id, language.lower(), level.lower()))
            else:
                # Overall leaderboard
                cursor.execute('''
                    SELECT user_id, SUM(total_points) as total_points, 
                           SUM(words_learned) as total_words, MAX(streak_days) as best_streak
                    FROM user_progress 
                    WHERE guild_id = ?
                    GROUP BY user_id
                    ORDER BY total_points DESC
                    LIMIT 10
                ''', (guild_id,))
            
            results = cursor.fetchall()
        
        if not results:
            return await ctx.send("📊 No learners found on this server yet!")
        
        # Create leaderboard embed
        if language and level:
            title = f"🏆 {LANGUAGES.get(language, {}).get('name', language)} {level} Leaderboard"
        else:
            title = "🏆 Overall Language Learning Leaderboard"
        
        embed = discord.Embed(
            title=title,
            description=f"Top learners in **{ctx.guild.name}**",
            color=discord.Color.gold()
        )
        
        medal_emojis = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        
        leaderboard_text = []
        for i, (user_id, points, words, streak) in enumerate(results):
            user = ctx.guild.get_member(user_id)
            username = user.display_name if user else f"User {user_id}"
            
            if language and level:
                line = f"{medal_emojis[i]} **{username}** - {points:,} pts, {words} words, {streak} day streak"
            else:
                line = f"{medal_emojis[i]} **{username}** - {points:,} pts, {words} words, {streak} day best streak"
                
            leaderboard_text.append(line)
        
        embed.add_field(
            name="Rankings",
            value="\n".join(leaderboard_text),
            inline=False
        )
        
        # Add user's position if not in top 10
        user_rank = await self.get_user_rank(ctx.author.id, guild_id, language, level)
        if user_rank and user_rank > 10:
            embed.add_field(
                name="Your Position",
                value=f"🔢 **#{user_rank}** - Keep learning to climb higher!",
                inline=False
            )
        
        embed.set_footer(text="📈 Points are earned through daily study and quizzes")
        
        await ctx.send(embed=embed)
    
    async def get_user_rank(self, user_id: int, guild_id: int, language: str = None, level: str = None) -> Optional[int]:
        """Get user's rank in leaderboard"""
        with sqlite3.connect(PROGRESS_DB) as conn:
            cursor = conn.cursor()
            
            if language and level:
                cursor.execute('''
                    SELECT user_id, total_points,
                           ROW_NUMBER() OVER (ORDER BY total_points DESC) as rank
                    FROM user_progress 
                    WHERE guild_id = ? AND language = ? AND level = ?
                ''', (guild_id, language, level))
            else:
                cursor.execute('''
                    SELECT user_id, SUM(total_points) as total_points,
                           ROW_NUMBER() OVER (ORDER BY SUM(total_points) DESC) as rank
                    FROM user_progress 
                    WHERE guild_id = ?
                    GROUP BY user_id
                ''', (guild_id,))
            
            results = cursor.fetchall()
            
            for uid, points, rank in results:
                if uid == user_id:
                    return rank
        
        return None
    
    @commands.hybrid_command(name="lang_send_now", description="Manually send vocabulary (Admin only)")
    @commands.has_permissions(administrator=True)
    async def send_vocabulary_now(self, ctx: commands.Context):
        """Manually trigger vocabulary sending"""
        # Defer immediately as this can take a long time
        if ctx.interaction:
            await ctx.defer()
            
        embed = discord.Embed(
            title="🔄 Sending Daily Vocabulary",
            description="Preparing vocabulary for all registered learners...",
            color=discord.Color.blue()
        )
        
        message = await ctx.send(embed=embed)
        
        try:
            await self.send_daily_vocabulary()
            
            embed.title = "✅ Vocabulary Sent Successfully"
            embed.description = "Daily vocabulary has been delivered to all registered channels!"
            embed.color = discord.Color.green()
            embed.set_footer(text=f"Completed at {datetime.datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            embed.title = "❌ Error Sending Vocabulary"
            embed.description = f"An error occurred: {str(e)}"
            embed.color = discord.Color.red()
            logger.error(f"Error in manual vocabulary send: {e}")
        
        await message.edit(embed=embed)
    
    @commands.hybrid_command(name="lang_unregister", description="Unregister from language learning")
    @discord.app_commands.autocomplete(language=language_autocomplete, level=level_autocomplete)
    async def unregister_language(self, ctx: commands.Context, language: str, level: str):
        """Unregister from daily language vocabulary"""
        language = language.lower()
        level = level.lower()
        
        # Validate language and level
        if language not in LANGUAGES:
            available_langs = "\n".join([f"• **{code}**: {info['name']}" for code, info in LANGUAGES.items()])
            return await ctx.send(f"❌ Invalid language. Available languages:\n{available_langs}")
        
        if level not in LANGUAGES[language]["levels"]:
            available_levels = "\n".join([f"• **{code}**: {info['name']}" for code, info in LANGUAGES[language]['levels'].items()])
            return await ctx.send(f"❌ Invalid level for {language}. Available levels:\n{available_levels}")
        
        # Remove registration
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if (guild_id in self.learners and 
            language in self.learners[guild_id] and 
            level in self.learners[guild_id][language] and
            user_id in self.learners[guild_id][language][level]):
            
            self.learners[guild_id][language][level].remove(user_id)
            
            # Clean up empty structures
            if not self.learners[guild_id][language][level]:
                del self.learners[guild_id][language][level]
            if not self.learners[guild_id][language]:
                del self.learners[guild_id][language]
            if not self.learners[guild_id]:
                del self.learners[guild_id]
            
            self.save_data()
            
            # Remove role
            if guild_id in self.server_configs and language in self.server_configs[guild_id]:
                role_info = self.server_configs[guild_id][language]["channels"].get(level)
                if role_info:
                    role = ctx.guild.get_role(role_info["role_id"])
                    if role and role in ctx.author.roles:
                        try:
                            await ctx.author.remove_roles(role)
                        except Exception as e:
                            logger.error(f"Failed to remove role: {e}")
            
            lang_config = LANGUAGES[language]
            level_config = lang_config["levels"][level]
            
            embed = discord.Embed(
                title=f"{lang_config['emoji']} Unregistered Successfully",
                description=f"✅ You've been unregistered from **{lang_config['name']} - {level_config['name']}**",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="📊 Your Progress",
                value="Your learning progress has been preserved.\nYou can re-register anytime to continue where you left off!",
                inline=False
            )
            
            embed.set_footer(text="Use /lang_register to join again anytime")
            
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ You're not registered for {language} {level}")
    
    @commands.hybrid_command(name="lang_list", description="List your language registrations")
    async def list_registrations(self, ctx: commands.Context):
        """List user's current registrations"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if guild_id not in self.learners:
            return await ctx.send("❌ You have no language learning registrations in this server.")
        
        embed = discord.Embed(
            title="📚 Your Language Registrations",
            description=f"**{ctx.author.display_name}**'s active learning languages",
            color=discord.Color.blue()
        )
        
        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url
        )
        
        registered_count = 0
        
        for language, levels in self.learners[guild_id].items():
            for level, users in levels.items():
                if user_id in users:
                    registered_count += 1
                    
                    lang_config = LANGUAGES[language]
                    level_config = lang_config["levels"][level]
                    
                    # Get channel info
                    channel_info = self.server_configs.get(guild_id, {}).get(language, {}).get("channels", {}).get(level)
                    if channel_info:
                        channel = ctx.guild.get_channel(channel_info["channel_id"])
                        channel_mention = channel.mention if channel else "Channel not found"
                    else:
                        channel_mention = "Channel setup pending"
                    
                    embed.add_field(
                        name=f"{lang_config['emoji']} {lang_config['name']} - {level_config['emoji']} {level_config['name']}",
                        value=f"📢 **Channel:** {channel_mention}\n⏰ **Daily delivery:** {DEFAULT_SEND_TIME}:00",
                        inline=False
                    )
        
        if registered_count == 0:
            return await ctx.send("❌ You have no language learning registrations in this server.")
        
        embed.add_field(
            name="🎯 Commands",
            value=(
                "• `/lang_progress` - Check your learning progress\n"
                "• `/lang_quiz <language> <level>` - Take a vocabulary quiz\n"
                "• `/lang_unregister <language> <level>` - Unregister from a language"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"Total registrations: {registered_count} | Use /lang_register to add more")
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    await bot.add_cog(LanguageLearningV2Cog(bot))
    logger.info("Language Learning V2 module loaded") 