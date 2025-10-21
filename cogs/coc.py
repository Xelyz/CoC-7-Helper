import re
import random
import logging
import discord
from discord import app_commands
from discord.ext import commands
from texts.coc7_texts import TEMP_INSANITY_D10

logger = logging.getLogger(__name__)


class CoC(commands.Cog):
    """掷骰子相关命令：/roll 输入 NdM 或 dM。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # 频道级缓存：channel_id -> user_id -> attr_key -> {label, value}
        # 将缓存挂在 bot 上，确保扩展 reload 后仍复用同一份数据
        if not hasattr(self.bot, "_coc_channel_player_stats"):
            self.bot._coc_channel_player_stats = {}
        # 直接引用，不复制
        self._channel_player_stats = self.bot._coc_channel_player_stats  # type: ignore[attr-defined]
        
        # KP 缓存：channel_id -> user_id
        if not hasattr(self.bot, "_coc_channel_kp"):
            self.bot._coc_channel_kp = {}
        self._channel_kp = self.bot._coc_channel_kp  # type: ignore[attr-defined]

    # ---------------- Helpers (private) ----------------
    def _get_display_name(self, channel_id: int, user: discord.Member | discord.User) -> str:
        """统一获取用户显示名：优先使用 .nn 设置的 NAME，否则使用 Discord 显示名。
        
        对于 KP，显示为 "KP" 或 "KP(名字)"。
        返回用户的显示名称。
        """
        # 检查是否是 KP
        is_kp = self._channel_kp.get(channel_id) == user.id
        
        # 尝试从属性中获取 NAME
        attrs = self._get_user_attrs(channel_id, user.id)
        name_key = self._normalize_attr_name("NAME")[0]
        name_meta = attrs.get(name_key)
        
        if name_meta is not None:
            custom_name = str(name_meta.get("value", "")).strip()
            if custom_name:
                # KP 显示为 "KP(名字)"
                if is_kp:
                    return f"KP({custom_name})"
                return custom_name
        
        # KP 没有设置 nn 时，显示为 "KP"
        if is_kp:
            return "KP"
        
        # 降级：使用 Discord 显示名
        if isinstance(user, discord.Member):
            return user.display_name
        return getattr(user, "name", "user")
    
    def _extract_mentions_and_clean_arg(self, ctx: commands.Context, arg: str) -> tuple[list[discord.Member | discord.User], str]:
        """从参数中提取被 @ 的用户，并返回清理后的参数字符串。
        
        返回 (目标用户列表, 清理后的参数)。
        如果没有 @，返回空列表和原参数。
        """
        mentions = ctx.message.mentions
        if not mentions:
            return [], arg
        
        # 移除所有 mention 标记，保留其他参数
        cleaned = arg
        for user in mentions:
            # Discord mention 格式：<@USER_ID> 或 <@!USER_ID>
            cleaned = re.sub(rf'<@!?{user.id}>', '', cleaned)
        
        cleaned = cleaned.strip()
        return mentions, cleaned

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

    def _roll_expression(self, expr: str) -> tuple[int, list[str]]:
        """解析并掷骰复杂表达式，例如："(2d6+6)*5"、"3d6*5+1d4-2"。

        返回 (总值, 细节列表)；细节列表包含每个骰子段的展开如 "2d6=[3,4]"。
        约束：1 <= N <= 100, 2 <= M <= 1000，避免滥用；仅支持 +, -, * 与括号。
        """
        s = (expr or "").replace(" ", "")
        if not s:
            raise ValueError("Empty expression")

        idx = 0
        details: list[str] = []

        def peek() -> str:
            return s[idx] if idx < len(s) else ""

        def consume(ch: str) -> bool:
            nonlocal idx
            if idx < len(s) and s[idx] == ch:
                idx += 1
                return True
            return False

        def parse_int() -> int:
            nonlocal idx
            start = idx
            if idx < len(s) and s[idx] in "+-":
                idx += 1
            while idx < len(s) and s[idx].isdigit():
                idx += 1
            if start == idx or s[start:idx] in {"+", "-"}:
                raise ValueError("Expected integer")
            return int(s[start:idx])

        def parse_factor() -> int:
            nonlocal idx
            # unary +/-
            if consume('+'):
                return parse_factor()
            if consume('-'):
                return -parse_factor()
            # parentheses
            if consume('('):
                val = parse_expr()
                if not consume(')'):
                    raise ValueError("Missing closing parenthesis")
                return val
            # dice or integer
            # pattern: [N]dM or integer
            save = idx
            # optional N
            n_sign = 1
            if peek() in '+-':
                n_sign = 1 if consume('+') else (-1 if consume('-') else 1)
            n_val = 0
            has_n = False
            while idx < len(s) and s[idx].isdigit():
                has_n = True
                n_val = n_val * 10 + int(s[idx])
                idx += 1
            if n_sign == -1:
                n_val = -n_val
            if idx < len(s) and s[idx].lower() == 'd':
                idx += 1
                # sides required
                if idx >= len(s) or (s[idx] in '+-*'):
                    raise ValueError("Missing sides after 'd'")
                # parse sides (no unary signs here)
                if not s[idx].isdigit():
                    raise ValueError("Invalid sides")
                sides = 0
                while idx < len(s) and s[idx].isdigit():
                    sides = sides * 10 + int(s[idx])
                    idx += 1
                count = n_val if has_n else 1
                if count <= 0:
                    raise ValueError("Dice count must be positive")
                if not (1 <= count <= 100 and 2 <= sides <= 1000):
                    raise ValueError("Out of range dice: require 1<=N<=100 and 2<=M<=1000")
                rolls = [random.randint(1, sides) for _ in range(count)]
                details.append(f"{count}d{sides}=[{', '.join(map(str, rolls))}]")
                return sum(rolls)
            # fallback: integer
            idx = save
            val = parse_int()
            return val

        def parse_term() -> int:
            val = parse_factor()
            while True:
                if consume('*'):
                    rhs = parse_factor()
                    val = val * rhs
                else:
                    break
            return val

        def parse_expr() -> int:
            val = parse_term()
            while True:
                if consume('+'):
                    val += parse_term()
                elif consume('-'):
                    val -= parse_term()
                else:
                    break
            return val

        value = parse_expr()
        if idx != len(s):
            raise ValueError("Unexpected trailing characters")
        return value, details

    # ---------------- CoC Check Helpers (private) ----------------
    def _coc_check(self, target: int) -> tuple[int, str]:
        """执行一次 CoC 判定并返回 (roll, 结果文本)。

        规则：
        - roll 一个 d100，返回 "roll/target" 并附带以下文本之一：
          - critical success：roll 在 1~5 且 roll <= target
          - extreme success：roll <= floor(target/5)
          - hard success：roll <= floor(target/2)
          - success：roll <= target
          - critical failure：roll 在 96~100 且 roll > target
          - failure：其它情况
        """
        roll = random.randint(1, 100)
        half = target // 2
        fifth = target // 5

        if roll <= target:
            if 1 <= roll <= 5:
                return roll, "critical success"
            if roll <= fifth:
                return roll, "extreme success"
            if roll <= half:
                return roll, "hard success"
            return roll, "success"

        # roll > target
        if 96 <= roll <= 100:
            return roll, "critical failure"
        return roll, "failure"

    # ---------------- Attribute Store Helpers (private) ----------------
    def _normalize_attr_name(self, name: str) -> tuple[str, str]:
        """标准化属性名作为键：去两端空白、压缩内部空白为单个空格并转小写。

        返回 (key, label)，label 为展示用。
        """
        compact = " ".join((name or "").strip().split())
        key = compact.lower()
        return key, compact

    def _get_user_attrs(self, channel_id: int, user_id: int) -> dict[str, dict[str, int | str]]:
        chan = self._channel_player_stats.setdefault(channel_id, {})
        return chan.setdefault(user_id, {})

    def _parse_set_items(self, items: str) -> list[tuple[str, int]]:
        """解析批量设置字符串：以逗号分隔的若干组 `名称 数值`。
        示例："STR 60, Dex 50, Move Rate 8"
        """
        if not items or not items.strip():
            return []
        parts = re.split(r"[，,]+", items)
        pairs: list[tuple[str, int]] = []
        for raw in parts:
            seg = raw.strip()
            if not seg:
                continue
            # 允许名称与数值之间无空格：如 "STR60" 或 "Move Rate60"
            m = re.match(r"^(.+?)\s*(-?\d+)\s*$", seg)
            if not m:
                raise ValueError(f"Invalid segment: '{seg}'. Use 'Name Value' pairs, separated by commas.")
            name = m.group(1)
            try:
                value = int(m.group(2))
            except ValueError:
                raise ValueError(f"Invalid number in segment: '{seg}'.")
            pairs.append((name, value))
        return pairs

    def _format_stats_lines(self, attrs: dict[str, dict[str, int | str]]) -> list[str]:
        if not attrs:
            return []
        # 保留插入顺序：不排序，直接按 dict 的迭代顺序输出
        lines: list[str] = []
        for _key, meta in attrs.items():
            label = str(meta.get("label", ""))
            raw_val = meta.get("value", "")
            # 显示时兼容字符串（如 NAME）与整数
            try:
                value_str = str(int(raw_val))
            except Exception:
                value_str = str(raw_val)
            lines.append(f"{label}: {value_str}")
        return lines

    def _format_stats_columns_block(self, attrs: dict[str, dict[str, int | str]], columns: int = 3) -> str:
        """将任意属性以多列代码块形式输出（列宽自适应）。"""
        if not attrs:
            return "``````"
        # 保留插入顺序，使用存储的 label 展示
        entries: list[str] = []
        for key, meta in attrs.items():
            label = str(meta.get('label', key))
            raw_val = meta.get('value', '')
            try:
                value_str = str(int(raw_val))
            except Exception:
                value_str = str(raw_val)
            entries.append(f"{label}: {value_str}")
        col_width = max(3, max(len(e) for e in entries))
        cols = max(1, columns)
        rows = (len(entries) + cols - 1) // cols
        lines: list[str] = []
        for r in range(rows):
            parts: list[str] = []
            for c in range(cols):
                idx = r + c * rows
                if idx >= len(entries):
                    continue
                cell = entries[idx]
                if c < cols - 1:
                    parts.append(cell.ljust(col_width + 2))
                else:
                    parts.append(cell)
            lines.append("".join(parts).rstrip())
        body = "\n".join(lines)
        return f"```\n{body}\n```"

    def _reset_user_attrs(self, channel_id: int, user_id: int) -> bool:
        """清除指定频道内指定用户的属性，返回是否存在并被清除。"""
        chan = self._channel_player_stats.get(channel_id)
        if not chan:
            return False
        existed = user_id in chan
        if existed:
            try:
                del chan[user_id]
            except KeyError:
                existed = False
        if not chan:
            # 频道下已无用户，移除频道
            try:
                del self._channel_player_stats[channel_id]
            except KeyError:
                pass
        return existed

    # ---------------- CoC7 Character Generation (private) ----------------

    def _generate_coc7_attributes(self) -> dict[str, int]:
        """按 CoC7 标准生成基础属性（含 LUCK）。"""
        return {
            "STR": self._roll_expression("3d6*5")[0],
            "CON": self._roll_expression("3d6*5")[0],
            "DEX": self._roll_expression("3d6*5")[0],
            "APP": self._roll_expression("3d6*5")[0],
            "POW": self._roll_expression("3d6*5")[0],
            "SIZ": self._roll_expression("(2d6+6)*5")[0],
            "INT": self._roll_expression("(2d6+6)*5")[0],
            "EDU": self._roll_expression("(2d6+6)*5")[0],
            "LUCK": self._roll_expression("3d6*5")[0],
        }

    def _format_coc7_attrs_block(self, rolled: dict[str, int]) -> str:
        """格式化 CoC7 属性为对齐的代码块文本，并附带总和（含/不含 LUCK）。"""
        order = ["STR", "CON", "DEX", "APP", "POW", "SIZ", "INT", "EDU", "LUCK"]
        items = [(k, rolled.get(k, 0)) for k in order]
        value_width = max(3, max((len(str(v)) for _k, v in items), default=3))
        lines: list[str] = []
        for k, v in items:
            lines.append(f"{k:<4} {v:>{value_width}}")
        total_wo_luck = sum(v for k, v in items if k != "LUCK")
        total_with_luck = total_wo_luck + rolled.get("LUCK", 0)
        sep_len = max(12, 6 + value_width)
        lines.append("-" * sep_len)
        lines.append(f"SUM (w/o LUCK): {total_wo_luck}")
        lines.append(f"SUM (with LUCK): {total_with_luck}")
        body = "\n".join(lines)
        return f"```\n{body}\n```"

    @app_commands.command(name="roll", description="Roll dice: NdM or dM (e.g., 2d6, d20)")
    async def roll(self, interaction: discord.Interaction, expr: str) -> None:
        """根据表达式掷骰并返回结果，支持 NdM 及复杂表达式(如 (2d6+6)*5)。"""
        # 为避免网络/计算延迟导致 Unknown interaction，统一先延迟响应
        await interaction.response.defer(ephemeral=False)
        expr = (expr or "").strip()
        if not expr:
            await interaction.followup.send("Missing parameter: expr.", ephemeral=True)
            return
        try:
            total, details = self._roll_expression(expr)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        extra = f" | {'; '.join(details)}" if details else ""
        await interaction.followup.send(f"Roll: {expr} -> {total}{extra}")

    @app_commands.command(name="secret", description="Secret roll: NdM or dM; DM result to you and hint in channel")
    async def secret_slash(self, interaction: discord.Interaction, expr: str) -> None:
        """与 roll 相同表达式规则，但将结果通过私聊发送给触发者，并在频道内提示一条神秘信息。"""
        await interaction.response.defer(ephemeral=False)
        expr = (expr or "").strip()
        if not expr:
            await interaction.followup.send("Missing parameter: expr.", ephemeral=True)
            return
        try:
            total, details = self._roll_expression(expr)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        extra = f" | {'; '.join(details)}" if details else ""
        # DM result to the user
        try:
            await interaction.user.send(f"Secret Roll: {expr} -> {total}{extra}")
        except Exception as exc:
            logger.warning("Failed to DM secret roll result: %s", exc)
            # 作为降级，给出仅自己可见的提示
            try:
                await interaction.followup.send("Could not DM you the result. Please enable DMs.", ephemeral=True)
            except Exception:
                pass
        # Post mysterious teaser in channel
        await interaction.followup.send("Shadows stir... A secret roll has been cast beyond the veil.")

    # ---------------- CoC Check Commands ----------------
    @app_commands.command(name="check", description="CoC d100 check by number or your attribute name")
    @app_commands.describe(arg="Positive integer (1-100) or your attribute name")
    async def coc_check(self, interaction: discord.Interaction, arg: str) -> None:
        await interaction.response.defer(ephemeral=False)
        arg = (arg or "").strip()
        if not arg:
            await interaction.followup.send("Missing parameter: arg.", ephemeral=True)
            return
        # number path
        m = re.match(r"^\s*(\d+)\s*$", arg or "")
        if m:
            target = int(m.group(1))
            if not (1 <= target <= 100):
                await interaction.followup.send("Out of range: require 1 <= target <= 100.", ephemeral=True)
                return
            roll, outcome = self._coc_check(target)
            await interaction.followup.send(f"{roll}/{target} -> {outcome}")
            return

        # attribute path (channel+user scoped)
        channel = interaction.channel
        user = interaction.user
        if channel is None or user is None:
            await interaction.followup.send("Channel or user not found.", ephemeral=True)
            return
        attrs = self._get_user_attrs(channel.id, user.id)
        key, _label_req = self._normalize_attr_name(arg)
        meta = attrs.get(key)
        if not meta:
            await interaction.followup.send("Attribute not found. Use /set or .set to define it.", ephemeral=True)
            return
        label = str(meta.get("label", arg))
        try:
            target = int(meta.get("value", 0))
        except Exception:
            await interaction.followup.send("Attribute value is invalid.", ephemeral=True)
            return
        target = max(1, min(100, target))  # clamp to [1,100]
        roll, outcome = self._coc_check(target)
        # 显示名：使用统一格式
        display_name = self._get_display_name(channel.id, user)
        await interaction.followup.send(f"[{label}] check of {display_name}:\n{roll}/{target} -> {outcome}")

    @app_commands.command(name="sc", description="Sanity check: input 'succ_expr/fail_expr'")
    @app_commands.describe(loss="Two dice expressions separated by '/', e.g., 1d3/1d10")
    async def sc_slash(self, interaction: discord.Interaction, loss: str) -> None:
        await interaction.response.defer(ephemeral=False)
        channel = interaction.channel
        user = interaction.user
        if channel is None or user is None:
            await interaction.followup.send("Channel or user not found.", ephemeral=True)
            return
        loss = (loss or "").strip()
        if not loss:
            await interaction.followup.send("Missing parameter: loss. Use 'succ_expr/fail_expr'.", ephemeral=True)
            return
        parts = (loss or "").split("/", 1)
        if len(parts) != 2:
            await interaction.followup.send("Invalid format. Use 'succ_expr/fail_expr'.", ephemeral=True)
            return
        succ_expr = parts[0].strip()
        fail_expr = parts[1].strip()
        if not succ_expr or not fail_expr:
            await interaction.followup.send("Invalid format. Both parts required: 'succ_expr/fail_expr'.", ephemeral=True)
            return

        attrs = self._get_user_attrs(channel.id, user.id)
        san_meta = attrs.get(self._normalize_attr_name("Sanity")[0])
        if not san_meta:
            await interaction.followup.send("Attribute 'Sanity' not found. Use /set to define it.", ephemeral=True)
            return
        try:
            san_val = int(san_meta.get("value", 0))
        except Exception:
            await interaction.followup.send("Attribute 'Sanity' value is invalid.", ephemeral=True)
            return
        target = max(1, min(100, san_val))

        roll = random.randint(1, 100)
        is_success = roll <= target
        chosen_expr = succ_expr if is_success else fail_expr
        try:
            loss_total, details = self._roll_expression(chosen_expr)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        new_san = max(0, san_val - max(0, loss_total))
        # 回写属性
        san_key, san_label = self._normalize_attr_name(str(san_meta.get("label", "Sanity")))
        attrs[san_key] = {"label": san_label, "value": int(new_san)}

        # 显示名：使用统一格式
        display_name = self._get_display_name(channel.id, user)

        outcome = "success" if is_success else "failure"
        extra = f" | {'; '.join(details)}" if details else ""
        ti_note = "\n[Temporary Insanity] Use /ti or .ti." if loss_total >= 5 else ""
        await interaction.followup.send(
            f"Sanity Check of {display_name}:\n"
            f"SC {roll}/{target} [{san_label}] -> {outcome} | loss: {chosen_expr} -> {loss_total}{extra} | Sanity: {san_val} -> {new_san}{ti_note}"
        )

    @app_commands.command(name="growth", description="Growth check: input number (1-100) or your attribute name")
    @app_commands.describe(arg="Positive integer (1-100) or your attribute name")
    async def growth_slash(self, interaction: discord.Interaction, arg: str) -> None:
        await interaction.response.defer(ephemeral=False)
        arg = (arg or "").strip()
        if not arg:
            await interaction.followup.send("Missing parameter: arg.", ephemeral=True)
            return
        # number path
        m = re.match(r"^\s*(\d+)\s*$", arg or "")
        if m:
            target = int(m.group(1))
            if not (1 <= target <= 100):
                await interaction.followup.send("Out of range: require 1 <= target <= 100.", ephemeral=True)
                return
            roll, outcome = self._coc_check(target)
            is_success = outcome in {"critical success", "extreme success", "hard success", "success"}
            if is_success:
                await interaction.followup.send(
                    f"Growth Check: {roll}/{target} -> {outcome}\nGrowth failed (check success)."
                )
            else:
                growth = random.randint(1, 10)
                await interaction.followup.send(
                    f"Growth Check: {roll}/{target} -> {outcome}\nGrowth value: 1d10 -> {growth}"
                )
            return

        # attribute path (channel+user scoped)
        channel = interaction.channel
        user = interaction.user
        if channel is None or user is None:
            await interaction.followup.send("Channel or user not found.", ephemeral=True)
            return
        attrs = self._get_user_attrs(channel.id, user.id)
        key, _label_req = self._normalize_attr_name(arg)
        meta = attrs.get(key)
        if not meta:
            await interaction.followup.send("Attribute not found. Use /set or .set to define it.", ephemeral=True)
            return
        label = str(meta.get("label", arg))
        try:
            target = int(meta.get("value", 0))
        except Exception:
            await interaction.followup.send("Attribute value is invalid.", ephemeral=True)
            return
        target = max(1, min(100, target))
        roll, outcome = self._coc_check(target)
        # 显示名：使用统一格式
        display_name = self._get_display_name(channel.id, user)
        is_success = outcome in {"critical success", "extreme success", "hard success", "success"}
        if is_success:
            await interaction.followup.send(
                f"[{label}] growth of {display_name}:\n{roll}/{target} -> {outcome}\nGrowth failed."
            )
        else:
            growth = random.randint(1, 10)
            await interaction.followup.send(
                f"[{label}] growth of {display_name}:\n{roll}/{target} -> {outcome}\nGrowth value: 1d10 -> {growth}"
            )

    # ---------------- Temporary Insanity (TI) ----------------
    @app_commands.command(name="ti", description="Temporary Insanity: roll 1d10 and show effect")
    async def ti_slash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=False)
        value = random.randint(1, 10)
        data = TEMP_INSANITY_D10.get(value)
        if not data:
            logger.error("TI mapping missing for value=%s", value)
            await interaction.followup.send(f"TI: {value}")
            return
        name = str(data.get("name", "Unknown")).strip()
        desc = str(data.get("desc", "")).strip()
        duration = random.randint(1, 10)
        desc = desc.format(duration=duration)
        await interaction.followup.send(f"TI: {value} - {name}\n{desc}")

    # ---------------- CoC Attributes Commands ----------------
    @app_commands.command(name="stats", description="Show your attributes in this channel")
    async def stats_slash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        user = interaction.user
        if channel is None or user is None:
            await interaction.followup.send("Channel or user not found.", ephemeral=True)
            return
        attrs = self._get_user_attrs(channel.id, user.id)
        if not attrs:
            await interaction.followup.send("No attributes set.", ephemeral=True)
            return
        # 显示名：使用统一格式
        display_name = self._get_display_name(channel.id, user)
        # 正文中不包含 NAME
        filtered = {k: v for k, v in attrs.items() if k != self._normalize_attr_name("NAME")[0]}
        pretty = self._format_stats_columns_block(filtered, columns=3)
        await interaction.followup.send(f"Stats of {display_name}\n{pretty}", ephemeral=True)

    @app_commands.command(name="set", description="Batch set your attributes in this channel")
    @app_commands.describe(items="Comma-separated pairs: 'Name Value, Name2 Value2'")
    async def set_slash(self, interaction: discord.Interaction, items: str) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        user = interaction.user
        if channel is None or user is None:
            await interaction.followup.send("Channel or user not found.", ephemeral=True)
            return
        items = (items or "").strip()
        if not items:
            await interaction.followup.send("Nothing to set.", ephemeral=True)
            return
        try:
            pairs = self._parse_set_items(items)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if not pairs:
            await interaction.followup.send("Nothing to set.", ephemeral=True)
            return
        store = self._get_user_attrs(channel.id, user.id)
        for name, value in pairs:
            key, label = self._normalize_attr_name(name)
            store[key] = {"label": label, "value": int(value)}
        summary = ", ".join([f"{self._normalize_attr_name(n)[1]}={int(v)}" for n, v in pairs])
        await interaction.followup.send(f"Set: {summary}", ephemeral=True)

    @app_commands.command(name="add", description="Batch add deltas to your attributes in this channel")
    @app_commands.describe(items="Comma-separated pairs: 'Name Delta, Name2 Delta2' (Delta can be negative)")
    async def add_slash(self, interaction: discord.Interaction, items: str) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        user = interaction.user
        if channel is None or user is None:
            await interaction.followup.send("Channel or user not found.", ephemeral=True)
            return
        items = (items or "").strip()
        if not items:
            await interaction.followup.send("Nothing to add.", ephemeral=True)
            return
        try:
            pairs = self._parse_set_items(items)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if not pairs:
            await interaction.followup.send("Nothing to add.", ephemeral=True)
            return
        store = self._get_user_attrs(channel.id, user.id)
        summary_items: list[str] = []
        for name, delta in pairs:
            key, label = self._normalize_attr_name(name)
            meta = store.get(key)
            curr_val = 0
            if meta is not None:
                try:
                    curr_val = int(meta.get("value", 0))
                except Exception:
                    curr_val = 0
            new_val = int(curr_val) + int(delta)
            store[key] = {"label": label, "value": int(new_val)}
            summary_items.append(f"{label}{'+' if int(delta) >= 0 else ''}{int(delta)} => {int(new_val)}")
        summary = ", ".join(summary_items)
        await interaction.followup.send(f"Add: {summary}", ephemeral=True)

    @app_commands.command(name="reset", description="Reset your attributes in this channel")
    async def reset_slash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        user = interaction.user
        if channel is None or user is None:
            await interaction.followup.send("Channel or user not found.", ephemeral=True)
            return
        ok = self._reset_user_attrs(channel.id, user.id)
        
        # 如果是 KP 执行 reset，清空 KP 位
        if self._channel_kp.get(channel.id) == user.id:
            del self._channel_kp[channel.id]
            await interaction.followup.send("Reset done. KP position cleared.", ephemeral=True)
        elif ok:
            await interaction.followup.send("Reset done.", ephemeral=True)
        else:
            await interaction.followup.send("No attributes to reset.", ephemeral=True)

    @app_commands.command(name="remove", description="Remove attributes from your stats")
    @app_commands.describe(items="Comma-separated attribute names to remove, e.g., 'HP, MP, 临时技能'")
    async def remove_slash(self, interaction: discord.Interaction, items: str) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        user = interaction.user
        if channel is None or user is None:
            await interaction.followup.send("Channel or user not found.", ephemeral=True)
            return
        
        items = (items or "").strip()
        if not items:
            await interaction.followup.send("No attributes specified.", ephemeral=True)
            return
        
        # 解析要删除的属性名列表
        attr_names = [name.strip() for name in re.split(r"[，,]+", items) if name.strip()]
        if not attr_names:
            await interaction.followup.send("No attributes specified.", ephemeral=True)
            return
        
        # 获取用户属性
        attrs = self._get_user_attrs(channel.id, user.id)
        if not attrs:
            await interaction.followup.send("No attributes set.", ephemeral=True)
            return
        
        # 删除指定的属性
        removed: list[str] = []
        not_found: list[str] = []
        
        for name in attr_names:
            key, label = self._normalize_attr_name(name)
            # 不允许删除 NAME 属性，使用 /nn 来管理
            if key == self._normalize_attr_name("NAME")[0]:
                not_found.append(f"{label} (use /nn to change name)")
                continue
            
            if key in attrs:
                del attrs[key]
                removed.append(label)
            else:
                not_found.append(label)
        
        # 构建反馈消息
        messages = []
        if removed:
            messages.append(f"Removed: {', '.join(removed)}")
        if not_found:
            messages.append(f"Not found: {', '.join(not_found)}")
        
        if messages:
            await interaction.followup.send("\n".join(messages), ephemeral=True)
        else:
            await interaction.followup.send("No attributes were removed.", ephemeral=True)

    # ---------------- CoC7 Character Generation Commands ----------------
    @app_commands.command(name="cs", description="Generate CoC7 base attributes (including Luck) and totals")
    async def cs_slash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=False)
        channel = interaction.channel
        user = interaction.user
        if channel is None or user is None:
            await interaction.followup.send("Channel or user not found.", ephemeral=True)
            return
        rolled = self._generate_coc7_attributes()
        # 写入频道级缓存
        store = self._get_user_attrs(channel.id, user.id)
        for name, value in rolled.items():
            key, label = self._normalize_attr_name(name)
            store[key] = {"label": label, "value": int(value)}
        pretty = self._format_coc7_attrs_block(rolled)
        await interaction.followup.send(pretty)

    @app_commands.command(name="nn", description="Set your display name in this channel")
    @app_commands.describe(name="Your name to show in stats, or 'clear' to remove")
    async def nn_slash(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        user = interaction.user
        if channel is None or user is None:
            await interaction.followup.send("Channel or user not found.", ephemeral=True)
            return
        name = (name or "").strip()
        if not name:
            await interaction.followup.send("Missing parameter: name.", ephemeral=True)
            return
        
        store = self._get_user_attrs(channel.id, user.id)
        key, label = self._normalize_attr_name("NAME")
        
        # 检查是否是 clear 命令
        if name.lower() == "clear":
            if key in store:
                del store[key]
                await interaction.followup.send("Name cleared.", ephemeral=True)
            else:
                await interaction.followup.send("No name to clear.", ephemeral=True)
        else:
            store[key] = {"label": label, "value": name}
            await interaction.followup.send(f"Name set to: {name}", ephemeral=True)

    # 文本命令：`.roll 2d6` 或 `.roll d20`
    @commands.command(name="roll", aliases=["r"], help="Roll dice: NdM or dM. Usage: .roll 2d6 or .r 2d6")
    async def roll_text(self, ctx: commands.Context, *, expr: str | None = None) -> None:
        expr = (expr or "").strip()
        if not expr:
            await ctx.send("Usage: .roll <expr> or .r <expr>")
            return
        try:
            total, details = self._roll_expression(expr)
        except ValueError as exc:
            await ctx.send(str(exc))
            return
        extra = f" | {'; '.join(details)}" if details else ""
        await ctx.send(f"Roll: {expr} -> {total}{extra}")

    @commands.command(name="secret", help="Secret roll. Usage: .secret <expr>")
    async def secret_text(self, ctx: commands.Context, *, expr: str | None = None) -> None:
        expr = (expr or "").strip()
        if not expr:
            await ctx.send("Usage: .secret <expr>")
            return
        try:
            total, details = self._roll_expression(expr)
        except ValueError as exc:
            await ctx.send(str(exc))
            return
        extra = f" | {'; '.join(details)}" if details else ""
        # DM result
        try:
            await ctx.author.send(f"Secret Roll: {expr} -> {total}{extra}")
        except Exception as exc:
            logger.warning("Failed to DM secret roll result: %s", exc)
            try:
                await ctx.author.send("Could not DM you the result. Please enable DMs.")
            except Exception:
                pass
        await ctx.send("Shadows stir... A secret roll has been cast beyond the veil.")

    @commands.command(name="stats", help="Show your attributes in this channel. Usage: .stats. Support @mention")
    async def stats_text(self, ctx: commands.Context, *, arg: str | None = None) -> None:
        channel = ctx.channel
        if channel is None:
            return
        
        # 提取 mentions
        arg = (arg or "").strip()
        mentions, _ = self._extract_mentions_and_clean_arg(ctx, arg)
        target_users = mentions if mentions else [ctx.author]
        
        # 对每个目标用户显示属性
        results = []
        for user in target_users:
            attrs = self._get_user_attrs(channel.id, user.id)
            if not attrs:
                user_display = self._get_display_name(channel.id, user)
                results.append(f"{user_display}: No attributes set.")
                continue
            # 显示名：使用统一格式
            display_name = self._get_display_name(channel.id, user)
            # 正文中不包含 NAME
            filtered = {k: v for k, v in attrs.items() if k != self._normalize_attr_name("NAME")[0]}
            pretty = self._format_stats_columns_block(filtered, columns=3)
            results.append(f"Stats of {display_name}\n{pretty}")
        
        await ctx.send("\n\n".join(results))

    @commands.command(name="set", help="Batch set attributes. Usage: .set Name Value, Name2 Value2. Support @mention")
    async def set_text(self, ctx: commands.Context, *, items: str | None = None) -> None:
        channel = ctx.channel
        if channel is None:
            return
        
        items = (items or "").strip()
        if not items:
            await ctx.send("Nothing to set.")
            return
        
        # 提取 mentions 并清理参数
        mentions, cleaned_items = self._extract_mentions_and_clean_arg(ctx, items)
        target_users = mentions if mentions else [ctx.author]
        
        try:
            pairs = self._parse_set_items(cleaned_items)
        except ValueError as exc:
            await ctx.send(str(exc))
            return
        if not pairs:
            await ctx.send("Nothing to set.")
            return
        
        # 对每个目标用户设置属性
        results = []
        for user in target_users:
            store = self._get_user_attrs(channel.id, user.id)
            for name, value in pairs:
                key, label = self._normalize_attr_name(name)
                store[key] = {"label": label, "value": int(value)}
            summary = ", ".join([f"{self._normalize_attr_name(n)[1]}={int(v)}" for n, v in pairs])
            user_display = self._get_display_name(channel.id, user)
            results.append(f"{user_display}: Set {summary}")
        
        await ctx.send("\n".join(results))

    @commands.command(name="add", help="Batch add deltas. Usage: .add Name Delta, Name2 Delta2. Support @mention")
    async def add_text(self, ctx: commands.Context, *, items: str | None = None) -> None:
        channel = ctx.channel
        if channel is None:
            return
        
        items = (items or "").strip()
        if not items:
            await ctx.send("Nothing to add.")
            return
        
        # 提取 mentions 并清理参数
        mentions, cleaned_items = self._extract_mentions_and_clean_arg(ctx, items)
        target_users = mentions if mentions else [ctx.author]
        
        try:
            pairs = self._parse_set_items(cleaned_items)
        except ValueError as exc:
            await ctx.send(str(exc))
            return
        if not pairs:
            await ctx.send("Nothing to add.")
            return
        
        # 对每个目标用户增加属性
        results = []
        for user in target_users:
            store = self._get_user_attrs(channel.id, user.id)
            summary_items: list[str] = []
            for name, delta in pairs:
                key, label = self._normalize_attr_name(name)
                meta = store.get(key)
                curr_val = 0
                if meta is not None:
                    try:
                        curr_val = int(meta.get("value", 0))
                    except Exception:
                        curr_val = 0
                new_val = int(curr_val) + int(delta)
                store[key] = {"label": label, "value": int(new_val)}
                summary_items.append(f"{label}{'+' if int(delta) >= 0 else ''}{int(delta)} => {int(new_val)}")
            summary = ", ".join(summary_items)
            user_display = self._get_display_name(channel.id, user)
            results.append(f"{user_display}: Add {summary}")
        
        await ctx.send("\n".join(results))

    @commands.command(name="reset", help="Reset your attributes in this channel. Usage: .reset")
    async def reset_text(self, ctx: commands.Context) -> None:
        channel = ctx.channel
        author = ctx.author
        if channel is None or author is None:
            return
        ok = self._reset_user_attrs(channel.id, author.id)
        
        # 如果是 KP 执行 reset，清空 KP 位
        if self._channel_kp.get(channel.id) == author.id:
            del self._channel_kp[channel.id]
            await ctx.send("Reset done. KP position cleared.")
        elif ok:
            await ctx.send("Reset done.")
        else:
            await ctx.send("No attributes to reset.")

    @commands.command(name="remove", help="Remove attributes from your stats. Usage: .remove Name1, Name2")
    async def remove_text(self, ctx: commands.Context, *, items: str | None = None) -> None:
        channel = ctx.channel
        author = ctx.author
        if channel is None or author is None:
            return
        
        items = (items or "").strip()
        if not items:
            await ctx.send("Usage: .remove Name1, Name2")
            return
        
        # 检查是否包含 mention，如果有则报错
        if ctx.message.mentions:
            await ctx.send("Error: .remove command can only be used on yourself.")
            return
        
        # 解析要删除的属性名列表
        attr_names = [name.strip() for name in re.split(r"[，,]+", items) if name.strip()]
        if not attr_names:
            await ctx.send("No attributes specified.")
            return
        
        # 获取用户属性
        attrs = self._get_user_attrs(channel.id, author.id)
        if not attrs:
            await ctx.send("No attributes set.")
            return
        
        # 删除指定的属性
        removed: list[str] = []
        not_found: list[str] = []
        
        for name in attr_names:
            key, label = self._normalize_attr_name(name)
            # 不允许删除 NAME 属性，使用 .nn 来管理
            if key == self._normalize_attr_name("NAME")[0]:
                not_found.append(f"{label} (use .nn to change name)")
                continue
            
            if key in attrs:
                del attrs[key]
                removed.append(label)
            else:
                not_found.append(label)
        
        # 构建反馈消息
        messages = []
        if removed:
            messages.append(f"Removed: {', '.join(removed)}")
        if not_found:
            messages.append(f"Not found: {', '.join(not_found)}")
        
        if messages:
            await ctx.send("\n".join(messages))
        else:
            await ctx.send("No attributes were removed.")

    @commands.command(name="cs", help="Generate CoC7 base attributes and totals. Usage: .cs")
    async def cs_text(self, ctx: commands.Context) -> None:
        channel = ctx.channel
        author = ctx.author
        if channel is None or author is None:
            return
        rolled = self._generate_coc7_attributes()
        # 写入频道级缓存
        store = self._get_user_attrs(channel.id, author.id)
        for name, value in rolled.items():
            key, label = self._normalize_attr_name(name)
            store[key] = {"label": label, "value": int(value)}
        pretty = self._format_coc7_attrs_block(rolled)
        await ctx.send(pretty)

    @commands.command(name="ti", help="Temporary Insanity: roll 1d10 and show effect. Usage: .ti")
    async def ti_text(self, ctx: commands.Context) -> None:
        value = random.randint(1, 10)
        data = TEMP_INSANITY_D10.get(value)
        if not data:
            logger.error("TI mapping missing for value=%s", value)
            await ctx.send(f"TI: {value}")
            return
        name = str(data.get("name", "Unknown")).strip()
        desc = str(data.get("desc", "")).strip()
        duration = random.randint(1, 10)
        desc = desc.format(duration=duration)
        await ctx.send(f"TI: {value} - {name}\n{desc}")

    @commands.command(name="nn", help="Set display name in this channel. Usage: .nn <name> or .nn clear")
    async def nn_text(self, ctx: commands.Context, *, name: str | None = None) -> None:
        channel = ctx.channel
        author = ctx.author
        if channel is None or author is None:
            return
        name = (name or "").strip()
        if not name:
            await ctx.send("Usage: .nn <name> or .nn clear")
            return
        
        # 检查是否包含 mention，如果有则报错
        if ctx.message.mentions:
            await ctx.send("Error: .nn command can only be used on yourself.")
            return
        
        store = self._get_user_attrs(channel.id, author.id)
        key, label = self._normalize_attr_name("NAME")
        
        # 检查是否是 clear 命令
        if name.lower() == "clear":
            if key in store:
                del store[key]
                await ctx.send("Name cleared.")
            else:
                await ctx.send("No name to clear.")
        else:
            store[key] = {"label": label, "value": name}
            await ctx.send(f"Name set to: {name}")

    @commands.command(name="kp", help="Register as KP (Keeper) in this channel. Usage: .kp")
    async def kp_text(self, ctx: commands.Context, *, arg: str | None = None) -> None:
        channel = ctx.channel
        author = ctx.author
        if channel is None or author is None:
            return
        
        # 不接受任何参数
        if arg and arg.strip():
            await ctx.send("Error: .kp command does not accept any parameters.")
            return
        
        # 检查当前频道是否已有 KP
        current_kp_id = self._channel_kp.get(channel.id)
        if current_kp_id is not None:
            if current_kp_id == author.id:
                await ctx.send("You are already the KP of this channel.")
            else:
                await ctx.send("Error: This channel already has a KP. Only one KP per channel is allowed.")
            return
        
        # 注册为 KP
        self._channel_kp[channel.id] = author.id
        display_name = self._get_display_name(channel.id, author)
        await ctx.send(f"{display_name} is now the KP of this channel.")

    # 文本命令：`.check 60`
    @commands.command(name="check", aliases=["ra"], help="CoC d100 check. Usage: .check <number|attr name> or .ra <number|attr name>. Support @mention")
    async def coc_check_text(self, ctx: commands.Context, *, arg: str | None = None) -> None:
        arg = (arg or "").strip()
        if not arg:
            await ctx.send("Usage: .check <number|attr name> or .ra <number|attr name>")
            return

        channel = ctx.channel
        if channel is None:
            return
        
        # 提取 mentions 并清理参数
        mentions, cleaned_arg = self._extract_mentions_and_clean_arg(ctx, arg)
        target_users = mentions if mentions else [ctx.author]
        
        # number path
        m = re.match(r"^\s*(\d+)\s*$", cleaned_arg)
        if m:
            target = int(m.group(1))
            if not (1 <= target <= 100):
                await ctx.send("Out of range: require 1 <= target <= 100.")
                return
            # 对每个目标用户执行判定
            results = []
            for user in target_users:
                roll, outcome = self._coc_check(target)
                user_display = self._get_display_name(channel.id, user)
                results.append(f"{user_display}: {roll}/{target} -> {outcome}")
            await ctx.send("\n".join(results))
            return
        
        # 对每个目标用户执行判定
        results = []
        for user in target_users:
            attrs = self._get_user_attrs(channel.id, user.id)
            key, _label_req = self._normalize_attr_name(cleaned_arg)
            meta = attrs.get(key)
            if not meta:
                user_display = self._get_display_name(channel.id, user)
                results.append(f"{user_display}: Attribute not found. Use .set to define it.")
                continue
            label = str(meta.get("label", cleaned_arg))
            try:
                target = int(meta.get("value", 0))
            except Exception:
                user_display = self._get_display_name(channel.id, user)
                results.append(f"{user_display}: Attribute value is invalid.")
                continue
            target = max(1, min(100, target))
            roll, outcome = self._coc_check(target)
            # 显示名：使用统一格式
            display_name = self._get_display_name(channel.id, user)
            results.append(f"[{label}] check of {display_name}:\n{roll}/{target} -> {outcome}")
        
        await ctx.send("\n\n".join(results))

    @commands.command(name="sc", help="Sanity check. Usage: .sc succ_expr/fail_expr. Support @mention")
    async def sc_text(self, ctx: commands.Context, *, loss: str | None = None) -> None:
        loss = (loss or "").strip()
        if not loss:
            await ctx.send("Usage: .sc succ_expr/fail_expr")
            return
        
        # 提取 mentions 并清理参数
        mentions, cleaned_loss = self._extract_mentions_and_clean_arg(ctx, loss)
        target_users = mentions if mentions else [ctx.author]
        
        parts = cleaned_loss.split("/", 1)
        if len(parts) != 2:
            await ctx.send("Invalid format. Use 'succ_expr/fail_expr'.")
            return
        succ_expr = parts[0].strip()
        fail_expr = parts[1].strip()
        if not succ_expr or not fail_expr:
            await ctx.send("Invalid format. Both parts required: 'succ_expr/fail_expr'.")
            return

        channel = ctx.channel
        if channel is None:
            return
        
        # 对每个目标用户执行理智检定
        results = []
        for user in target_users:
            attrs = self._get_user_attrs(channel.id, user.id)
            san_meta = attrs.get(self._normalize_attr_name("Sanity")[0])
            if not san_meta:
                user_display = self._get_display_name(channel.id, user)
                results.append(f"{user_display}: Attribute 'Sanity' not found. Use .set to define it.")
                continue
            try:
                san_val = int(san_meta.get("value", 0))
            except Exception:
                user_display = self._get_display_name(channel.id, user)
                results.append(f"{user_display}: Attribute 'Sanity' value is invalid.")
                continue
            target = max(1, min(100, san_val))

            roll = random.randint(1, 100)
            is_success = roll <= target
            chosen_expr = succ_expr if is_success else fail_expr
            try:
                loss_total, details = self._roll_expression(chosen_expr)
            except ValueError as exc:
                user_display = self._get_display_name(channel.id, user)
                results.append(f"{user_display}: {str(exc)}")
                continue

            new_san = max(0, san_val - max(0, loss_total))
            san_key, san_label = self._normalize_attr_name(str(san_meta.get("label", "Sanity")))
            attrs[san_key] = {"label": san_label, "value": int(new_san)}

            # 显示名：使用统一格式
            display_name = self._get_display_name(channel.id, user)

            outcome = "success" if is_success else "failure"
            extra = f" | {'; '.join(details)}" if details else ""
            ti_note = "\n[Temporary Insanity] One-time Sanity loss >= 5. Use /ti or .ti." if loss_total >= 5 else ""
            results.append(
                f"Sanity Check of {display_name}:\n"
                f"SC {roll}/{target} [{san_label}] -> {outcome} | loss: {chosen_expr} -> {loss_total}{extra} | Sanity: {san_val} -> {new_san}{ti_note}"
            )
        
        await ctx.send("\n\n".join(results))

    @commands.command(name="growth", help="Growth check. Usage: .growth <number|attr name>. Support @mention")
    async def growth_text(self, ctx: commands.Context, *, arg: str | None = None) -> None:
        arg = (arg or "").strip()
        if not arg:
            await ctx.send("Usage: .growth <number|attr name>")
            return
        
        # 提取 mentions 并清理参数
        mentions, cleaned_arg = self._extract_mentions_and_clean_arg(ctx, arg)
        target_users = mentions if mentions else [ctx.author]

        channel = ctx.channel
        if channel is None:
            return
        
        # number path
        m = re.match(r"^\s*(\d+)\s*$", cleaned_arg)
        if m:
            target = int(m.group(1))
            if not (1 <= target <= 100):
                await ctx.send("Out of range: require 1 <= target <= 100.")
                return
            # 对每个目标用户执行成长检定
            results = []
            for user in target_users:
                roll, outcome = self._coc_check(target)
                is_success = outcome in {"critical success", "extreme success", "hard success", "success"}
                user_display = self._get_display_name(channel.id, user)
                if is_success:
                    results.append(f"{user_display}: Growth Check {roll}/{target} -> Failed")
                else:
                    growth = random.randint(1, 10)
                    results.append(f"{user_display}: Growth Check {roll}/{target} -> Passed | Growth value: 1d10 -> {growth}")
            await ctx.send("\n".join(results))
            return

        # attribute path
        
        # 对每个目标用户执行成长检定
        results = []
        for user in target_users:
            attrs = self._get_user_attrs(channel.id, user.id)
            key, _label_req = self._normalize_attr_name(cleaned_arg)
            meta = attrs.get(key)
            if not meta:
                user_display = self._get_display_name(channel.id, user)
                results.append(f"{user_display}: Attribute not found. Use .set to define it.")
                continue
            label = str(meta.get("label", cleaned_arg))
            try:
                target = int(meta.get("value", 0))
            except Exception:
                user_display = self._get_display_name(channel.id, user)
                results.append(f"{user_display}: Attribute value is invalid.")
                continue
            target = max(1, min(100, target))
            roll, outcome = self._coc_check(target)
            # 显示名：使用统一格式
            display_name = self._get_display_name(channel.id, user)
            is_success = outcome in {"critical success", "extreme success", "hard success", "success"}
            if is_success:
                results.append(f"[{label}] growth of {display_name}:\n{roll}/{target} -> {outcome}\nGrowth failed.")
            else:
                growth = random.randint(1, 10)
                results.append(f"[{label}] growth of {display_name}:\n{roll}/{target} -> {outcome}\nGrowth value: 1d10 -> {growth}")
        
        await ctx.send("\n\n".join(results))

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CoC(bot))
    logger.info("Cog 'CoC' loaded")


