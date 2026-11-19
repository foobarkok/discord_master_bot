import asyncio
import importlib
import io
import logging
import sys
from collections import deque
from functools import wraps
from os import environ
from pathlib import Path

# fmt: off
try:
    import dotenv
    dotenv.load_dotenv()
except ModuleNotFoundError:
    pass
if "--keep-alive" in sys.argv[1:]:
    from keep_alive import start_health_check_server
    start_health_check_server()
# fmt: on


class MyHandler(logging.Handler):
    def __init__(self, capacity: int):
        super().__init__()
        self.records = deque(maxlen=capacity)
        self.log_str = ""

    def emit(self, record: logging.LogRecord):
        self.records.append(record)
        formatted = self.format(record)
        self.log_str += formatted + "\n"
        if record.levelno >= logging.WARNING or not record.name.startswith("discord"):
            print(formatted)


my_handler = MyHandler(capacity=10000)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        my_handler,
        logging.FileHandler("app.log", encoding="utf-8"),
    ],
)


from bot_manager import ChildBotsManager

logger = logging.getLogger(__name__)

import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
master_bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

bm: ChildBotsManager

ADMIN_IDS = {int(id) for id in environ["ADMIN_IDS"].split(",") if id.strip()}


def check_admin():
    def dec(coroutine):
        @wraps(coroutine)
        async def _wrapper(
            interaction: discord.Interaction,
            *args,
            **kwargs,
        ) -> None:
            if interaction.user.id not in ADMIN_IDS:
                await interaction.response.send_message(
                    "このコマンドはこのBotの管理者のみが使用できます",
                    ephemeral=True,
                )
                return

            await coroutine(interaction, *args, **kwargs)

        return _wrapper

    return dec


@master_bot.event
async def on_ready():
    await master_bot.tree.sync()
    logger.info(f"We have logged in as {master_bot.user}")


@master_bot.event
async def on_err_occurred(e: str):
    logger.error(e)


@master_bot.tree.command(name="log", description="logを出力")
@check_admin()
async def output_log(interaction: discord.Interaction):
    file = discord.File(
        io.BytesIO(my_handler.log_str.encode("utf-8")), filename="app.log"
    )
    await interaction.response.send_message("logを送信しました", file=file)


@master_bot.event
async def on_child_bot_crashed(name: str, tb: str):
    logger.error(f"Bot {name} crashed.")
    logger.error("TraceBack:")
    logger.error(tb.rstrip())


@master_bot.tree.command(name="hello", description="Hello!")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hello!")


@master_bot.tree.command(name="info", description="get bot list")
async def get_info(interaction: discord.Interaction):
    await interaction.response.send_message(await bm.get_info())


@master_bot.tree.command(name="stop", description="stop a child-bot")
@check_admin()
async def stop_bot(interaction: discord.Interaction, name: str):
    tmp = await bm.stop_child(name)
    if not tmp:
        tmp = "操作は正常に完了しました"
    await interaction.response.send_message(tmp)


@master_bot.tree.command(name="start", description="start a child-bot")
@check_admin()
async def start_bot(interaction: discord.Interaction, name: str):
    tmp = await bm.start_child(name)
    if not tmp:
        tmp = "操作は正常に完了しました"
    await interaction.response.send_message(tmp)


@master_bot.tree.command(name="reboot", description="stop and restart a child-bot")
@check_admin()
async def reboot_bot(interaction: discord.Interaction, name: str):
    tmp = await bm.reboot_child(name)
    if not tmp:
        tmp = "操作は正常に完了しました"
    await interaction.response.send_message(tmp)


async def main():
    global bm

    bm = ChildBotsManager(master_bot)
    bots_dir = Path(__file__).parent / "bots"
    for item in bots_dir.iterdir():
        if item.is_dir():
            name = item.name
        elif item.suffix == ".py":
            name = item.stem
        else:
            continue

        module = importlib.import_module(f"bots.{name}")
        bm.register(name, module)

    tmp = await bm.start_all()
    if tmp:
        print(tmp)
        return
    await master_bot.start(environ["MASTER_TOKEN"])


asyncio.run(main())
