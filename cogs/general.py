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

    @app_commands.command(name="help", description="Show all available commands")
    async def help_slash(self, interaction: discord.Interaction) -> None:
        """显示所有可用的命令列表。"""
        # 构建帮助消息
        help_embed = discord.Embed(
            title="📖 Command Help",
            description="Here are all available commands. Use `/` for slash commands and `.` prefix for text commands.",
            color=discord.Color.blue()
        )

        # 通用命令
        help_embed.add_field(
            name="🔧 General Commands",
            value=(
                "`/ping` or `.ping` - Check bot latency\n"
                "`/help` or `.help` - Show this help message"
            ),
            inline=False
        )

        # 掷骰命令
        help_embed.add_field(
            name="🎲 Dice Rolling",
            value=(
                "`/roll <expr>` or `.roll <expr>` - Roll dice (e.g., 2d6, d20, (2d6+6)*5)\n"
                "`/secret <expr>` or `.secret <expr>` - Secret roll (DM result to you)\n"
                "`/flip [coins]` or `.flip [coins]` - Flip coins (default 1)"
            ),
            inline=False
        )

        # CoC 检定命令
        help_embed.add_field(
            name="🎭 CoC Checks",
            value=(
                "`/check <number|attr>` or `.check <number|attr>` - CoC d100 check\n"
                "`/sc <succ/fail>` or `.sc <succ/fail>` - Sanity check (e.g., 1d3/1d10)\n"
                "`/growth <number|attr>` or `.growth <number|attr>` - Growth check\n"
                "`/ti` or `.ti` - Temporary insanity effect"
            ),
            inline=False
        )

        # 角色管理
        help_embed.add_field(
            name="👤 Character Management",
            value=(
                "`/stats` or `.stats [@user]` - Show character attributes\n"
                "`/set <items>` or `.set [@user] <items>` - Set attributes (e.g., STR 60, DEX 50)\n"
                "`/add <items>` or `.add [@user] <items>` - Add to attributes (e.g., HP -5)\n"
                "`/remove <items>` or `.remove <items>` - Remove attributes\n"
                "`/reset` or `.reset` - Reset all attributes\n"
                "`/cs` or `.cs` - Generate CoC7 character stats\n"
                "`/nn <name>` or `.nn <name>` - Set display name (use 'clear' to remove)\n"
                "`/kp` or `.kp` - Register as KP (Keeper)"
            ),
            inline=False
        )

        # 提示信息
        help_embed.set_footer(text="Tip: Many text commands support @user to perform actions on other players")

        await interaction.response.send_message(embed=help_embed, ephemeral=True)

    # 文本命令：`.r ping`
    @commands.command(name="ping", help="Return bot latency (ms). Usage: .r ping")
    async def ping_text(self, ctx: commands.Context) -> None:
        latency_ms = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! {latency_ms}ms")

    # 文本命令：`.help`
    @commands.command(name="help", help="Show all available commands. Usage: .help")
    async def help_text(self, ctx: commands.Context) -> None:
        """显示所有可用的命令列表。"""
        # 构建帮助消息
        help_embed = discord.Embed(
            title="📖 Command Help",
            description="Here are all available commands. Use `/` for slash commands and `.` prefix for text commands.",
            color=discord.Color.blue()
        )

        # 通用命令
        help_embed.add_field(
            name="🔧 General Commands",
            value=(
                "`/ping` or `.ping` - Check bot latency\n"
                "`/help` or `.help` - Show this help message"
            ),
            inline=False
        )

        # 掷骰命令
        help_embed.add_field(
            name="🎲 Dice Rolling",
            value=(
                "`/roll <expr>` or `.roll <expr>` - Roll dice (e.g., 2d6, d20, (2d6+6)*5)\n"
                "`/secret <expr>` or `.secret <expr>` - Secret roll (DM result to you)\n"
                "`/flip [coins]` or `.flip [coins]` - Flip coins (default 1)"
            ),
            inline=False
        )

        # CoC 检定命令
        help_embed.add_field(
            name="🎭 CoC Checks",
            value=(
                "`/check <number|attr>` or `.check <number|attr>` - CoC d100 check\n"
                "`/sc <succ/fail>` or `.sc <succ/fail>` - Sanity check (e.g., 1d3/1d10)\n"
                "`/growth <number|attr>` or `.growth <number|attr>` - Growth check\n"
                "`/ti` or `.ti` - Temporary insanity effect"
            ),
            inline=False
        )

        # 角色管理
        help_embed.add_field(
            name="👤 Character Management",
            value=(
                "`/stats` or `.stats [@user]` - Show character attributes\n"
                "`/set <items>` or `.set [@user] <items>` - Set attributes (e.g., STR 60, DEX 50)\n"
                "`/add <items>` or `.add [@user] <items>` - Add to attributes (e.g., HP -5)\n"
                "`/remove <items>` or `.remove <items>` - Remove attributes\n"
                "`/reset` or `.reset` - Reset all attributes\n"
                "`/cs` or `.cs` - Generate CoC7 character stats\n"
                "`/nn <name>` or `.nn <name>` - Set display name (use 'clear' to remove)\n"
                "`/kp` or `.kp` - Register as KP (Keeper)"
            ),
            inline=False
        )

        # 提示信息
        help_embed.set_footer(text="Tip: Many text commands support @user to perform actions on other players")

        await ctx.send(embed=help_embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
    logger.info("Cog 'General' loaded")


