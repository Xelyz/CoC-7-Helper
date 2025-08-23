import os
import logging

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


def owner_or_admin(owner_env_var: str = "DISCORD_OWNER_ID") -> app_commands.check:
    """Slash 命令装饰器：允许指定 Owner 或服务器管理员使用。

    - 若设置了环境变量 `DISCORD_OWNER_ID`，则该用户恒通过；
    - 否则回退到检测调用者是否具备管理员权限。
    """

    def predicate(interaction: discord.Interaction) -> bool:
        user = interaction.user
        if user is None:
            return False

        owner_id = os.getenv(owner_env_var)
        if owner_id:
            try:
                if int(owner_id) == user.id:
                    return True
            except ValueError:
                logger.warning("Invalid %s, fallback to administrator permission", owner_env_var)

        # 回退：检查是否管理员
        if isinstance(user, discord.Member):
            perms = user.guild_permissions
            return bool(perms.administrator)
        return False

    return app_commands.check(predicate)


async def sync_app_commands(bot: "commands.Bot") -> tuple[str, int]:
    """同步应用命令。

    - 若设置 `DISCORD_GUILD_ID`：仅同步到该服务器（开发/测试推荐）
    - 否则：执行全局同步（传播较慢）

    返回 (scope, count)，scope 为 'guild' 或 'global'。
    """
    try:
        import discord as _discord
        from discord.ext import commands as _commands
    except Exception:  # 安全兜底
        return ("unknown", 0)

    guild_id_str = os.getenv("DISCORD_GUILD_ID")
    if guild_id_str:
        try:
            guild_id = int(guild_id_str)
        except ValueError:
            logger.warning("DISCORD_GUILD_ID is not a valid integer. Falling back to global sync.")
            guild_id = None
    else:
        guild_id = None

    try:
        if guild_id:
            guild_obj = _discord.Object(id=guild_id)
            bot.tree.copy_global_to(guild=guild_obj)
            synced = await bot.tree.sync(guild=guild_obj)
            return ("guild", len(synced))
        synced = await bot.tree.sync()
        return ("global", len(synced))
    except Exception as exc:  # 保持健壮性
        logger.exception("App command sync failed: %s", exc)
        return ("error", 0)


