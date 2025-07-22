import discord
from discord.ext import commands
from google import genai 
import asyncio
import logging
import re
from typing import Optional, Dict

logger = logging.getLogger('discord_bot')

MAX_HISTORY_LENGTH = 10  
MAX_PROMPT_LENGTH = 30000  
THINKING_EMOJI = "🤔"
TYPING_DELAY = 1.0 

class GeminiAI:
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)  
        self.user_history: Dict[int, list] = {}  
        
    async def generate_response(self, user_id: int, prompt: str) -> str:
        try:
            if user_id not in self.user_history:
                self.user_history[user_id] = []
            
            chat_history = []
            for msg in self.user_history[user_id]:
                chat_history.append(msg)
            
            self.user_history[user_id].append({"role": "user", "parts": [{"text": prompt}]})
            
            if len(self.user_history[user_id]) > MAX_HISTORY_LENGTH:
                self.user_history[user_id] = self.user_history[user_id][-MAX_HISTORY_LENGTH:]
            
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-2.0-flash-thinking-exp-01-21",  
                contents=chat_history + [{"role": "user", "parts": [{"text": prompt}]}],
            )
            
            text_response = response.text
            
            self.user_history[user_id].append({"role": "model", "parts": [{"text": text_response}]})
            
            return text_response
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return f"Sorry, I encountered an error: {str(e)}"
    
    def clear_history(self, user_id: int) -> None:
        if user_id in self.user_history:
            del self.user_history[user_id]


class GeminiChatCog(commands.Cog):
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gemini_ai = None
        self.processing_messages = set()
        
        # Get API key from bot config (handle both old and new format)
        api_key = (getattr(bot, 'gemini_api_key', None) or 
                   bot.config.get('gemini_api_key') or 
                   bot.config.get('geminiApiKey'))
        
        if api_key:
            self.gemini_ai = GeminiAI(api_key)
            logger.info("✅ Gemini AI initialized successfully")
        else:
            logger.warning("⚠️ No Gemini API key found - AI chat disabled")
        
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.gemini_ai:  # AI not initialized
            return
            
        if message.author.bot:
            return
            
        if message.id in self.processing_messages:
            return
            
        should_respond = False
        prompt = ""
        
        if self.bot.user in message.mentions:
            prompt = re.sub(f'<@!?{self.bot.user.id}>', '', message.content).strip()
            should_respond = True
            
        elif message.reference and isinstance(message.reference.resolved, discord.Message):
            referenced_msg = message.reference.resolved
            if referenced_msg.author.id == self.bot.user.id:
                prompt = message.content.strip()
                should_respond = True
                
        if should_respond and prompt:
            self.processing_messages.add(message.id)
            
            try:
                await message.add_reaction(THINKING_EMOJI)
                
                async with message.channel.typing():
                    if len(prompt) > MAX_PROMPT_LENGTH:
                        prompt = prompt[:MAX_PROMPT_LENGTH] + "... (truncated)"
                        
                    response = await self.gemini_ai.generate_response(message.author.id, prompt)
                    
                    await asyncio.sleep(TYPING_DELAY)
                    
                    if len(response) <= 2000:
                        await message.reply(response)
                    else:
                        chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                        for i, chunk in enumerate(chunks):
                            if i == 0:
                                await message.reply(chunk)
                            else:
                                await message.channel.send(chunk)
            
            except Exception as e:
                logger.error(f"Error in Gemini chat handler: {e}")
                await message.channel.send(f"Sorry, I encountered an error: {str(e)}")
                
            finally:
                try:
                    await message.remove_reaction(THINKING_EMOJI, self.bot.user)
                except:
                    pass
                self.processing_messages.discard(message.id)
    
    @commands.hybrid_command(
        name="chatai_clear",
        description="Clear your chat history with the AI"
    )
    async def clear_chat(self, ctx: commands.Context):
        """Clear chat history"""
        if not self.gemini_ai:
            return await ctx.send("❌ AI chat is not available (no API key configured)")
            
        self.gemini_ai.clear_history(ctx.author.id)
        
        embed = discord.Embed(
            title="🧹 Chat History Cleared",
            description="✅ Your chat history has been cleared! We can start a fresh conversation.",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="chatai_help",
        description="Get help with using the Gemini AI chat feature"
    )
    async def gemini_help(self, ctx: commands.Context):
        """Show AI chat help"""
        if not self.gemini_ai:
            embed = discord.Embed(
                title="❌ AI Chat Unavailable",
                description="AI chat is currently disabled because no Gemini API key is configured.",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="How to Enable",
                value="Ask an administrator to add a `gemini_api_key` to the bot configuration.",
                inline=False
            )
            
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title="🤖 Gemini AI Chat Help",
            description="Chat with Google's Gemini AI through this bot!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💬 How to Chat",
            value=(
                "• **Mention the bot**: `@BotName your question here`\n"
                "• **Reply to bot messages**: Just reply to any of the bot's messages\n"
                "• **Natural conversation**: The AI remembers context from your recent messages"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Available Commands",
            value=(
                "• `/chatai_clear` - Reset your conversation history with the AI\n"
                "• `/chatai_help` - Show this help message\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Pro Tips",
            value=(
                "• The bot remembers your last 10 messages for context\n"
                "• For best results, ask clear and specific questions\n"
                "• Each user has their own separate conversation history\n"
                "• The AI can help with coding, explanations, creative writing, and more!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚡ AI Model",
            value="Using **Gemini 2.0 Flash Thinking** - Google's latest reasoning model",
            inline=False
        )
        
        embed.set_footer(text="AI responses are generated by Google Gemini and may not always be accurate")
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    await bot.add_cog(GeminiChatCog(bot))
    logger.info("Gemini Chat module loaded")