import random
import logging
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


class Coin(commands.Cog):
    """抛硬币：/flip coins，返回每次结果与统计。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ---------------- Helpers (private) ----------------
    def _flip_n(self, coins: int) -> tuple[list[str], int, int, str, str]:
        results = ["H" if random.getrandbits(1) else "T" for _ in range(coins)]
        heads = results.count("H")
        tails = coins - heads
        if coins <= 50:
            detail = ", ".join(results)
            suffix = ""
        else:
            preview = ", ".join(results[:50])
            suffix = f" (showing first 50 of {coins} flips)"
            detail = preview
        return (results, heads, tails, detail, suffix)

    @app_commands.command(name="flip", description="Flip N coins (default 1) and show results")
    async def flip(self, interaction: discord.Interaction, coins: int = 1) -> None:
        """抛掷指定数量的硬币。

        - coins 范围限制，避免滥用
        - 小数量展示完整序列；数量大时仅预览前 50 次并给出统计
        """
        await interaction.response.defer(ephemeral=False)
        if not (1 <= coins <= 1000):
            await interaction.followup.send(
                "Out of range: require 1 <= coins <= 1000.", ephemeral=True
            )
            return

        # 使用 getrandbits 更快地产生二元结果
        _results, heads, tails, detail, suffix = self._flip_n(coins)
        await interaction.followup.send(f"Flip {coins}: [{detail}] -> Heads={heads}, Tails={tails}{suffix}")

    # 文本命令：`.r flip 10`
    @commands.command(name="flip", help="Flip N coins (default 1). Usage: .r flip [coins]")
    async def flip_text(self, ctx: commands.Context, coins: int = 1) -> None:
        if not (1 <= coins <= 1000):
            await ctx.send("Out of range: require 1 <= coins <= 1000.")
            return

        _results, heads, tails, detail, suffix = self._flip_n(coins)
        await ctx.send(f"Flip {coins}: [{detail}] -> Heads={heads}, Tails={tails}{suffix}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Coin(bot))
    logger.info("Cog 'Coin' loaded")


