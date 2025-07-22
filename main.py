import discord
from discord.ext import commands
import logging
import asyncio
import os
import json
import subprocess
import sys
import time
import signal

# Setup logging with more detailed configuration
def setup_logging(config):
    """Setup logging with configuration"""
    log_level = getattr(logging, config.get('logging', {}).get('level', 'INFO'))
    
    # Create logs directory
    os.makedirs('./logs', exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('./logs/bot.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific loggers
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.WARNING)  # Reduce Discord spam
    
    return logging.getLogger('discord_bot')

def validate_config(config):
    """Validate configuration file"""
    required_fields = ['token']
    
    for field in required_fields:
        if not config.get(field):
            raise ValueError(f"Missing required config field: {field}")
    
    # Validate language learning config
    if config.get('language_learning', {}).get('enabled', False):
        lang_config = config['language_learning']
        if not isinstance(lang_config.get('daily_send_time'), int) or not (0 <= lang_config['daily_send_time'] <= 23):
            raise ValueError("daily_send_time must be an integer between 0-23")
        if not isinstance(lang_config.get('words_per_day'), int) or lang_config['words_per_day'] <= 0:
            raise ValueError("words_per_day must be a positive integer")
    
    return True

class GameBot(commands.Bot):
    def __init__(self, config):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.members = True
        
        self.config = config
        validate_config(config)
        
        super().__init__(
            command_prefix=config.get('prefix', '!'), 
            intents=intents,
            help_command=None
        )
        
        self.logger = setup_logging(config)
        
    async def setup_hook(self):
        """Setup hook for loading extensions"""
        extensions_loaded = 0
        extensions_failed = 0
        
        if os.path.exists('./functions'):
            for filename in os.listdir('./functions'):
                if not filename.endswith('.py') or filename.startswith('_'):
                    continue
                
                extension_name = filename[:-3]
                
                if not self._is_extension_enabled(extension_name):
                    self.logger.info(f"Skipping disabled extension: {extension_name}")
                    continue
                
                try:
                    await self.load_extension(f'functions.{extension_name}')
                    self.logger.info(f"✅ Loaded function: {extension_name}")
                    extensions_loaded += 1
                except Exception as e:
                    self.logger.error(f"❌ Failed to load function {extension_name}: {e}")
                    extensions_failed += 1
        
        # Load game_tactic extensions
        if os.path.exists('./game_tactic'):
            for filename in os.listdir('./game_tactic'):
                if not filename.endswith('.py') or filename.startswith('_'):
                    continue
                
                extension_name = filename[:-3]
                
                try:
                    await self.load_extension(f'game_tactic.{extension_name}')
                    self.logger.info(f"✅ Loaded game_tactic extension: {extension_name}")
                    extensions_loaded += 1
                except Exception as e:
                    self.logger.error(f"❌ Failed to load game_tactic extension {extension_name}: {e}")
                    extensions_failed += 1
        
        # Sync slash commands
        try:
            await self.tree.sync()
            self.logger.info("✅ Slash commands synchronized!")
        except Exception as e:
            self.logger.error(f"❌ Failed to sync slash commands: {e}")
        
        self.logger.info(f"📊 Extensions loaded: {extensions_loaded}, Failed: {extensions_failed}")
    
    def _is_extension_enabled(self, extension_name: str) -> bool:
        """Check if extension is enabled in config"""
        # Map extension names to config keys
        extension_config_map = {
            'language_learning': 'language_learning.enabled',
            'language_learning_v2': 'language_learning.enabled', 
            'voice_manager': 'voice_manager.enabled',
            'voice_activity_logger': 'voice_manager.enabled',
            'gemini_chat': 'features.gemini_chat',
            'fun': 'fun_commands.enabled',
            'cotuong': 'games.cotuong_enabled',
            'covay': 'games.covay_enabled', 
            'ca_ngua': 'games.cangua_enabled'
        }
        
        config_path = extension_config_map.get(extension_name)
        if not config_path:
            return True  # Enable by default if no config specified
        
        # Navigate config path
        config_value = self.config
        for key in config_path.split('.'):
            config_value = config_value.get(key, True)
            if not isinstance(config_value, dict) and key != config_path.split('.')[-1]:
                break
        
        return bool(config_value)

    async def on_ready(self):
        """Called when bot is ready"""
        self.logger.info(f'🤖 Logged in successfully: {self.user.name} ({self.user.id})')
        
        # Set presence based on enabled features
        activity_parts = []
        if self.config.get('games', {}).get('cotuong_enabled', True):
            activity_parts.append("Co Tuong")
        if self.config.get('games', {}).get('covay_enabled', True):
            activity_parts.append("Cờ vây")
        if self.config.get('voice_manager', {}).get('enabled', True):
            activity_parts.append("Voice Manager")
        if self.config.get('features', {}).get('gemini_chat', True):
            activity_parts.append("Chat with me!")
        if self.config.get('language_learning', {}).get('enabled', True):
            activity_parts.append("Language Learning")
        
        activity_text = " | ".join(activity_parts) + " | Type /help"
        
        try:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.playing,
                    name=activity_text
                )
            )
        except Exception as e:
            self.logger.error(f"Failed to set presence: {e}")
    
    async def on_error(self, event, *args, **kwargs):
        """Global error handler"""
        self.logger.error(f"Error in event {event}: {sys.exc_info()}")
    
    async def on_command_error(self, ctx, error):
        """Command error handler"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        elif isinstance(error, commands.MissingPermissions):
            try:
                await ctx.send("❌ You don't have permission to use this command.")
            except:
                pass
        elif isinstance(error, commands.MissingRequiredArgument):
            try:
                await ctx.send(f"❌ Missing required argument: `{error.param.name}`")
            except:
                pass
        elif isinstance(error, commands.BadArgument):
            try:
                await ctx.send(f"❌ Invalid argument: {str(error)}")
            except:
                pass
        elif isinstance(error, commands.CommandOnCooldown):
            try:
                await ctx.send(f"⏰ Command on cooldown. Try again in {error.retry_after:.1f} seconds.")
            except:
                pass
        elif isinstance(error, discord.NotFound) and "Unknown interaction" in str(error):
            # Handle interaction timeout errors silently
            self.logger.warning(f"Interaction timeout in command {ctx.command}: {error}")
            return
        elif isinstance(error, (commands.HybridCommandError, commands.CommandInvokeError)):
            # Unwrap the actual error
            actual_error = error.original if hasattr(error, 'original') else error
            
            if isinstance(actual_error, discord.NotFound) and "Unknown interaction" in str(actual_error):
                self.logger.warning(f"Interaction timeout in command {ctx.command}: {actual_error}")
                return
            
            self.logger.error(f"Command error in {ctx.command}: {actual_error}", exc_info=actual_error)
            try:
                await ctx.send("❌ An unexpected error occurred. Please try again.")
            except:
                pass
        else:
            self.logger.error(f"Unhandled command error: {error}", exc_info=error)
            try:
                await ctx.send("❌ An unexpected error occurred. Please try again.")
            except:
                pass

# Custom help command
@commands.hybrid_command(name="help", description="Show bot help")
async def help_command(ctx):
    """Custom help command"""
    embed = discord.Embed(
        title="🤖 Bot Commands Help",
        description="Here are all available commands organized by category:",
        color=discord.Color.blue()
    )
    
    # Language Learning Commands
    embed.add_field(
        name="📚 Language Learning",
        value=(
            "• `/lang_register <language> <level>` - Register for daily vocabulary\n"
            "• `/lang_unregister <language> <level>` - Unregister from vocabulary\n"
            "• `/lang_progress` - Check your learning progress\n"
            "• `/lang_list` - List your registrations\n"
            "• `/lang_send_now` - Send vocabulary now (Admin only)"
        ),
        inline=False
    )
    
    # Game Commands
    embed.add_field(
        name="🎮 Games",
        value=(
            "• `/cotuong_play @player1 @player2` - Start Chinese Chess game\n"
            "• `/cotuong_move <piece> <from_x> <from_y> <to_x> <to_y>` - Make a move\n"
            "• `/covay_play @player1 @player2 <size>` - Start Go game\n"
            "• `/covay_move <x> <y>` - Place stone\n"
            "• `/cangua_play @players...` - Start Ludo game"
        ),
        inline=False
    )
    
    # Fun Commands  
    embed.add_field(
        name="🎪 Fun",
        value=(
            "• `/fun_isgay @user` - Check gay meter (for fun)\n"
            "• `@mention bot` or reply - Chat with AI\n"
            "• `/chatai_clear` - Clear chat history"
        ),
        inline=False
    )
    
    # Voice Commands
    embed.add_field(
        name="🔊 Voice",
        value=(
            "• Join **'tạo phòng'** channel to create private voice room\n"
            "• Voice channels auto-cleanup when empty"
        ),
        inline=False
    )
    
    embed.set_footer(text="Bot created with ❤️ | Use slash commands (/) for best experience")
    
    await ctx.send(embed=embed)

# Signal handlers for graceful shutdown
def signal_handler(sig, frame):
    logger = logging.getLogger('discord_bot')
    logger.info("🛑 Shutdown signal received, cleaning up...")
    sys.exit(0)

# Register signal handlers  
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def load_config():
    """Load and validate configuration"""
    try:
        if not os.path.exists('./config.json'):
            print("❌ config.json not found! Please copy config.template.json to config.json and fill in your values.")
            sys.exit(1)
        
        with open('./config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        return config
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in config.json: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)

def main():
    """Main entry point"""
    # Load configuration
    config = load_config()
    
    # Initialize bot
    bot = GameBot(config)
    
    # Add custom help command
    bot.add_command(help_command)
    
    try:
        # Get token from config
        token = config.get('token')
        if not token:
            print("❌ No token found in config.json")
            return
        
        # Additional setup for specific features
        if config.get('features', {}).get('gemini_chat', True):
            gemini_key = config.get('gemini_api_key') or config.get('geminiApiKey')
            if gemini_key:
                # Pass Gemini API key to cog when loading
                bot.gemini_api_key = gemini_key
            else:
                print("⚠️  Gemini API key not found - AI chat will be disabled")
        
        print("🚀 Starting bot...")
        bot.run(token)
        
    except discord.LoginFailure:
        print("❌ Invalid bot token. Please check your config.json")
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
    finally:
        print("👋 Bot has shut down")

if __name__ == "__main__":
    main()