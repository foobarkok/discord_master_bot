# fmt: off
try:
    import dotenv
    dotenv.load_dotenv()
except ModuleNotFoundError:
    pass
# fmt: on

import asyncio
import importlib
import logging
from collections import deque
from os import environ
from pathlib import Path


class MemoryHandler(logging.Handler):
    def __init__(self, capacity: int):
        super().__init__()
        self.records = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord):
        self.records.append(record)


memory_handler = MemoryHandler(capacity=10000)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        memory_handler,
        logging.FileHandler("app.log", encoding="utf-8"),
    ],
)
logging.getLogger("discord").setLevel(logging.WARNING)


from bot_manager import ChildBotsManager

logger = logging.getLogger(__name__)

import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
master_bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

bm: ChildBotsManager


@master_bot.event
async def on_ready():
    await master_bot.tree.sync()
    logger.info(f"We have logged in as {master_bot.user}")


@master_bot.event
async def on_err_occurred(e: str):
    logger.error(e)


@master_bot.tree.command(name="log", description="logを出力")
async def output_log(interaction: discord.Interaction):
    pass


@master_bot.event
async def on_child_bot_crashed(name: str, tb: str):
    logger.error(f"Bot {name} crashed.")
    logger.error("======TraceBack======")
    logger.error(tb.rstrip())
    logger.error("=====================")


@master_bot.tree.command(name="hello", description="Hello!")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hello!")


@master_bot.tree.command(name="info", description="get bot list")
async def get_info(interaction: discord.Interaction):
    await interaction.response.send_message(await bm.get_info())


@master_bot.tree.command(name="stop", description="stop a child-bot")
async def stop_bot(interaction: discord.Interaction, name: str):
    tmp = await bm.stop_child(name)
    if not tmp:
        tmp = "操作は正常に完了しました"
    await interaction.response.send_message(tmp)


@master_bot.tree.command(name="start", description="start a child-bot")
async def start_bot(interaction: discord.Interaction, name: str):
    tmp = await bm.start_child(name)
    if not tmp:
        tmp = "操作は正常に完了しました"
    await interaction.response.send_message(tmp)


@master_bot.tree.command(name="reboot", description="stop and restart a child-bot")
async def reboot_bot(interaction: discord.Interaction, name: str):
    tmp = await bm.reboot_child(name)
    if not tmp:
        tmp = "操作は正常に完了しました"
    await interaction.response.send_message(tmp)


async def main():
    global bm

    bm = ChildBotsManager(master_bot)
    bots_dir = Path(__file__).parent / "bots"
    for file in bots_dir.glob("*.py"):
        if file.stem == "__init__":
            continue

        name = file.stem
        module = importlib.import_module(f"bots.{name}")
        bm.register(name, module)

    tmp = await bm.start_all()
    if tmp:
        print(tmp)
        return
    await master_bot.start(environ["MASTER_TOKEN"])


asyncio.run(main())
