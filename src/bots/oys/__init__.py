# fmt: off
try:
    import dotenv
    dotenv.load_dotenv()
except ModuleNotFoundError:
    pass
# fmt: on

import asyncio
import logging
from functools import wraps
from os import environ
from pathlib import Path

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

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
    async def inmu_king(
        interaction: discord.Interaction,
        user: discord.Member,
    ):
        await interaction.response.send_message(
            f"今から、被告人 {user.display_name} をINMU KINGの刑に処す。"
        )

        icon_path = BASE_DIR / f"rect_{interaction.id}.png"
        output_path = BASE_DIR / f"result_{interaction.id}.mp4"

        try:
            await user.display_avatar.with_format("png").save(icon_path)

            process = await asyncio.create_subprocess_exec(
                "./render.sh",
                "inmu_king_w_audio.mp4",
                icon_path.name,
                output_path.name,
                cwd=BASE_DIR,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(
                    f"render.sh failed (code {process.returncode}): "
                    f"{stderr.decode(errors='replace')}"
                )
                await interaction.followup.send("動画の生成に失敗しました")
                return

            await interaction.channel.send(
                file=discord.File(output_path, filename="_.mp4")
            )
        finally:
            icon_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

    return bot


token_name = "OYS_TOKEN"
