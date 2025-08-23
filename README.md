### rng-helper

基于 discord.py 的仅 Slash 命令机器人模板，内置通用 Cogs 架构与动态扩展加载。

---

### 依赖与环境

- **Python**: >= 3.13
- **依赖管理（推荐）**: `uv`（也可使用 pip）
- **Discord**: 需要在开发者门户创建应用与 Bot，并邀请到服务器

---

### 环境变量

- **DISCORD_TOKEN**: 你的 Bot Token（必填）
- **DISCORD_GUILD_ID**: 单个服务器 ID（可选，设置后会将 Slash 命令优先同步到该测试服务器，生效更快）

可以使用 shell 导出或 `.env` 文件（若使用 `uv run --env-file .env`）。

推荐使用两套配置文件：

- `.env.development`
  ```env
  DISCORD_TOKEN=your_dev_bot_token_here
  DISCORD_GUILD_ID=your_test_guild_id_here
  DISCORD_OWNER_ID=your_user_id_here
  ```
- `.env.production`
  ```env
  DISCORD_TOKEN=your_prod_bot_token_here
  # 不建议设置 DISCORD_GUILD_ID（默认进行全局同步）
  DISCORD_OWNER_ID=your_user_id_here
  ```

---

### 安装与运行

使用 uv（推荐）：

```bash
# 安装依赖（按需）
uv pip install -U discord-py

# 运行（读取 .env）
uv run --env-file .env.development python bot.py   # 开发
uv run --env-file .env.production python bot.py    # 生产
```

使用 pip：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip discord-py
python bot.py
```

---

### 仅 Slash 命令

- 基础命令：
  - **/ping**: 返回延迟（ms）

- 管理命令（需要管理员权限）：
  - **/load ext:** 加载扩展（如 `cogs.general`）
  - **/unload ext:** 卸载扩展
  - **/reload ext:** 重载扩展（传入 `all` 可重载全部）
  - **/sync [scope]:** 同步应用命令（`guild` 仅当前服务器、默认 `global` 全局）

> 提示：`DISCORD_GUILD_ID` 设置后，启动时会将全局命令复制到该服务器并优先同步，开发调试更快；全局同步通常需要更长时间在所有服务器生效。

---

### 目录结构与扩展

```
cogs/
  __init__.py
  general.py    # 示例：/ping
  manager.py    # 管理：/load /unload /reload /sync
bot.py          # 入口，自动加载 cogs 并同步 Slash 命令
```

- 新增命令：在 `cogs/` 内新建模块，定义 `async def setup(bot): await bot.add_cog(YourCog(bot))`。
- 命名规范：文件名与 Cog 类名均可自定义；文件名以 `_` 开头会被忽略。

---

### 动态加载与同步

- 使用 `/load`、`/unload`、`/reload` 管理扩展；完成后会自动同步 Slash 命令。
- 新增文件后：执行 `/load cogs.your_module`；修改后：执行 `/reload cogs.your_module` 或 `/reload all`。

### 日志

- 按需求记录英文日志（遵循规则：响应中文、日志英文）。
- 启动时会显示登录信息、扩展加载状态与命令同步结果。

---

### 常见问题

- 命令未出现：
  - 确认机器人已加入服务器、权限足够。
  - 若为全局命令，同步到所有服务器可能需一段时间；测试阶段建议设置 `DISCORD_GUILD_ID`。
  - 查看控制台日志是否有同步错误。

- 热重载无效：
  - 确认设置 `COGS_AUTO_RELOAD=1` 并安装 `watchdog`。
  - 检查修改的文件是否位于 `cogs/` 且不是以下划线开头的文件。


