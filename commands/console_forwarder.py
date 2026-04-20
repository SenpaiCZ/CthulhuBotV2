import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import sys
import io
import logging
import datetime
from collections import deque
from loadnsave import load_settings


class _StreamCapture(io.TextIOBase):
    def __init__(self, original, queue):
        self.original = original
        self.queue = queue
        self._buf = ""

    def write(self, text):
        self.original.write(text)
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self.queue.append((datetime.datetime.now(), line))
        return len(text)

    def flush(self):
        self.original.flush()

    def fileno(self):
        return self.original.fileno()


class _DiscordLogHandler(logging.Handler):
    def __init__(self, queue):
        super().__init__(level=logging.WARNING)
        self.queue = queue
        self.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))

    def emit(self, record):
        try:
            self.queue.append((datetime.datetime.now(), self.format(record)))
        except Exception:
            pass


class ConsoleForwarder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._queue: deque = deque(maxlen=500)
        self._owner: discord.User | None = None
        self._capturing = False
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._log_handler = _DiscordLogHandler(self._queue)
        self.forward_task.start()

    def cog_unload(self):
        self.forward_task.cancel()
        self._stop_capture()

    # ── capture control ──────────────────────────────────────

    def _start_capture(self):
        if self._capturing:
            return
        sys.stdout = _StreamCapture(self._original_stdout, self._queue)
        sys.stderr = _StreamCapture(self._original_stderr, self._queue)
        logging.getLogger().addHandler(self._log_handler)
        self._capturing = True

    def _stop_capture(self):
        if not self._capturing:
            return
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        logging.getLogger().removeHandler(self._log_handler)
        self._capturing = False

    # ── owner DM ─────────────────────────────────────────────

    async def _get_owner(self) -> discord.User | None:
        if self._owner is None:
            try:
                app_info = await self.bot.application_info()
                self._owner = app_info.owner
            except Exception:
                return None
        return self._owner

    async def _send_batched(self, lines: list[str]):
        owner = await self._get_owner()
        if not owner:
            return
        chunk = ""
        for line in lines:
            entry = line + "\n"
            if len(chunk) + len(entry) > 1800:
                try:
                    await owner.send(f"```\n{chunk}```")
                except Exception:
                    pass
                chunk = entry
            else:
                chunk += entry
        if chunk:
            try:
                await owner.send(f"```\n{chunk}```")
            except Exception:
                pass

    # ── background task ───────────────────────────────────────

    @tasks.loop(seconds=5)
    async def forward_task(self):
        if not self._queue:
            return
        settings = load_settings()
        if not settings.get("console_forwarding", False):
            self._queue.clear()
            return
        lines = []
        while self._queue:
            ts, text = self._queue.popleft()
            lines.append(f"[{ts.strftime('%H:%M:%S')}] {text}")
        if lines:
            await self._send_batched(lines)

    @forward_task.before_loop
    async def before_forward_task(self):
        await self.bot.wait_until_ready()
        settings = load_settings()
        if settings.get("console_forwarding", False):
            self._start_capture()

    # ── slash commands ────────────────────────────────────────

    console_group = app_commands.Group(name="console", description="Console log forwarding to DM.")

    @console_group.command(name="on", description="Start forwarding console output to owner DM.")
    async def console_on(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Owner only.", ephemeral=True)
            return
        self._start_capture()
        settings = load_settings()
        settings["console_forwarding"] = True
        from loadnsave import save_settings
        await save_settings(settings)
        await interaction.response.send_message("Console forwarding **enabled**. Logs go to your DM.", ephemeral=True)

    @console_group.command(name="off", description="Stop forwarding console output to owner DM.")
    async def console_off(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Owner only.", ephemeral=True)
            return
        self._stop_capture()
        self._queue.clear()
        settings = load_settings()
        settings["console_forwarding"] = False
        from loadnsave import save_settings
        await save_settings(settings)
        await interaction.response.send_message("Console forwarding **disabled**.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ConsoleForwarder(bot))
