import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import yt_dlp
import os
import logging
import json
from typing import Dict, List, Optional, Any

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('music_bot')

# Đọc config
try:
    with open('config/config.json', 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
except Exception as e:
    logger.error(f"Không thể đọc file config: {e}")
    config = {"token": "", "spotify_client_id": "", "spotify_client_secret": ""}

# Các tùy chọn YT-DLP
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')
        self.requester = None

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, requester=None):
        loop = loop or asyncio.get_event_loop()
        logger.info(f"Đang xử lý URL: {url}")
        
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            # Lấy mục đầu tiên từ danh sách phát
            data = data['entries'][0]
            
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        # Fixed line - don't use create_source() method
        source = discord.FFmpegPCMAudio(filename, **ffmpeg_options)
        
        instance = cls(source, data=data)
        instance.requester = requester
        return instance

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        
        # Lưu trữ hàng đợi nhạc cho mỗi server
        self.music_queues: Dict[int, List[Dict[str, Any]]] = {}
    
    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Đã đồng bộ lệnh slash!")
    
    async def on_ready(self):
        logger.info(f'Đã đăng nhập thành công: {self.user.name} ({self.user.id})')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/help"))

bot = MusicBot()

# Quản lý hàng đợi nhạc
class MusicPlayer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.bot = ctx.bot
        self.guild_id = ctx.guild.id
        self.channel = ctx.channel
        self.queue = []
        self.next = asyncio.Event()
        self.current = None
        self.volume = 0.5
        
        self.bot.loop.create_task(self.player_loop())
    
    async def player_loop(self):
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            self.next.clear()
            
            # Nếu hàng đợi trống, thoát
            if not self.queue:
                await asyncio.sleep(1)
                continue
            
            # Lấy bài hát tiếp theo từ hàng đợi
            song_info = self.queue.pop(0)
            
            try:
                source = await YTDLSource.from_url(song_info['url'], loop=self.bot.loop, stream=True, requester=song_info['requester'])
                source.volume = self.volume
                
                voice_client = self.ctx.voice_client
                if not voice_client:
                    logger.error("Không có kết nối voice!")
                    continue
                
                # Lưu thông tin bài hát hiện tại
                self.current = source
                
                # Thông báo bài hát đang phát
                embed = discord.Embed(
                    title="Đang Phát",
                    description=f"**{source.title}**",
                    color=discord.Color.blue()
                )
                
                if source.thumbnail:
                    embed.set_thumbnail(url=source.thumbnail)
                
                embed.add_field(name="Thời lượng", value=self._format_duration(source.duration), inline=True)
                embed.add_field(name="Yêu cầu bởi", value=song_info['requester'], inline=True)
                
                await self.channel.send(embed=embed)
                
                # Phát nhạc
                voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
                
                # Đợi cho đến khi bài hát kết thúc
                await self.next.wait()
                
                # Xóa bài hát hiện tại
                self.current = None
                
            except Exception as e:
                logger.error(f"Lỗi khi phát nhạc: {e}")
                await self.channel.send(f"Lỗi khi phát bài hát: {e}")
                continue
    
    def _format_duration(self, seconds):
        if not seconds:
            return "N/A"
        minutes, seconds = divmod(int(seconds), 60)
        return f"{minutes}:{seconds:02d}"

