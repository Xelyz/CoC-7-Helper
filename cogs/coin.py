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

    @app_commands.command(name="flip", description="Flip N coins and show results")
    async def flip(self, interaction: discord.Interaction, coins: int) -> None:
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
        results = ["H" if random.getrandbits(1) else "T" for _ in range(coins)]
        heads = results.count("H")
        tails = coins - heads

        # 输出裁剪，避免消息过长
        if coins <= 50:
            detail = ", ".join(results)
            suffix = ""
        else:
            preview = ", ".join(results[:50])
            suffix = f" (showing first 50 of {coins} flips)"
            detail = preview

        await interaction.followup.send(
            f"Flip {coins}: [{detail}] -> Heads={heads}, Tails={tails}{suffix}"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Coin(bot))
    logger.info("Cog 'Coin' loaded")


