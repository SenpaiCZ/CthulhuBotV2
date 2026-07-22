import os
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import discord
import pytest

import bot as bot_module


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def make_fake_bot(owner=None):
    fake_bot = MagicMock()
    app_info = MagicMock()
    app_info.owner = owner
    fake_bot.application_info = AsyncMock(return_value=app_info)
    fake_bot.fetch_user = AsyncMock()
    return fake_bot


class TestGetOwner:
    @pytest.mark.asyncio
    async def test_returns_direct_owner(self):
        owner = MagicMock()
        owner.send = AsyncMock()
        fake_bot = make_fake_bot(owner=owner)

        result = await bot_module._get_owner(fake_bot)

        assert result is owner

    @pytest.mark.asyncio
    async def test_resolves_team_owner_by_fetching_user(self):
        team = MagicMock(spec=discord.Team)
        team.owner = 12345
        fetched_user = MagicMock()
        fetched_user.send = AsyncMock()
        fake_bot = make_fake_bot(owner=team)
        fake_bot.fetch_user = AsyncMock(return_value=fetched_user)

        result = await bot_module._get_owner(fake_bot)

        fake_bot.fetch_user.assert_awaited_once_with(12345)
        assert result is fetched_user

    @pytest.mark.asyncio
    async def test_returns_none_when_application_info_raises(self):
        fake_bot = MagicMock()
        fake_bot.application_info = AsyncMock(side_effect=Exception("network error"))

        result = await bot_module._get_owner(fake_bot)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_owner_has_no_send(self):
        fake_bot = make_fake_bot(owner=object())  # no .send attribute

        result = await bot_module._get_owner(fake_bot)

        assert result is None


class TestWriteHealthMarker:
    def test_creates_marker_file(self):
        bot_module._write_health_marker()
        assert os.path.exists(bot_module.UPDATE_HEALTH_MARKER)

    def test_does_not_raise_on_write_failure(self, monkeypatch):
        def _raise(*a, **kw):
            raise OSError("disk full")
        monkeypatch.setattr("builtins.open", _raise)
        bot_module._write_health_marker()  # must not raise


class TestSendRollbackNoticeIfPresent:
    @pytest.mark.asyncio
    async def test_noop_when_no_notice_file(self):
        fake_bot = MagicMock()
        await bot_module._send_rollback_notice_if_present(fake_bot)
        fake_bot.application_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_notice_content_to_owner_and_deletes_file(self):
        with open(bot_module.ROLLBACK_NOTICE_FILE, "w") as f:
            f.write("The bot was rolled back.")
        owner = MagicMock()
        owner.send = AsyncMock()
        fake_bot = make_fake_bot(owner=owner)

        await bot_module._send_rollback_notice_if_present(fake_bot)

        owner.send.assert_awaited_once_with("The bot was rolled back.")
        assert not os.path.exists(bot_module.ROLLBACK_NOTICE_FILE)

    @pytest.mark.asyncio
    async def test_deletes_file_even_if_owner_unavailable(self):
        with open(bot_module.ROLLBACK_NOTICE_FILE, "w") as f:
            f.write("notice")
        fake_bot = MagicMock()
        fake_bot.application_info = AsyncMock(side_effect=Exception("no owner"))

        await bot_module._send_rollback_notice_if_present(fake_bot)

        assert not os.path.exists(bot_module.ROLLBACK_NOTICE_FILE)


class TestOnReadyWiring:
    @pytest.mark.asyncio
    async def test_writes_health_marker(self, monkeypatch):
        with patch.object(type(bot_module.bot), 'user', new_callable=PropertyMock) as mock_user:
            mock_user.return_value = MagicMock(id=123)
            monkeypatch.setattr(bot_module.bot, "failed_extensions", [])
            monkeypatch.setattr(bot_module.bot, "application_info", AsyncMock(side_effect=Exception("no network in test")))

            await bot_module.on_ready()

            assert os.path.exists(bot_module.UPDATE_HEALTH_MARKER)
