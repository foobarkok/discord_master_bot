# fmt: off
try:
    import dotenv
    dotenv.load_dotenv()
except ModuleNotFoundError:
    pass
# fmt: on

import logging
from functools import wraps
from os import environ

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


OYS_ALLOWED_IDS = {
    int(id) for id in environ["OYS_ALLOWED_IDS"].split(",") if id.strip()
}


def check_oys():
    def dec(coroutine):
        @wraps(coroutine)
        async def _wrapper(
            interaction: discord.Interaction,
            *args,
            **kwargs,
        ) -> None:
            if interaction.user.id not in OYS_ALLOWED_IDS:
                await interaction.response.send_message(
                    "罪人を判断してINMU KINGの刑に処せるのは、権限を持ってる一部の人だけだって、それ一番言われてるから",
                    ephemeral=True,
                )
                return

            await coroutine(interaction, *args, **kwargs)

        return _wrapper

    return dec


def create_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

    @bot.event
    async def on_ready():
        await bot.tree.sync()
        logger.info(f"We have logged in as {bot.user}")

    @bot.tree.command(name="inmu_king", description="罪人をINMU KINGの刑に処す")
    @check_oys()
    async def hello(
        interaction: discord.Interaction,
        user: discord.Member,
    ):
        await interaction.response.send_message(
            f"{user.display_name}をINMU KINGの刑に処すよ〜"
        )

    return bot


token_name = "OYS_TOKEN"
