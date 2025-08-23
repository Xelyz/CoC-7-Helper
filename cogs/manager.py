import os
import logging
import asyncio
from pathlib import Path
from typing import Iterable, List

import discord
from discord import app_commands
from discord.ext import commands
from ._utils import owner_or_admin, sync_app_commands


logger = logging.getLogger(__name__)


def _iter_cog_module_paths(base_package: str = "cogs") -> List[str]:
    """Discover all extension module paths under a base package.

    Returns paths like 'cogs.general'.
    """
    package_dir = Path(__file__).resolve().parent if base_package == "cogs" else Path(__file__).resolve().parent / base_package
    if not package_dir.exists():
        return []
    modules: List[str] = []
    for path in package_dir.rglob("*.py"):
        if path.name.startswith("_"):
            continue
        rel = path.with_suffix("")
        try:
            rel = rel.relative_to(package_dir)
        except ValueError:
            # Should not happen, but keep safe
            continue
        dotted = str(rel).replace(os.sep, ".")
        modules.append(f"{base_package}.{dotted}")
    return sorted(modules)


class Manager(commands.Cog):
    """管理命令：以 /admin 作为命令组的入口。"""

    # 定义命令组：/admin
    admin = app_commands.Group(name="admin", description="Admin operations")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ---------------- Common helpers ----------------
    async def _choices(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        items = _iter_cog_module_paths("cogs")
        filtered = [m for m in items if current.lower() in m.lower()]
        return [app_commands.Choice(name=m, value=m) for m in filtered[:25]]

    async def _load_ext(self, interaction: discord.Interaction, ext: str) -> None:
        try:
            await self.bot.load_extension(ext)
            scope, count = await sync_app_commands(self.bot)
            await interaction.followup.send(f"Loaded: {ext} | synced {count} ({scope})", ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(f"Failed to load {ext}: {exc}", ephemeral=True)

    async def _unload_ext(self, interaction: discord.Interaction, ext: str) -> None:
        try:
            await self.bot.unload_extension(ext)
            scope, count = await sync_app_commands(self.bot)
            await interaction.followup.send(f"Unloaded: {ext} | synced {count} ({scope})", ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(f"Failed to unload {ext}: {exc}", ephemeral=True)

    async def _reload_ext(self, interaction: discord.Interaction, ext: str) -> None:
        try:
            await self.bot.reload_extension(ext)
            scope, count = await sync_app_commands(self.bot)
            await interaction.followup.send(f"Reloaded: {ext} | synced {count} ({scope})", ephemeral=True)
        except commands.ExtensionNotLoaded:
            try:
                await self.bot.load_extension(ext)
                scope, count = await sync_app_commands(self.bot)
                await interaction.followup.send(f"Loaded (was not loaded): {ext} | synced {count} ({scope})", ephemeral=True)
            except Exception as exc:
                await interaction.followup.send(f"Failed to load {ext}: {exc}", ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(f"Failed to reload {ext}: {exc}", ephemeral=True)

    # ---------------- /admin sub-commands ----------------
    @admin.command(name="load", description="Load an extension module")
    @app_commands.autocomplete(ext=_choices)
    @owner_or_admin()
    async def admin_load(self, interaction: discord.Interaction, ext: str) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._load_ext(interaction, ext)

    @admin.command(name="unload", description="Unload an extension module")
    @app_commands.autocomplete(ext=_choices)
    @owner_or_admin()
    async def admin_unload(self, interaction: discord.Interaction, ext: str) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._unload_ext(interaction, ext)

    @admin.command(name="reload", description="Reload an extension or all (pass 'all')")
    @app_commands.autocomplete(ext=_choices)
    @owner_or_admin()
    async def admin_reload(self, interaction: discord.Interaction, ext: str) -> None:
        await interaction.response.defer(ephemeral=True)
        if ext.lower() == "all":
            count = 0
            for mod in _iter_cog_module_paths("cogs"):
                try:
                    await self.bot.reload_extension(mod)
                    count += 1
                except commands.ExtensionNotLoaded:
                    try:
                        await self.bot.load_extension(mod)
                        count += 1
                    except Exception:
                        logger.exception("Load failed for %s", mod)
                except Exception:
                    logger.exception("Reload failed for %s", mod)
            scope, sync_count = await sync_app_commands(self.bot)
            await interaction.followup.send(f"Reloaded all. OK: {count} | synced {sync_count} ({scope})", ephemeral=True)
            return
        await self._reload_ext(interaction, ext)

    @admin.command(name="sync", description="Sync app commands (global/guild/clear_global/clear_guild)")
    @owner_or_admin()
    async def admin_sync(self, interaction: discord.Interaction, scope: str = "global") -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            scope = scope.lower().strip()
            if scope == "guild" and interaction.guild:
                self.bot.tree.copy_global_to(guild=interaction.guild)
                synced = await self.bot.tree.sync(guild=interaction.guild)
                await interaction.followup.send(
                    f"Synced {len(synced)} commands to guild {interaction.guild.id}", ephemeral=True
                )
                return

            if scope == "clear_global":
                self.bot.tree.clear_commands(guild=None)
                synced = await self.bot.tree.sync()
                await interaction.followup.send(
                    f"Cleared global commands. Remaining: {len(synced)}", ephemeral=True
                )
                return

            if scope == "clear_guild" and interaction.guild:
                self.bot.tree.clear_commands(guild=interaction.guild)
                synced = await self.bot.tree.sync(guild=interaction.guild)
                await interaction.followup.send(
                    f"Cleared guild {interaction.guild.id} commands. Remaining: {len(synced)}", ephemeral=True
                )
                return

            # default: global or fallback to helper util
            s_scope, s_count = await sync_app_commands(self.bot)
            await interaction.followup.send(
                f"Synced {s_count} ({s_scope})", ephemeral=True
            )
        except Exception as exc:
            await interaction.followup.send(f"Sync failed: {exc}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Manager(bot))
    logger.info("Cog 'Manager' loaded")


