from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from commands.rollback import Rollback, BackupSelect, BackupSelectView


def make_interaction(user=None):
    interaction = MagicMock()
    interaction.user = user or MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup.send = AsyncMock()
    interaction.client.close = AsyncMock()
    return interaction


class TestRollbackCommand:
    @pytest.mark.asyncio
    async def test_rejects_non_owner(self):
        bot = MagicMock()
        bot.is_owner = AsyncMock(return_value=False)
        cog = Rollback(bot)
        interaction = make_interaction()

        await Rollback.rollback.callback(cog, interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "⛔ You do not have permission to run this command.", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_no_backups_available_shows_message(self):
        bot = MagicMock()
        bot.is_owner = AsyncMock(return_value=True)
        cog = Rollback(bot)
        interaction = make_interaction()

        with patch("commands.rollback.get_system_backups", return_value=[]):
            await Rollback.rollback.callback(cog, interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "No backups available to restore.", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_shows_select_view_with_backups(self):
        bot = MagicMock()
        bot.is_owner = AsyncMock(return_value=True)
        cog = Rollback(bot)
        interaction = make_interaction()
        backups = [{"name": "backup_1.zip", "size": 2048, "created": "2026-07-22 10:00:00"}]

        with patch("commands.rollback.get_system_backups", return_value=backups):
            await Rollback.rollback.callback(cog, interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert isinstance(kwargs["view"], BackupSelectView)


class TestBackupSelectCallback:
    @pytest.mark.asyncio
    async def test_spawns_updater_restore_and_closes_bot(self):
        backups = [{"name": "backup_1.zip", "size": 2048, "created": "2026-07-22 10:00:00"}]
        select = BackupSelect(backups)
        select._values = ["backup_1.zip"]
        interaction = make_interaction()

        with patch("commands.rollback.subprocess.Popen") as mock_popen, \
             patch("commands.rollback.os.getpid", return_value=4242), \
             patch("commands.rollback.sys.executable", "/usr/bin/python3"), \
             patch("commands.rollback.os.name", "posix"):
            await select.callback(interaction)

        mock_popen.assert_called_once_with(
            ["/usr/bin/python3", "updater.py", "4242", "--restore", "backup_1.zip"]
        )
        interaction.client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_popen_failure_sends_error_and_does_not_close_bot(self):
        backups = [{"name": "backup_1.zip", "size": 2048, "created": "2026-07-22 10:00:00"}]
        select = BackupSelect(backups)
        select._values = ["backup_1.zip"]
        interaction = make_interaction()

        with patch("commands.rollback.subprocess.Popen", side_effect=OSError("no permission")):
            await select.callback(interaction)

        interaction.followup.send.assert_awaited_once()
        interaction.client.close.assert_not_called()
