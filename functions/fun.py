import discord
from discord.ext import commands
import random

gay_levels = [
    (0, 10, "hơi ít nhưng vẫn gay"),
    (11, 20, "hơi ít nhưng vẫn gay"),
    (21, 30, "MMB for real"),
    (31, 40, "Gay nhiều hơn rồi đấy"),
    (41, 50, "Gay Gay"),
    (51, 60, "bạn có thể dootdeet Taiki"),
    (61, 70, "bạn có thể dootdeet Hieu"),
    (71, 80, "gay vai lon"),
    (81, 90, "nếu bạn xài iphone, chắc chắn bạn là gay real"),
    (91, 100, "biểu tượng của cộng đồng gay!")
]

gay_images = [
    "https://i.imgur.com/VdZYC7W.jpeg",  
    "https://i.imgur.com/NKnbUrA.jpeg",
    "https://i.imgur.com/ojZq8kb.jpeg",
    "https://i.imgur.com/BvGxO8s.jpeg",
    "https://i.imgur.com/3Xc5EiZ.jpeg",
    "https://i.imgur.com/ESw1YLm.jpeg",
    "https://i.imgur.com/c1eOhuG.jpeg",
    "https://i.imgur.com/DDRwmIR.jpeg",  
    "https://i.imgur.com/TA6WogZ.jpeg"   
]

class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.hybrid_command(
        name="isgay",
        description="Check your fucking GAYYYYYY"
    )
    async def compatibility(self, ctx, name: discord.Member):
        percentage = random.randint(0, 100)
        
        for min_val, max_val, description in gay_levels:
            if min_val <= percentage <= max_val:
                gay_description = description
                break
                
        embed = discord.Embed(
            title=f"Gay Meter: {name}",
            description=f"{name.mention} has a gay meter of {percentage}%** \n{gay_description}",
            color=discord.Color.purple()
        )
        
        if gay_images:
            embed.set_image(url=random.choice(gay_images))
            
        progress_bar = "▓" * (percentage // 10) + "░" * (10 - (percentage // 10))
        embed.add_field(name="GAYYY", value=f"[{progress_bar}] {percentage}%", inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(FunCog(bot))