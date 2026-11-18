# このファイルはほぼ全部AIで記述されており、人間の確認は入っていないことに注意

from __future__ import annotations

import calendar
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import dateparser
import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    delete,
    func,
    select,
)
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# External Bot manager uses this to obtain the Discord token.
token_name = "REMINDER_BOT_TOKEN"

# Maximum character length for message preview in confirmation replies.
MESSAGE_PREVIEW_MAX_LENGTH = 40

# Pattern for Japanese relative time expressions:
# [N年][N(ヶ)月][N日][N時(間)][N分][N秒]後
RELATIVE_JA_TIME_PATTERN = re.compile(
    r"^"
    r"(?:(?P<years>\d+)年\s*)?"
    r"(?:(?P<months>\d+)(?:ヶ|か|ヵ|ケ)?月\s*)?"
    r"(?:(?P<days>\d+)日\s*)?"
    r"(?:(?P<hours>\d+)時(?:間)?\s*)?"
    r"(?:(?P<minutes>\d+)分\s*)?"
    r"(?:(?P<seconds>\d+)秒\s*)?"
    r"後$"
)


# ============================================================
# Database
# ============================================================


class Base(DeclarativeBase):
    pass


class Reserved(Base):
    __tablename__ = "reserved"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    value: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )


# ============================================================
# Utilities
# ============================================================


def create_database_engine():
    """
    Create an async SQLAlchemy engine from REMINDER_DB_URL.

    Supports Supabase Direct Connection and Session Pooler.
    SSL is required by default.
    """

    url = make_url(os.environ["REMINDER_DB_URL"])

    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+asyncpg")

    elif url.drivername != "postgresql+asyncpg":
        raise ValueError(f"Unsupported database driver: {url.drivername}")

    # asyncpg uses "ssl", not libpq's "sslmode".
    query = dict(url.query)

    sslmode = query.pop("sslmode", None)

    if "ssl" not in query:
        query["ssl"] = sslmode or "require"

    url = url.set(query=query)

    return create_async_engine(
        url,
        pool_pre_ping=True,
    )


def parse_relative_ja_time(value: str, base: datetime) -> datetime | None:
    """
    Parse Japanese relative time expressions such as:
    '[N年][N(ヶ)月][N日][N時(間)][N分][N秒]後'
    """

    match = RELATIVE_JA_TIME_PATTERN.fullmatch(value)
    if match is None:
        return None

    groups = match.groupdict()
    if all(v is None for v in groups.values()):
        return None

    years = int(groups["years"] or 0)
    months = int(groups["months"] or 0)
    days = int(groups["days"] or 0)
    hours = int(groups["hours"] or 0)
    minutes = int(groups["minutes"] or 0)
    seconds = int(groups["seconds"] or 0)

    # Add years and months with end-of-month clamping.
    total_months = (base.year * 12 + (base.month - 1)) + years * 12 + months
    target_year, target_month_zero = divmod(total_months, 12)
    target_month = target_month_zero + 1
    max_day = calendar.monthrange(target_year, target_month)[1]
    target_day = min(base.day, max_day)

    result = base.replace(
        year=target_year,
        month=target_month,
        day=target_day,
    )

    return result + timedelta(
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
    )


def parse_remind_time(value: str) -> datetime:
    """
    Parse a wide variety of date/time formats.

    Naive datetimes are interpreted as JST.
    Timezone-aware datetimes are converted to JST.
    """

    value = value.strip().replace(" ", " ")

    if not value:
        raise ValueError("Datetime is empty")

    now = datetime.now(JST)

    # Try ISO 8601 first.
    try:
        result = datetime.fromisoformat(value)

    except ValueError:
        # Try Japanese relative time format next.
        result = parse_relative_ja_time(value, now)

        if result is None:
            # Fall back to dateparser.
            result = dateparser.parse(
                value,
                languages=["ja", "en"],
                settings={
                    "TIMEZONE": "Asia/Tokyo",
                    "TO_TIMEZONE": "Asia/Tokyo",
                    "RETURN_AS_TIMEZONE_AWARE": True,
                    "RELATIVE_BASE": now,
                    "PREFER_DATES_FROM": "future",
                },
            )

    if result is None:
        raise ValueError(f"Could not parse datetime: {value!r}")

    # Assume JST when timezone is omitted.
    if result.tzinfo is None:
        result = result.replace(tzinfo=JST)

    return result.astimezone(JST)


