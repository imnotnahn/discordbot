import discord
from discord.ext import commands
import logging
import asyncio
import os
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('discord_bot')

class GameBot(commands.Bot):
    def __init__(self):
        # Enhanced intents to handle message content, reactions, and mentions
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.members = True
        
        # Load config
        with open('./config.json', 'r') as f:
            self.config = json.load(f)
            
        super().__init__(command_prefix=self.config.get('prefix', '!'), intents=intents)
        
    async def setup_hook(self):
        # Load all cogs from functions directory
        for filename in os.listdir('./functions'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'functions.{filename[:-3]}')
                    logger.info(f"Loaded function: {filename}")
                except Exception as e:
                    logger.error(f"Failed to load function {filename}: {e}")
        
        # Load all cogs from game directory if it exists
        game_dir = './game'
        if os.path.exists(game_dir):
            for filename in os.listdir(game_dir):
                if filename.endswith('.py'):
                    try:
                        await self.load_extension(f'game.{filename[:-3]}')
                        logger.info(f"Loaded game extension: {filename}")
                    except Exception as e:
                        logger.error(f"Failed to load game extension {filename}: {e}")
        
        await self.tree.sync()
        logger.info("Slash commands synchronized!")

    async def on_ready(self):
        logger.info(f'Logged in successfully: {self.user.name} ({self.user.id})')
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="Cờ vây | Co Tuong | Voice Manager | Chat with me! | Type /help"
            )
        )

# Run the bot
def main():
    bot = GameBot()
    try:
        # Get token from config
        with open('./config.json', 'r') as f:
            config = json.load(f)
            TOKEN = config.get('token')
        
        if not TOKEN:
            logger.error("Token not found in config")
            return
            
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        print(f"Could not start bot. Error: {e}")

if __name__ == "__main__":
    main()