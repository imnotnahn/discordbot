import discord
from discord.ext import commands, tasks
import json
import logging
import os
import datetime
from typing import Dict, List, Optional, Tuple
import sqlite3
import asyncio
import random

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
            "hsk1": {"name": "HSK 1", "emoji": "1️⃣", "description": "Beginner level - 150 basic words"},
            "hsk2": {"name": "HSK 2", "emoji": "2️⃣", "description": "Elementary level - 300 words total"},
            "hsk3": {"name": "HSK 3", "emoji": "3️⃣", "description": "Intermediate level - 600 words total"},
            "hsk4": {"name": "HSK 4", "emoji": "4️⃣", "description": "Upper intermediate - 1200 words total"},
            "hsk5": {"name": "HSK 5", "emoji": "5️⃣", "description": "Advanced level - 2500 words total"}
        }
    },
    "english": {
        "name": "English",
        "emoji": "🇬🇧", 
        "color": 0x00247D,
        "thumbnail": "https://i.imgur.com/JOKsECQ.png",
        "levels": {
            "a1": {"name": "CEFR A1", "emoji": "🔰", "description": "Beginner - Basic vocabulary"},
            "a2": {"name": "CEFR A2", "emoji": "📘", "description": "Elementary - Pre-intermediate"},
            "b1": {"name": "CEFR B1", "emoji": "📗", "description": "Intermediate - Independent user"},
            "b2": {"name": "CEFR B2", "emoji": "📙", "description": "Upper-intermediate - Independent user"},
            "c1": {"name": "CEFR C1", "emoji": "📕", "description": "Advanced - Proficient user"},
            "c2": {"name": "CEFR C2", "emoji": "⭐", "description": "Mastery - Proficient user"}
        }
    },
    "japanese": {
        "name": "Japanese (日本語)",
        "emoji": "🇯🇵",
        "color": 0xBC002D,
        "thumbnail": "https://i.imgur.com/XYZ.png",
        "levels": {
            "jlpt_n5": {"name": "JLPT N5", "emoji": "5️⃣", "description": "Basic Japanese - 800 words"},
            "jlpt_n4": {"name": "JLPT N4", "emoji": "4️⃣", "description": "Elementary Japanese - 1500 words"},
            "jlpt_n3": {"name": "JLPT N3", "emoji": "3️⃣", "description": "Intermediate Japanese - 3750 words"},
            "jlpt_n2": {"name": "JLPT N2", "emoji": "2️⃣", "description": "Advanced Japanese - 6000 words"},
            "jlpt_n1": {"name": "JLPT N1", "emoji": "1️⃣", "description": "Proficient Japanese - 10000 words"}
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
            # Create user_progress table
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
            
            # Create word_reviews table with all required columns
            conn.execute('''
                CREATE TABLE IF NOT EXISTS word_reviews (
                    user_id INTEGER,
                    guild_id INTEGER,
                    language TEXT,
                    level TEXT,
                    word_index INTEGER,
                    correct_count INTEGER DEFAULT 0,
                    incorrect_count INTEGER DEFAULT 0,
                    last_reviewed DATE,
                    next_review_date DATE,
                    retention_strength REAL DEFAULT 1.0,
                    quiz_count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id, language, level, word_index)
                )
            ''')
            
            # Create daily_stats table
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
            
            # Create quiz_history table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS quiz_history (
                    user_id INTEGER,
                    guild_id INTEGER,
                    language TEXT,
                    level TEXT,
                    word_index INTEGER,
                    quiz_date DATE,
                    is_correct INTEGER,
                    PRIMARY KEY (user_id, guild_id, language, level, word_index, quiz_date)
                )
            ''')
            
            # Migration: Add missing columns to existing tables if they don't exist
            try:
                # Check and add guild_id to word_reviews if missing
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(word_reviews)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'guild_id' not in columns:
                    conn.execute('ALTER TABLE word_reviews ADD COLUMN guild_id INTEGER')
                    logger.info("Added guild_id column to word_reviews table")
                
                if 'quiz_count' not in columns:
                    conn.execute('ALTER TABLE word_reviews ADD COLUMN quiz_count INTEGER DEFAULT 0')
                    logger.info("Added quiz_count column to word_reviews table")
                    
                # Update NULL values to default values
                conn.execute('UPDATE word_reviews SET guild_id = 0 WHERE guild_id IS NULL')
                conn.execute('UPDATE word_reviews SET quiz_count = 0 WHERE quiz_count IS NULL')
                
            except Exception as e:
                logger.error(f"Migration error (this is usually normal for first run): {e}")
                
                # If migration fails, try to recreate word_reviews table with correct schema
                try:
                    # Backup existing data
                    cursor.execute('SELECT * FROM word_reviews')
                    existing_data = cursor.fetchall()
                    
                    # Drop and recreate table
                    conn.execute('DROP TABLE IF EXISTS word_reviews')
                    conn.execute('''
                        CREATE TABLE word_reviews (
                            user_id INTEGER,
                            guild_id INTEGER DEFAULT 0,
                            language TEXT,
                            level TEXT,
                            word_index INTEGER,
                            correct_count INTEGER DEFAULT 0,
                            incorrect_count INTEGER DEFAULT 0,
                            last_reviewed DATE,
                            next_review_date DATE,
                            retention_strength REAL DEFAULT 1.0,
                            quiz_count INTEGER DEFAULT 0,
                            PRIMARY KEY (user_id, guild_id, language, level, word_index)
                        )
                    ''')
                    
                    logger.info("Recreated word_reviews table with proper schema")
                    
                    # Restore data if possible (with default guild_id=0)
                    if existing_data:
                        for row in existing_data:
                            try:
                                # Insert with guild_id=0 if old data doesn't have it
                                if len(row) < 11:  # Old schema
                                    conn.execute('''
                                        INSERT INTO word_reviews 
                                        (user_id, guild_id, language, level, word_index, correct_count, 
                                         incorrect_count, last_reviewed, next_review_date, retention_strength, quiz_count)
                                        VALUES (?, 0, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                                    ''', row[:9])
                                else:  # New schema
                                    conn.execute('''
                                        INSERT INTO word_reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', row)
                            except Exception as restore_error:
                                logger.warning(f"Could not restore row {row}: {restore_error}")
                                
                except Exception as recreate_error:
                    logger.error(f"Could not recreate word_reviews table: {recreate_error}")
            
            conn.commit()
            logger.info("Database schema initialized/updated successfully")

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
                # Map level codes to actual file names
                file_mapping = {
                    # Chinese HSK files
                    "hsk1": "vi_cn_hsk1",
                    "hsk2": "vi_cn_hsk2", 
                    "hsk3": "vi_cn_hsk3",
                    "hsk4": "vi_cn_hsk4",
                    "hsk5": "vi_cn_hsk5",
                    # English CEFR files
                    "a1": "eng_cerf_vocab_A1",
                    "a2": "eng_cerf_vocab_A2",
                    "b1": "eng_cerf_vocab_B1",
                    "b2": "eng_cerf_vocab_B2",
                    "c1": "eng_cerf_vocab_C1",
                    "c2": "eng_cerf_vocab_C2",
                    # Japanese JLPT files
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
                            
                            # Handle different JSON structures
                            if lang_code == "chinese":
                                # Chinese files are arrays directly
                                if isinstance(vocab_data, list):
                                    processed_data = []
                                    for item in vocab_data:
                                        if item.get('forms') and len(item['forms']) > 0:
                                            form = item['forms'][0]  # Use first form
                                            processed_item = {
                                                'word': item.get('simplified', ''),
                                                'traditional': form.get('traditional', ''),
                                                'pinyin': form.get('transcriptions', {}).get('pinyin', ''),
                                                'meanings': form.get('meanings', []),
                                                'meaning': '; '.join(form.get('meanings', [])) if form.get('meanings') else '',
                                                'pos': ', '.join(item.get('pos', [])) if item.get('pos') else '',
                                                'frequency': item.get('frequency', 0)
                                            }
                                            processed_data.append(processed_item)
                                    vocab_data = processed_data
                                    
                            elif lang_code in ["english", "japanese"]:
                                # English and Japanese files have "data" wrapper
                                if isinstance(vocab_data, dict) and "data" in vocab_data:
                                    vocab_data = vocab_data["data"]
                                
                                # Process English data to standardize field names
                                if lang_code == "english":
                                    processed_data = []
                                    for item in vocab_data:
                                        processed_item = {
                                            'word': item.get('word', ''),
                                            'meaning': item.get('meaning', ''),
                                            'word_form': item.get('word_form', ''),
                                            'cefr_level': item.get('cefr_level', ''),
                                            'part_of_speech': item.get('word_form', ''),  # Alias
                                            'pronunciation': ''  # Will be added if available
                                        }
                                        processed_data.append(processed_item)
                                    vocab_data = processed_data
                                
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
            word_data = vocab_list[word_index].copy()
            word_data['word_index'] = word_index  # Add index for tracking
            words.append(word_data)
        
        return words

    async def get_quiz_words(self, user_id: int, guild_id: int, language: str, level: str, count: int = 10) -> List[dict]:
        """Get words for quiz with intelligent selection avoiding recent repeats"""
        vocab_key = f"{language}_{level}"
        if vocab_key not in self.vocabulary:
            return []
        
        vocab_list = self.vocabulary[vocab_key]
        if not vocab_list:
            return []
        
        with sqlite3.connect(PROGRESS_DB) as conn:
            cursor = conn.cursor()
            
            # Get user's current progress
            cursor.execute('''
                SELECT current_word_index FROM user_progress 
                WHERE user_id = ? AND guild_id = ? AND language = ? AND level = ?
            ''', (user_id, guild_id, language, level))
            
            result = cursor.fetchone()
            current_index = result[0] if result else 0
            
            # Get words that were quizzed in the last 7 days
            one_week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
            cursor.execute('''
                SELECT DISTINCT word_index FROM quiz_history 
                WHERE user_id = ? AND guild_id = ? AND language = ? AND level = ? 
                AND quiz_date > ?
            ''', (user_id, guild_id, language, level, one_week_ago))
            
            recent_quiz_indices = {row[0] for row in cursor.fetchall()}
        
        # Create word pool for selection
        total_words = len(vocab_list)
        
        # Priority 1: Words around current progress (not quizzed recently)
        priority_range = 100  # words around current position
        start_index = max(0, current_index - priority_range // 2)
        end_index = min(total_words, current_index + priority_range // 2)
        
        priority_words = []
        secondary_words = []
        fallback_words = []
        
        for i in range(start_index, end_index):
            word_data = vocab_list[i].copy()
            word_data['word_index'] = i
            
            if i not in recent_quiz_indices:
                priority_words.append(word_data)
            else:
                secondary_words.append(word_data)
        
        # If not enough priority words, expand range
        if len(priority_words) < count:
            for i in range(total_words):
                if i < start_index or i >= end_index:
                    word_data = vocab_list[i].copy()
                    word_data['word_index'] = i
                    
                    if i not in recent_quiz_indices:
                        fallback_words.append(word_data)
        
        # Select words intelligently
        selected_words = []
        
        # First, try to get from priority words
        available_priority = min(count, len(priority_words))
        if available_priority > 0:
            selected_words.extend(random.sample(priority_words, available_priority))
        
        # Fill remaining with secondary words if needed
        remaining_count = count - len(selected_words)
        if remaining_count > 0 and secondary_words:
            available_secondary = min(remaining_count, len(secondary_words))
            selected_words.extend(random.sample(secondary_words, available_secondary))
        
        # Fill remaining with fallback words if still needed
        remaining_count = count - len(selected_words)
        if remaining_count > 0 and fallback_words:
            available_fallback = min(remaining_count, len(fallback_words))
            selected_words.extend(random.sample(fallback_words, available_fallback))
        
        # If still not enough, use any available words
        if len(selected_words) < count:
            all_words = [vocab_list[i] for i in range(total_words)]
            for i, word in enumerate(all_words):
                word_copy = word.copy()
                word_copy['word_index'] = i
                if word_copy not in selected_words:
                    selected_words.append(word_copy)
                    if len(selected_words) >= count:
                        break
        
        return selected_words[:count]

    async def record_quiz_results(self, user_id: int, guild_id: int, language: str, level: str, 
                                quiz_results: List[Tuple[int, bool]], total_points: int):
        """Record quiz results and update user progress"""
        today = datetime.date.today().isoformat()
        
        with sqlite3.connect(PROGRESS_DB) as conn:
            cursor = conn.cursor()
            
            # Record each word's quiz result
            for word_index, is_correct in quiz_results:
                # Update quiz history
                cursor.execute('''
                    INSERT OR REPLACE INTO quiz_history 
                    (user_id, guild_id, language, level, word_index, quiz_date, is_correct)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, guild_id, language, level, word_index, today, int(is_correct)))
                
                # Get existing word review data
                cursor.execute('''
                    SELECT correct_count, incorrect_count, retention_strength, quiz_count
                    FROM word_reviews 
                    WHERE user_id = ? AND guild_id = ? AND language = ? AND level = ? AND word_index = ?
                ''', (user_id, guild_id, language, level, word_index))
                
                existing = cursor.fetchone()
                if existing:
                    old_correct, old_incorrect, old_strength, old_quiz_count = existing
                else:
                    old_correct, old_incorrect, old_strength, old_quiz_count = 0, 0, 1.0, 0
                
                # Calculate new values
                new_correct = old_correct + (1 if is_correct else 0)
                new_incorrect = old_incorrect + (0 if is_correct else 1)
                new_strength = old_strength * 1.2 if is_correct else old_strength * 0.8
                new_quiz_count = old_quiz_count + 1
                
                # Update or insert word review
                cursor.execute('''
                    INSERT OR REPLACE INTO word_reviews 
                    (user_id, guild_id, language, level, word_index, correct_count, incorrect_count, 
                     last_reviewed, next_review_date, retention_strength, quiz_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, date('now', '+3 days'), ?, ?)
                ''', (user_id, guild_id, language, level, word_index, new_correct, new_incorrect,
                      today, new_strength, new_quiz_count))
            
            # Update user progress - advance current_word_index for correctly answered words
            correct_words = [word_index for word_index, is_correct in quiz_results if is_correct]
            if correct_words:
                # Get current progress
                cursor.execute('''
                    SELECT current_word_index, words_learned, streak_days, last_study_date, total_points
                    FROM user_progress 
                    WHERE user_id = ? AND guild_id = ? AND language = ? AND level = ?
                ''', (user_id, guild_id, language, level))
                
                result = cursor.fetchone()
                if result:
                    current_index, learned, streak, last_date, points = result
                    
                    # Calculate new position based on highest correct word index
                    max_correct_index = max(correct_words)
                    new_index = max(current_index, max_correct_index + 1)
                    
                    # Calculate new streak
                    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
                    if last_date == yesterday:
                        new_streak = streak + 1
                    elif last_date == today:
                        new_streak = streak
                    else:
                        new_streak = 1
                    
                    # Update progress
                    cursor.execute('''
                        UPDATE user_progress 
                        SET current_word_index = ?, words_learned = ?, 
                            streak_days = ?, last_study_date = ?, total_points = ?
                        WHERE user_id = ? AND guild_id = ? AND language = ? AND level = ?
                    ''', (new_index, learned + len(correct_words), new_streak, today, 
                          points + total_points, user_id, guild_id, language, level))
                else:
                    # Create new progress record
                    max_correct_index = max(correct_words)
                    cursor.execute('''
                        INSERT INTO user_progress 
                        (user_id, guild_id, language, level, current_word_index, words_learned, 
                         streak_days, last_study_date, total_points)
                        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ''', (user_id, guild_id, language, level, max_correct_index + 1, 
                          len(correct_words), today, total_points))
            
            # Update daily stats  
            cursor.execute('''
                SELECT words_studied, quizzes_completed, points_earned 
                FROM daily_stats 
                WHERE user_id = ? AND guild_id = ? AND date = ?
            ''', (user_id, guild_id, today))
            
            daily_result = cursor.fetchone()
            if daily_result:
                current_words, current_quizzes, current_points = daily_result
                cursor.execute('''
                    UPDATE daily_stats 
                    SET words_studied = ?, quizzes_completed = ?, points_earned = ?
                    WHERE user_id = ? AND guild_id = ? AND date = ?
                ''', (current_words + len(correct_words), current_quizzes + 1, 
                      current_points + total_points, user_id, guild_id, today))
            else:
                cursor.execute('''
                    INSERT INTO daily_stats (user_id, guild_id, date, words_studied, quizzes_completed, points_earned)
                    VALUES (?, ?, ?, ?, 1, ?)
                ''', (user_id, guild_id, today, len(correct_words), total_points))

    async def update_progress(self, user_id: int, guild_id: int, language: str, level: str, words_studied: int):
        """Update user learning progress for daily vocabulary"""
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
                word = word_data.get('word', 'N/A')  # Simplified
                traditional = word_data.get('traditional', '')
                
                # Always show both simplified and traditional
                if traditional and traditional != word:
                    word_header = f"**{i}. {word}** ({traditional})"
                else:
                    word_header = f"**{i}. {word}**"
                
                # Format meanings with line breaks
                meanings = word_data.get('meanings', [])
                if meanings:
                    meanings_text = '\n'.join([f"• {meaning}" for meaning in meanings])
                else:
                    meanings_text = word_data.get('meaning', 'N/A')
                
                value_parts = [
                    f"🔊 **Pinyin:** {word_data.get('pinyin', 'N/A')}",
                    f"🏷️ **Từ loại:** {word_data.get('pos', 'N/A')}",
                    f"🔤 **Nghĩa:**\n{meanings_text}",
                    ""
                ]
                
            elif language == "english":
                word_header = f"**{i}. {word_data.get('word', 'N/A')}**"
                value_parts = [
                    f"🏷️ **Từ loại:** {word_data.get('word_form', 'N/A')}",
                    f"🔤 **Nghĩa:** {word_data.get('meaning', 'N/A')}",
                    f"📊 **CEFR Level:** {word_data.get('cefr_level', 'N/A')}",
                    ""
                ]
                
                # Add pronunciation if available
                pronunciation = word_data.get('pronunciation', '')
                if pronunciation:
                    value_parts.insert(0, f"🔊 **Phát âm:** {pronunciation}")
            
            elif language == "japanese":
                word = word_data.get('word', 'N/A')
                hiragana = word_data.get('hiragana', '')
                
                # Show hiragana if different from word
                if word != hiragana and hiragana:
                    word_header = f"**{i}. {word}** ({hiragana})"
                else:
                    word_header = f"**{i}. {word}**"
                
                value_parts = [
                    f"🔊 **Romaji:** {word_data.get('romaji', 'N/A')}",
                    f"🏷️ **Loại từ:** {word_data.get('category', 'N/A')}",
                    f"🔤 **Nghĩa:** {word_data.get('meaning', 'N/A')}",
                    f"📊 **JLPT Level:** N{word_data.get('jlpt_level', 'N/A')}",
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
        
        prep_msg = await ctx.send("🎯 Preparing your personalized vocabulary quiz...")
        
        try:
            question_count = min(question_count, 20)
            question_count = max(question_count, 5)
            
            # Use intelligent word selection
            selected_words = await self.get_quiz_words(int(user_id), int(guild_id), language, level, question_count)
            
            if not selected_words:
                try:
                    await prep_msg.edit(content="❌ No words available for quiz. Please try again later.")
                except discord.NotFound:
                    await ctx.send("❌ No words available for quiz. Please try again later.")
                return
            
            try:
                await prep_msg.edit(content="✨ Quiz prepared with smart word selection - avoiding recent repeats!")
                await asyncio.sleep(1)  # Brief pause to show the message
                await prep_msg.delete()
            except discord.NotFound:
                # Message was already deleted, just continue
                pass
            
            await self.start_quiz(ctx, language, level, selected_words)
            
        except Exception as e:
            logger.error(f"Error in vocabulary_quiz: {e}")
            try:
                await prep_msg.edit(content=f"❌ An error occurred while preparing the quiz: {str(e)}")
            except discord.NotFound:
                try:
                    await ctx.send(f"❌ An error occurred while preparing the quiz: {str(e)}")
                except:
                    pass
    
    def select_mixed_wrong_answers(self, all_options: List[dict], current_word_type: str, count: int) -> List[str]:
        """Select wrong answers with mixed word types to avoid pattern recognition"""
        if not all_options:
            return ["Unknown option"] * count
        
        # Group options by word type
        same_type = []
        different_type = []
        
        for option in all_options:
            if option['word_type'] == current_word_type:
                same_type.append(option['meaning'])
            else:
                different_type.append(option['meaning'])
        
        wrong_answers = []
        
        # Strategy: Mix word types intelligently
        if len(different_type) >= count:
            # If we have enough different types, use mostly different types with maybe 1 same type
            if len(same_type) > 0 and count >= 2:
                # Add 1 same type and rest different types
                wrong_answers.append(random.choice(same_type))
                wrong_answers.extend(random.sample(different_type, count - 1))
            else:
                # All different types
                wrong_answers = random.sample(different_type, count)
        elif len(same_type) >= count:
            # If we only have same types, add some different types if available
            if len(different_type) > 0:
                # Mix: 1-2 different types, rest same type
                different_count = min(len(different_type), count // 2)
                wrong_answers.extend(random.sample(different_type, different_count))
                wrong_answers.extend(random.sample(same_type, count - different_count))
            else:
                # All same type (fallback)
                wrong_answers = random.sample(same_type, count)
        else:
            # Mix whatever we have
            available_meanings = [opt['meaning'] for opt in all_options]
            wrong_answers = random.sample(available_meanings, min(count, len(available_meanings)))
        
        # Fill up if we don't have enough
        while len(wrong_answers) < count:
            wrong_answers.append("Unknown option")
            
        return wrong_answers[:count]

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
        quiz_results = []  # Track results: [(word_index, is_correct), ...]
        
        for i, word_data in enumerate(words, 1):
            # Create multiple choice question
            word_index = word_data.get('word_index', 0)  # Get the word index for tracking
            
            # For Chinese, get the first meaning if multiple meanings exist
            if language == "chinese":
                meanings = word_data.get('meanings', [])
                if meanings:
                    correct_answer = meanings[0]  # Take first meaning only
                else:
                    correct_answer = word_data.get('meaning', 'Unknown')
            else:
                correct_answer = word_data.get('meaning', 'Unknown')
            
            # Get other wrong answers from the same vocabulary set with mixed word types
            vocab_key = f"{language}_{level}"
            
            # Get current word type for mixing strategy
            if language == "english":
                current_word_form = word_data.get('word_form', '')
            elif language == "chinese":
                current_pos = word_data.get('pos', '')
            elif language == "japanese":
                current_category = word_data.get('category', '')
            else:
                current_word_form = ''
            
            # Collect wrong answers with word type info
            all_options = []
            for w in self.vocabulary[vocab_key]:
                if w != word_data:
                    if language == "chinese":
                        w_meanings = w.get('meanings', [])
                        meaning = w_meanings[0] if w_meanings else w.get('meaning', 'Unknown')
                        all_options.append({
                            'meaning': meaning,
                            'word_type': w.get('pos', ''),
                            'word': w.get('word', '')
                        })
                    elif language == "english":
                        all_options.append({
                            'meaning': w.get('meaning', 'Unknown'),
                            'word_type': w.get('word_form', ''),
                            'word': w.get('word', '')
                        })
                    elif language == "japanese":
                        all_options.append({
                            'meaning': w.get('meaning', 'Unknown'),
                            'word_type': w.get('category', ''),
                            'word': w.get('word', '')
                        })
            
            # Smart selection: mix word types to avoid pattern recognition
            wrong_answers = self.select_mixed_wrong_answers(all_options, current_word_form if language == "english" else current_pos if language == "chinese" else current_category if language == "japanese" else '', 3)
            
            # Ensure we have 4 choices total (1 correct + 3 wrong)
            choices = [correct_answer] + wrong_answers
            random.shuffle(choices)
            correct_index = choices.index(correct_answer) + 1
            
            # Create question embed with better styling
            question_embed = discord.Embed(
                title=f"🎯 Question {i}/{len(words)}",
                description=f"💡 **{lang_config['name']} Quiz** • {level_config['name']}",
                color=lang_config["color"]
            )
            
            if language == "chinese":
                word = word_data.get('word', 'N/A')  # Simplified
                traditional = word_data.get('traditional', '')
                
                # Always show both simplified and traditional  
                if traditional and traditional != word:
                    word_text = f"**{word}** ({traditional})"
                else:
                    word_text = f"**{word}**"
                
                # Don't show meanings in question - only word info for quiz
                # Create elegant display for Chinese - just essential info
                display_value = f"🔤 {word_text}\n📝 *{word_data.get('pinyin', 'N/A')}* • *{word_data.get('pos', 'N/A')}*"
                
                question_embed.add_field(
                    name="📚 词汇 (Vocabulary)",
                    value=display_value,
                    inline=False
                )
            elif language == "english":
                word_text = word_data.get('word', 'N/A')
                word_form = word_data.get('word_form', '')
                cefr_level = word_data.get('cefr_level', '')
                
                # Create a more elegant display
                display_parts = [f"🔤 **{word_text}**"]
                if word_form:
                    display_parts.append(f"📝 *{word_form}*")
                if cefr_level:
                    display_parts.append(f"📊 *Level {cefr_level.upper()}*")
                
                question_embed.add_field(
                    name="📚 Vocabulary",
                    value=" • ".join(display_parts),
                    inline=False
                )
            elif language == "japanese":
                word_display = word_data.get('word', 'N/A')
                hiragana_display = word_data.get('hiragana', '')
                if word_display != hiragana_display and hiragana_display:
                    word_text = f"**{word_display}** ({hiragana_display})"
                else:
                    word_text = f"**{word_display}**"
                # Create elegant display for Japanese
                romaji = word_data.get('romaji', 'N/A')
                category = word_data.get('category', 'N/A')
                jlpt_level = word_data.get('jlpt_level', 'N/A')
                
                display_parts = [f"🔤 {word_text}"]
                display_parts.append(f"📝 *{romaji}*")
                if category != 'N/A':
                    display_parts.append(f"*{category}*")
                if jlpt_level != 'N/A':
                    display_parts.append(f"📊 *N{jlpt_level}*")
                
                question_embed.add_field(
                    name="📚 語彙 (Vocabulary)", 
                    value=" • ".join(display_parts),
                    inline=False
                )
            
            # Create choices display (no emojis for cleaner look)
            choices_text = "\n".join([f"**{j}.** {choice}" for j, choice in enumerate(choices, 1)])
            
            # Customize question text based on language
            question_text = "❓ What does this word mean?"
            
            question_embed.add_field(
                name=question_text,
                value=choices_text,
                inline=False
            )
            
            # Add footer with instruction
            question_embed.set_footer(
                text=f"⌨️ Type 1-4 or 'quit' to exit • Score: {correct_answers}/{i-1}",
                icon_url=ctx.author.display_avatar.url
            )
            
            await ctx.send(embed=question_embed)
            
            # Wait for user answer
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel
            
            is_correct = False
            try:
                answer_msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                
                if answer_msg.content.lower() == 'quit':
                    await ctx.send("🚪 Quiz ended early. Thanks for playing!")
                    # Still record partial results if quiz was quit
                    if quiz_results:
                        total_points = sum([5 for _, correct in quiz_results if correct])
                        await self.record_quiz_results(int(ctx.author.id), int(ctx.guild.id), 
                                                     language, level, quiz_results, total_points)
                    return
                
                try:
                    user_choice = int(answer_msg.content)
                    if user_choice == correct_index:
                        correct_answers += 1
                        is_correct = True
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
            
            # Record this question's result
            quiz_results.append((word_index, is_correct))
        
        # Quiz finished - show results
        score_percentage = (correct_answers / len(words)) * 100
        
        # Determine result emoji and color based on performance
        if score_percentage >= 90:
            result_emoji = "🏆"
            result_color = discord.Color.gold()
            performance_text = "Perfect! Outstanding performance!"
        elif score_percentage >= 80:
            result_emoji = "🎯"
            result_color = discord.Color.green()
            performance_text = "Excellent! Great job!"
        elif score_percentage >= 70:
            result_emoji = "👍"
            result_color = discord.Color.blue()
            performance_text = "Good work! Keep it up!"
        elif score_percentage >= 50:
            result_emoji = "📈"
            result_color = discord.Color.orange()
            performance_text = "Not bad! Keep practicing!"
        else:
            result_emoji = "💪"
            result_color = discord.Color.red()
            performance_text = "Keep studying! You'll improve!"
        
        result_embed = discord.Embed(
            title=f"{result_emoji} Quiz Complete!",
            description=f"**{ctx.author.display_name}** • {lang_config['name']} {level_config['name']}\n\n🎯 **Final Score: {correct_answers}/{len(words)} ({score_percentage:.1f}%)**\n💭 *{performance_text}*",
            color=result_color
        )
        
        # Award points based on performance
        base_points = correct_answers * 5
        bonus_points = 0
        
        if score_percentage >= 90:
            bonus_points = 20
        elif score_percentage >= 80:
            bonus_points = 10
        elif score_percentage >= 70:
            bonus_points = 5
        
        total_points = base_points + bonus_points
        
        # Create points display
        points_display = f"💰 **Base Points:** {base_points} ({correct_answers} correct × 5)\n"
        if bonus_points > 0:
            points_display += f"🎁 **Bonus Points:** +{bonus_points}\n"
        points_display += f"⭐ **Total Earned:** **{total_points} points**"
        
        result_embed.add_field(
            name="🏅 Points Breakdown",
            value=points_display,
            inline=False
        )
        
        # Add progress update info
        correct_word_indices = [idx for idx, correct in quiz_results if correct]
        if correct_word_indices:
            result_embed.add_field(
                name="📈 Progress Update",
                value=f"✅ {len(correct_word_indices)} words mastered - your learning progress has been updated!",
                inline=False
            )
        
        # Record quiz results using new system
        await self.record_quiz_results(int(ctx.author.id), int(ctx.guild.id), language, level, quiz_results, total_points)
        
        # Add thumbnail and footer
        result_embed.set_thumbnail(url=lang_config["thumbnail"])
        result_embed.set_footer(
            text=f"🚀 Keep practicing with /lang_quiz to improve! • {lang_config['name']} Learning",
            icon_url=ctx.author.display_avatar.url
        )
        
        await ctx.send(embed=result_embed)

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