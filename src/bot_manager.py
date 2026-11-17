# fmt: off
try:
    import dotenv
    dotenv.load_dotenv()
except ModuleNotFoundError:
    pass
# fmt: on

import asyncio
import logging
import sys
import traceback
from os import environ
from types import ModuleType

logger = logging.getLogger(__name__)

import discord


class ChildBotsManager:
    def __init__(self, master_bot: discord.Client):
        self.master_bot = master_bot
        self.modules: dict[str, ModuleType] = {}
        self.child_bots: dict[str, discord.Client | None] = {}
        self.child_tasks: dict[str, asyncio.Task | None] = {}
        self.child_locks: dict[str, asyncio.Lock] = {}

    def register(self, name: str, module: ModuleType):
        self.modules[name] = module
        self.child_bots[name] = None
        self.child_tasks[name] = None
        self.child_locks[name] = asyncio.Lock()

    async def start_child(self, name: str) -> str | None:
        async with self.child_locks[name]:
            task = self.child_tasks[name]
            if task and (not task.done()):
                return "開始済みのBotを開始しようとしています"
            self.child_tasks[name] = asyncio.create_task(self._run_child(name))

    async def stop_child(self, name: str) -> str | None:
        async with self.child_locks[name]:
            task = self.child_tasks[name]
            if (not task) or task.done():
                return "既に終了しているBotをstopしようとしています"

            bot = self.child_bots[name]
            assert bot is not None
            assert not bot.is_closed()
            await bot.close()

    async def reboot_child(self, name: str) -> str | None:
        return await self.stop_child(name) or await self.start_child(name)

    async def _run_child(self, name: str):
        module = self.modules[name]
        bot: discord.Client = module.create_bot()
        self.child_bots[name] = bot

        async def on_error(_event_method: str, /, *args, **kwargs):
            exc_type, exc, tb = sys.exc_info()
            tb_str = "".join(traceback.format_exception(exc_type, exc, tb))
            self.master_bot.dispatch(
                "child_bot_crashed",
                name,
                tb_str,
            )

        bot.on_error = on_error

        try:
            await bot.start(environ[module.token_name])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Bot %s crashed", name)
            self.master_bot.dispatch(
                "child_bot_crashed",
                name,
                "\n".join(traceback.TracebackException.from_exception(e).format()),
            )
        finally:
            await bot.close()

    async def start_all(self) -> str | None:
        for name in self.modules:
            tmp = await self.start_child(name)
            if tmp:
                return tmp

    async def get_info(self) -> str:
        result = []

        for name in self.modules:
            bot = self.child_bots[name]
            status = "Running"
            if (not bot) or bot.is_closed():
                status = "Not Running"
            result.append(f"{name}: {status}")

        return "\n".join(result)
