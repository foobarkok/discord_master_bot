import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


def create_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

    @bot.event
    async def on_ready():
        # await bot.tree.sync()
        logger.info(f"We have logged in as {bot.user}")

    @bot.event
    async def on_message(message: discord.Message):
        if "うお" in message.content:
            await message.reply("冷笑を検出しました！")

    return bot


token_name = "REISHOU_TOKEN"
