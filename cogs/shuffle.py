import re
import random
import logging
import discord
from discord import app_commands
from discord.ext import commands


logger = logging.getLogger(__name__)


class Shuffle(commands.Cog):
    """打乱给定列表：/shuffle items."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="shuffle", description="Shuffle the given list of items")
    @app_commands.describe(
        items="Items separated by commas (e.g., a,b,c)",
    )
    async def shuffle(self, interaction: discord.Interaction, items: str) -> None:
        """解析字符串列表并打乱顺序。

        - 支持分隔符：逗号/分号/竖线/中文逗号/顿号（不支持换行）
        - 限制：列表非空；最多 1000 个元素
        - 输出裁剪：超过 50 个仅展示前 50 个
        """
        await interaction.response.defer(ephemeral=False)

        parts = [p.strip() for p in re.split(r"[\,;\|，、]+", items or "")]
        pool = [p for p in parts if p]

        if not pool:
            await interaction.followup.send("No items provided. Please separate items by commas.", ephemeral=True)
            return

        if len(pool) > 1000:
            await interaction.followup.send(
                "Too many items. Maximum allowed is 1000.",
                ephemeral=True,
            )
            return

        shuffled = list(pool)
        random.shuffle(shuffled)

        # 原始数组与打乱结果的裁剪显示
        orig_detail = ", ".join(pool[:50])
        orig_suffix = "" if len(pool) <= 50 else f" (showing first 50 of {len(pool)} items)"

        if len(shuffled) <= 50:
            res_detail = ", ".join(shuffled)
            res_suffix = ""
        else:
            res_detail = ", ".join(shuffled[:50])
            res_suffix = f" (showing first 50 of {len(shuffled)} items)"

        await interaction.followup.send(
            f"From [{orig_detail}]{orig_suffix}, shuffled -> [{res_detail}]{res_suffix}"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Shuffle(bot))
    logger.info("Cog 'Shuffle' loaded")


