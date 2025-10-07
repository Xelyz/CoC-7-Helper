import logging
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


class General(commands.Cog):
    """通用示例：仅 Slash 命令。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Return bot latency (ms)")
    async def ping_slash(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! {latency_ms}ms", ephemeral=True)

    # 文本命令：`.r ping`
    @commands.command(name="ping", help="Return bot latency (ms). Usage: .r ping")
    async def ping_text(self, ctx: commands.Context) -> None:
        latency_ms = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! {latency_ms}ms")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
    logger.info("Cog 'General' loaded")


