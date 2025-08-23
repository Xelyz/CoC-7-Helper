import os
import logging
import discord
from typing import Iterable

# 推荐使用 discord.ext.commands 来创建命令
from discord.ext import commands


# ------------------------------
# Logging (English-only per user rule)
# ------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("bot")


# ------------------------------
# Intents & Bot 设置（仅 Slash，无前缀）
# ------------------------------
intents = discord.Intents.default()
intents.message_content = False  # 不读取消息内容（仅 Slash）


class RngHelperBot(commands.Bot):
    def __init__(self) -> None:
        # 仅 Slash：使用提及触发占位前缀，移除默认帮助命令
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)

    async def setup_hook(self) -> None:
        """启动前：加载 Cogs 并同步应用命令。"""
        await self._load_all_extensions("cogs")

        # 优先同步到单一测试服，加速开发；否则进行全局同步
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
                guild_obj = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild_obj)
                synced = await self.tree.sync(guild=guild_obj)
                logger.info("Synced %d app commands to guild %s", len(synced), guild_id)
            else:
                # 首次启动进行一次全局同步，后续变更由管理命令/热重载触发
                synced = await self.tree.sync()
                logger.info("Globally synced %d app commands", len(synced))
        except Exception as exc:
            logger.exception("App command sync failed: %s", exc)

    async def _load_all_extensions(self, base_package: str) -> None:
        """Recursively discover and load all extensions from a base package.

        An extension is any .py file that does not start with an underscore.
        """
        for ext in self._iter_extension_module_paths(base_package):
            try:
                await self.load_extension(ext)
                logger.info("Loaded extension: %s", ext)
            except Exception as exc:
                logger.exception("Failed to load extension %s: %s", ext, exc)

    @staticmethod
    def _iter_extension_module_paths(base_package: str) -> Iterable[str]:
        """扫描包下所有可加载的扩展模块路径。"""
        base_dir = os.path.join(os.path.dirname(__file__), base_package.replace(".", os.sep))
        if not os.path.isdir(base_dir):
            return []
        module_paths = []
        for root, _dirs, files in os.walk(base_dir):
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                if filename.startswith("_"):
                    continue
                relative = os.path.relpath(os.path.join(root, filename[:-3]), base_dir)
                dotted = relative.replace(os.sep, ".")
                module_paths.append(f"{base_package}.{dotted}")
        return module_paths


bot = RngHelperBot()


@bot.event
async def on_ready():
    # 日志使用英文，便于检索
    if bot.user:
        logger.info("Logged in as %s (ID: %s)", bot.user.name, bot.user.id)
    logger.info("------")


# ------------------------------
# Entrypoint
# ------------------------------
def _require_token() -> str:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("Environment variable DISCORD_TOKEN is not set.")
        raise SystemExit(1)
    return token



if __name__ == "__main__":
    bot.run(_require_token())
