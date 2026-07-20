import importlib
import pkgutil
import pytest
from discord.ext import tasks
from unittest.mock import AsyncMock, MagicMock

import commands as commands_pkg


def _cog_module_names():
    """Every commands/*.py module that isn't a _foo.py shared-UI helper file."""
    names = []
    for _, name, is_pkg in pkgutil.iter_modules(commands_pkg.__path__):
        if is_pkg or name.startswith("_"):
            continue
        names.append(name)
    return sorted(names)


COG_MODULE_NAMES = _cog_module_names()


def test_at_least_expected_cog_modules_discovered():
    """Sanity check the discovery mechanism itself isn't silently finding zero files."""
    assert len(COG_MODULE_NAMES) >= 30


@pytest.mark.parametrize("module_name", COG_MODULE_NAMES)
def test_cog_module_imports_cleanly(module_name):
    """Every commands/<module>.py must import without raising — catches a missing/broken
    import left behind by a companion-file split before any bot ever tries to load it."""
    importlib.import_module(f"commands.{module_name}")


@pytest.mark.parametrize("module_name", COG_MODULE_NAMES)
def test_cog_module_has_setup_function(module_name):
    """Every non-underscore commands/*.py file must expose def setup(bot) per the project's
    auto-load convention (bot.py iterates commands/*.py and calls bot.load_extension)."""
    mod = importlib.import_module(f"commands.{module_name}")
    assert hasattr(mod, "setup"), f"commands.{module_name} has no setup(bot) function"


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name", COG_MODULE_NAMES)
async def test_cog_setup_registers_without_error(module_name):
    """Actually call setup(bot) with a mock bot and confirm it doesn't raise — this is the
    check that would catch a companion-file split breaking Cog instantiation (e.g. a UI class
    referenced in __init__ that got moved but not re-imported)."""
    mod = importlib.import_module(f"commands.{module_name}")
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.add_cog = AsyncMock()
    await mod.setup(bot)
    assert bot.add_cog.called, f"commands.{module_name}.setup(bot) never called bot.add_cog(...)"

    # Some cogs start a discord.ext.tasks.Loop in __init__ (e.g. music.py, rss.py). Cancel any
    # such loops immediately so they never get a chance to run against the mock bot in the
    # background (which would fail on unmocked async bot methods like wait_until_ready()).
    cog = bot.add_cog.call_args.args[0]
    for attr_name in dir(cog):
        attr = getattr(cog, attr_name, None)
        if isinstance(attr, tasks.Loop):
            attr.cancel()