def format_remind_time(value: datetime) -> str:
    return value.astimezone(JST).strftime("%Y-%m-%d %H:%M:%S JST")


def truncate_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return "." * max_length
    return f"{text[: max_length - 3]}..."


# ============================================================
# Bot
# ============================================================


class ReminderBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.default(),
        )

        self.engine = create_database_engine()

        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

    async def setup_hook(self) -> None:
        # Create tables if they do not exist.
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Register application commands.
        await self.tree.sync()

        # Start the reminder scheduler.
        self.reminder_loop.start()

    async def close(self) -> None:
        if self.reminder_loop.is_running():
            self.reminder_loop.cancel()

        await super().close()
        await self.engine.dispose()

    # ========================================================
    # Reminder scheduler
    # ========================================================

    @tasks.loop(minutes=1)
    async def reminder_loop(self) -> None:

        # Retrieve due reminders.
        # A database error must not stop the scheduler.
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(
                        Reserved.id,
                        Reserved.value,
                    )
                    .where(Reserved.date <= func.now())
                    .order_by(
                        Reserved.date,
                        Reserved.id,
                    )
                )

                due_reminders = result.all()

        except Exception:
            logger.exception("Failed to retrieve due reminders")
            return

        # Process reminders sequentially.
        for reminder_id, value in due_reminders:
            await self.send_reminder(
                reminder_id,
                value,
            )

    @reminder_loop.before_loop
    async def before_reminder_loop(self) -> None:
        await self.wait_until_ready()

    @reminder_loop.error
    async def reminder_loop_error(
        self,
        error: Exception,
    ) -> None:
        logger.error(
            "Reminder loop failed",
            exc_info=(
                type(error),
                error,
                error.__traceback__,
            ),
        )

    # ========================================================
    # Send reminder and delete record
    # ========================================================

    async def send_reminder(
        self,
        reminder_id: int,
        value: dict[str, Any],
    ) -> None:

        try:
            channel_id = int(value["channel_id"])

            channel = self.get_channel(channel_id)

            if channel is None:
                channel = await self.fetch_channel(channel_id)

            kind = value["kind"]
            text = value["text"]

            if kind == "remind":
                await channel.send(
                    content=text,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            elif kind == "mention":
                user_id = int(value["user_id"])

                await channel.send(
                    content=f"<@{user_id}> {text}",
                    allowed_mentions=discord.AllowedMentions(
                        users=[discord.Object(id=user_id)],
                        roles=False,
                        everyone=False,
                        replied_user=False,
                    ),
                )

            else:
                raise ValueError(f"Unknown reminder kind: {kind}")

        except Exception:
            logger.exception(
                "Failed to send reminder. id=%s",
                reminder_id,
            )

        finally:
            # Always delete the record regardless of
            # whether sending succeeded or failed.
            try:
                async with self.session_factory.begin() as session:
                    await session.execute(
                        delete(Reserved).where(Reserved.id == reminder_id)
                    )

            except Exception:
                logger.exception(
                    "Failed to delete reminder. id=%s",
                    reminder_id,
                )


# ============================================================
# Bot factory
# ============================================================


def create_bot() -> ReminderBot:

    bot = ReminderBot()

    # ========================================================
    # Application command error handler
    # ========================================================

    @bot.tree.error
    async def app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:

        command_name = (
            interaction.command.qualified_name
            if interaction.command is not None
            else "unknown"
        )

        logger.error(
            "Application command failed: %s",
            command_name,
            exc_info=(
                type(error),
                error,
                error.__traceback__,
            ),
        )

        # Update the initial ephemeral response if possible.
        try:
            message = "予約処理中にエラーが発生しました。開発者ログを確認してください。"

            if interaction.response.is_done():
                await interaction.edit_original_response(content=message)
            else:
                await interaction.response.send_message(
                    message,
                    ephemeral=True,
                )

        except discord.HTTPException:
            logger.exception("Failed to send application command error response")

    # ========================================================
    # Shared reservation function
    # ========================================================

    async def reserve(
        interaction: discord.Interaction,
        when: str,
        value: dict[str, Any],
        max_message_length: int = 2000,
    ) -> None:

        # Respond immediately so that the interaction
        # does not expire during database operations.
        await interaction.response.send_message(
            "入力された日時は日本時間（JST）として解釈します。\n予約を処理しています。"
        )

        # Validate message length.
        if len(value["text"]) > max_message_length:
            await interaction.edit_original_response(
                content=(
                    f"メッセージが長すぎます"
                    f"（入力文字数: {len(value['text'])}文字 / 上限: {max_message_length}文字）。"
                )
            )
            return

        # Parse datetime.
        try:
            remind_at = parse_remind_time(when)

        except ValueError:
            when_preview = truncate_text(when, 200)
            await interaction.edit_original_response(
                content=(
                    "日時を解釈できませんでした。\n"
                    f"入力日時: {when_preview}\n"
                    "例:\n"
                    "- `2026-11-19 09:00`\n"
                    "- `2026/11/19 9:00`\n"
                    "- `2026年11月19日 9時`\n"
                    "- `Nov 19, 2026 9:00 AM`\n"
                    "- `明日の午前9時`\n"
                    "- `30分後` / `1時間30分後` / `1年2ヶ月3日後`"
                )
            )
            return

        if interaction.channel_id is None:
            raise RuntimeError("Channel ID is missing")

        value["channel_id"] = interaction.channel_id

        # Insert reminder into database.
        async with bot.session_factory.begin() as session:
            session.add(
                Reserved(
                    date=remind_at,
                    value=value,
                )
            )

        # Build confirmation message including input arguments.
        when_preview = truncate_text(when, 200)
        message_preview = truncate_text(value["text"], MESSAGE_PREVIEW_MAX_LENGTH)

        details = [
            f"入力日時: {when_preview}",
            f"実行時刻: {format_remind_time(remind_at)}",
        ]

        if value["kind"] == "mention":
            details.append(f"メンション先: <@{value['user_id']}>")

        details.append(f"メッセージ:\n{message_preview}")

        if value["kind"] == "mention":
            details.append("※確認返信ではメンション通知は送信されません。")

        await interaction.edit_original_response(
            content="リマインドを予約しました。\n" + "\n".join(details),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # ========================================================
    # reserve_remind
    # ========================================================

    @bot.tree.command(
        name="reserve_remind",
        description="リマインドを予約する",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        when="実行時刻（日本時間・JST）",
        message="リマインド時に送信するテキスト",
    )
    async def reserve_remind(
        interaction: discord.Interaction,
        when: str,
        message: str,
    ) -> None:

        await reserve(
            interaction,
            when,
            {
                "kind": "remind",
                "text": message,
            },
        )

    # ========================================================
    # reserve_mention
    # ========================================================

    @bot.tree.command(
        name="reserve_mention",
        description="メンション付きリマインドを予約する",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        when="実行時刻（日本時間・JST）",
        user="メンションするユーザー",
        message="メンション時に送信するテキスト",
    )
    async def reserve_mention(
        interaction: discord.Interaction,
        when: str,
        user: discord.Member,
        message: str,
    ) -> None:

        mention_prefix = f"<@{user.id}> "

        await reserve(
            interaction,
            when,
            {
                "kind": "mention",
                "user_id": user.id,
                "text": message,
            },
            max_message_length=(2000 - len(mention_prefix)),
        )

    return bot
