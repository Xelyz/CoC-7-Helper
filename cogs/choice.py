import re
import random
import logging
import discord
from discord import app_commands
from discord.ext import commands


logger = logging.getLogger(__name__)


class Choice(commands.Cog):
    """从给定列表中随机选取若干元素：/choice items, num."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="choice", description="Randomly pick N items from a list")
    @app_commands.describe(
        items="Items separated by commas (e.g., a,b,c)",
        num="Number of items to pick (default 1)",
    )
    async def choice(self, interaction: discord.Interaction, items: str, num: int = 1) -> None:
        """解析字符串列表并随机选取 num 个元素。

        - 支持分隔符：逗号/分号/竖线/中文逗号/顿号（不支持换行）
        - 限制：1 <= num <= 1000 且 num 不可超过项目数
        - 输出裁剪：超过 50 个仅展示前 50 个
        """
        await interaction.response.defer(ephemeral=False)

        # 解析输入字符串为列表
        # 包含：, ; | ， 、 多个连续分隔符视为一个；不支持换行
        parts = [p.strip() for p in re.split(r"[\,;\|，、]+", items or "")]
        pool = [p for p in parts if p]

        if not pool:
            await interaction.followup.send("No items provided. Please separate items by commas.", ephemeral=True)
            return

        # 合理范围限制，避免滥用
        if not (1 <= num <= 1000):
            await interaction.followup.send("Out of range: require 1 <= num <= 1000.", ephemeral=True)
            return

        if num > len(pool):
            await interaction.followup.send(
                f"num ({num}) cannot be greater than the number of items ({len(pool)}).",
                ephemeral=True,
            )
            return

        selected = random.sample(pool, k=num)

        # 原始数组与结果的裁剪显示
        orig_detail = ", ".join(pool[:50])
        orig_suffix = "" if len(pool) <= 50 else f" (showing first 50 of {len(pool)} items)"

        if num <= 50:
            res_detail = ", ".join(selected)
            res_suffix = ""
        else:
            res_detail = ", ".join(selected[:50])
            res_suffix = f" (showing first 50 of {num} picks)"

        await interaction.followup.send(
            f"From [{orig_detail}]{orig_suffix}, pick {num} -> [{res_detail}]{res_suffix}"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Choice(bot))
    logger.info("Cog 'Choice' loaded")


