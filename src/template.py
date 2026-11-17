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
        await bot.tree.sync()
        logger.info(f"We have logged in as {bot.user}")

    @bot.tree.command(name="hello", description="Hello!")
    async def hello(interaction: discord.Interaction):
        await interaction.response.send_message("Hello!")

    return bot


token_name = "TOKEN"
