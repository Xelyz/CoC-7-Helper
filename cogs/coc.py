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

    # ---------------- Helpers (private) ----------------
    def _parse_expr(self, expr: str) -> tuple[int, int] | None:
        text = (expr or "").strip()
        m = re.match(r"^\s*(\d*)\s*d\s*(\d+)\s*$", text, re.IGNORECASE)
        if not m:
            return None
        count_str, sides_str = m.group(1), m.group(2)
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
        return (count, sides)

    def _validate_bounds(self, count: int, sides: int) -> bool:
        return 1 <= count <= 100 and 2 <= sides <= 1000

    def _roll(self, count: int, sides: int) -> tuple[list[int], int, str, str]:
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        preview = rolls if len(rolls) <= 50 else (rolls[:50] + ["..."])
        detail = ", ".join(map(str, preview))
        suffix = "" if len(rolls) <= 50 else f" (showing first 50 of {len(rolls)} rolls)"
        return (rolls, total, detail, suffix)

    @app_commands.command(name="dice", description="Roll dice: NdM or dM (e.g., 2d6, d20)")
    async def dice(self, interaction: discord.Interaction, expr: str) -> None:
        """根据表达式 NdM 掷骰子并返回结果。"""
        # 为避免网络/计算延迟导致 Unknown interaction，统一先延迟响应
        await interaction.response.defer(ephemeral=False)
        parsed = self._parse_expr(expr)
        if not parsed:
            await interaction.followup.send("Invalid format. Use NdM or dM, e.g., 2d6 or d20.", ephemeral=True)
            return
        count, sides = parsed

        # 合理范围限制，避免滥用
        if not self._validate_bounds(count, sides):
            await interaction.followup.send("Out of range: require 1 <= N <= 100 and 2 <= M <= 1000.", ephemeral=True)
            return
        _rolls, total, detail, suffix = self._roll(count, sides)
        await interaction.followup.send(f"Roll: {count}d{sides} -> [{detail}] = {total}{suffix}")


    @app_commands.command(name="d6", description="Roll d6 N times (default 1)")
    @app_commands.describe(num="Number of d6 rolls (default 1)")
    async def d6(self, interaction: discord.Interaction, num: int = 1) -> None:
        """快捷掷 d6：num 可选，0 视为 1。"""
        await interaction.response.defer(ephemeral=False)

        count = num if num > 0 else 1
        sides = 6

        if not (1 <= count <= 100):
            await interaction.followup.send(
                "Out of range: require 1 <= num <= 100.", ephemeral=True
            )
            return

        _rolls, total, detail, suffix = self._roll(count, sides)

        await interaction.followup.send(
            f"Roll: {count}d{sides} -> [{detail}] = {total}{suffix}"
        )


    @app_commands.command(name="d20", description="Roll d20 N times (default 1)")
    @app_commands.describe(num="Number of d20 rolls (default 1)")
    async def d20(self, interaction: discord.Interaction, num: int = 1) -> None:
        """快捷掷 d20：num 可选，0 视为 1。"""
        await interaction.response.defer(ephemeral=False)

        count = num if num > 0 else 1
        sides = 20

        if not (1 <= count <= 100):
            await interaction.followup.send(
                "Out of range: require 1 <= num <= 100.", ephemeral=True
            )
            return

        _rolls, total, detail, suffix = self._roll(count, sides)

        await interaction.followup.send(
            f"Roll: {count}d{sides} -> [{detail}] = {total}{suffix}"
        )

    # 文本命令：`.r dice 2d6` 或 `.r dice d20`
    @commands.command(name="dice", help="Roll dice: NdM or dM. Usage: .r dice 2d6")
    async def dice_text(self, ctx: commands.Context, *, expr: str) -> None:
        parsed = self._parse_expr(expr)
        if not parsed:
            await ctx.send("Invalid format. Use NdM or dM, e.g., 2d6 or d20.")
            return
        count, sides = parsed

        if not self._validate_bounds(count, sides):
            await ctx.send("Out of range: require 1 <= N <= 100 and 2 <= M <= 1000.")
            return
        _rolls, total, detail, suffix = self._roll(count, sides)
        await ctx.send(f"Roll: {count}d{sides} -> [{detail}] = {total}{suffix}")

    # 文本命令：`.r d6 3`
    @commands.command(name="d6", help="Roll d6 N times (default 1). Usage: .r d6 [num]")
    async def d6_text(self, ctx: commands.Context, num: int = 1) -> None:
        count = num if num > 0 else 1
        sides = 6
        if not (1 <= count <= 100):
            await ctx.send("Out of range: require 1 <= num <= 100.")
            return
        _rolls, total, detail, suffix = self._roll(count, sides)
        await ctx.send(f"Roll: {count}d{sides} -> [{detail}] = {total}{suffix}")

    # 文本命令：`.r d20 3`
    @commands.command(name="d20", help="Roll d20 N times (default 1). Usage: .r d20 [num]")
    async def d20_text(self, ctx: commands.Context, num: int = 1) -> None:
        count = num if num > 0 else 1
        sides = 20
        if not (1 <= count <= 100):
            await ctx.send("Out of range: require 1 <= num <= 100.")
            return
        _rolls, total, detail, suffix = self._roll(count, sides)
        await ctx.send(f"Roll: {count}d{sides} -> [{detail}] = {total}{suffix}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Dice(bot))
    logger.info("Cog 'Dice' loaded")