@bot.hybrid_command(name="play", description="Phát nhạc từ YouTube hoặc URL")
async def play(ctx, *, query: str):
    if not ctx.author.voice:
        return await ctx.send("Bạn cần ở trong kênh thoại!")
    
    # Tham gia kênh thoại nếu chưa
    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()
    
    voice_client = ctx.voice_client
    
    # Thêm vào hàng đợi
    async with ctx.typing():
        try:
            # Kiểm tra xem query có phải URL không
            if not query.startswith(('http://', 'https://')):
                search_query = f"ytsearch:{query}"
            else:
                search_query = query
            
            # Lấy thông tin bài hát
            logger.info(f"Tìm kiếm: {search_query}")
            info = await bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search_query, download=False))
            
            if 'entries' in info:
                # Lấy mục đầu tiên từ danh sách kết quả tìm kiếm
                info = info['entries'][0]
            
            # Lưu thông tin bài hát
            song_info = {
                'title': info['title'],
                'url': info['webpage_url'] if 'webpage_url' in info else info['url'],
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration'),
                'requester': ctx.author.name
            }
            
            # Khởi tạo player nếu chưa có
            if not hasattr(bot, 'music_players'):
                bot.music_players = {}
            
            if ctx.guild.id not in bot.music_players:
                bot.music_players[ctx.guild.id] = MusicPlayer(ctx)
            
            player = bot.music_players[ctx.guild.id]
            
            # Thêm vào hàng đợi
            player.queue.append(song_info)
            
            # Thông báo
            embed = discord.Embed(
                title="Đã Thêm Vào Hàng Đợi",
                description=f"**{info['title']}** đã được thêm vào hàng đợi!",
                color=discord.Color.blue()
            )
            
            if info.get('thumbnail'):
                embed.set_thumbnail(url=info['thumbnail'])
            
            embed.add_field(name="Vị trí", value=str(len(player.queue)), inline=True)
            embed.add_field(name="Yêu cầu bởi", value=ctx.author.name, inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Lỗi khi tìm kiếm: {e}")
            await ctx.send(f"Không thể phát bài hát: {e}")

@bot.hybrid_command(name="skip", description="Bỏ qua bài hát hiện tại")
async def skip(ctx):
    if not ctx.voice_client:
        return await ctx.send("Bot không ở trong kênh thoại!")
    
    if not ctx.voice_client.is_playing():
        return await ctx.send("Bot không đang phát nhạc!")
    
    ctx.voice_client.stop()
    await ctx.send("Đã bỏ qua bài hát hiện tại ⏭️")

@bot.hybrid_command(name="queue", description="Hiển thị danh sách phát nhạc")
async def queue(ctx):
    if not hasattr(bot, 'music_players') or ctx.guild.id not in bot.music_players:
        return await ctx.send("Không có hàng đợi nhạc nào!")
    
    player = bot.music_players[ctx.guild.id]
    
    if not player.queue and not player.current:
        return await ctx.send("Hàng đợi trống!")
    
    embed = discord.Embed(
        title="Hàng Đợi Nhạc",
        color=discord.Color.blue()
    )
    
    description = ""
    
    if player.current:
        description += f"**Đang Phát:** {player.current.title}\n\n"
    
    description += "**Tiếp Theo:**\n"
    
    if not player.queue:
        description += "Không có gì trong hàng đợi!"
    else:
        for i, song in enumerate(player.queue[:10], 1):
            description += f"{i}. {song['title']}\n"
        
        if len(player.queue) > 10:
            description += f"\nVà {len(player.queue) - 10} bài hát khác..."
    
    embed.description = description
    await ctx.send(embed=embed)

@bot.hybrid_command(name="stop", description="Dừng phát nhạc và rời khỏi kênh thoại")
async def stop(ctx):
    if not ctx.voice_client:
        return await ctx.send("Bot không ở trong kênh thoại!")
    
    if hasattr(bot, 'music_players') and ctx.guild.id in bot.music_players:
        del bot.music_players[ctx.guild.id]
    
    await ctx.voice_client.disconnect()
    await ctx.send("Đã dừng phát và rời khỏi kênh thoại!")

@bot.hybrid_command(name="pause", description="Tạm dừng bài hát")
async def pause(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        return await ctx.send("Bot không đang phát nhạc!")
    
    ctx.voice_client.pause()
    await ctx.send("Đã tạm dừng nhạc ⏸️")

@bot.hybrid_command(name="resume", description="Tiếp tục phát nhạc")
async def resume(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_paused():
        return await ctx.send("Bot không đang tạm dừng!")
    
    ctx.voice_client.resume()
    await ctx.send("Tiếp tục phát nhạc ▶️")

@bot.hybrid_command(name="ping", description="Kiểm tra bot có hoạt động không")
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"Pong! 🏓 Độ trễ: {latency}ms")

# Chạy bot
try:
    bot.run(config['token'])
except Exception as e:
    logger.error(f"Lỗi khi khởi động bot: {e}")
    print(f"Không thể khởi động bot. Lỗi: {e}")