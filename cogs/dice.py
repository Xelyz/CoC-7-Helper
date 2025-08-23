import re
import random
import logging
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


class Dice(commands.Cog):
    """掷骰子相关命令：/dice 输入 NdM 或 dM。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="dice", description="Roll dice: NdM or dM (e.g., 2d6, d20)")
    async def dice(self, interaction: discord.Interaction, expr: str) -> None:
        """根据表达式 NdM 掷骰子并返回结果。"""
        # 为避免网络/计算延迟导致 Unknown interaction，统一先延迟响应
        await interaction.response.defer(ephemeral=False)
        text = expr.strip()
        m = re.match(r"^\s*(\d*)\s*d\s*(\d+)\s*$", text, re.IGNORECASE)
        if not m:
            await interaction.followup.send("Invalid format. Use NdM or dM, e.g., 2d6 or d20.", ephemeral=True)
            return

        count_str, sides_str = m.group(1), m.group(2)
        count = int(count_str) if count_str else 1
        sides = int(sides_str)

        # 合理范围限制，避免滥用
        if not (1 <= count <= 100 and 2 <= sides <= 1000):
            await interaction.followup.send("Out of range: require 1 <= N <= 100 and 2 <= M <= 1000.", ephemeral=True)
            return

        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)

        # 输出裁剪，避免消息过长
        preview = rolls if len(rolls) <= 50 else (rolls[:50] + ["..."])
        detail = ", ".join(map(str, preview))
        suffix = "" if len(rolls) <= 50 else f" (showing first 50 of {len(rolls)} rolls)"

        await interaction.followup.send(f"Roll: {count}d{sides} -> [{detail}] = {total}{suffix}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Dice(bot))
    logger.info("Cog 'Dice' loaded")


