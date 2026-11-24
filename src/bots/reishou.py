# なんと、このファイルは一切AIを使わずに書かれています

import logging
import re

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

left_bracket = r"(\(|（)"
right_bracket = r"(\)|）)"
symbols = r"(\\|/|\.|\^|\$|\||\*|\+|\?|\{|\}|\[|\]|\-|\(|\)|\"|\'|\!|[！”＃＄％＆’（）＝ー＾〜￥｜＠｀「｛；＋：＊」｝、＜。＞・？￥＿]←↓↑→)"
u_pattern = r"([うぅゥぅ゙ゥ゙ウuUｕＵ宇])"
o_pattern = r"([おぉオォぉ゙ォ゙oOｏＯοΟ於于])"
space_pattern = r"( |　)"
mid_pattern = rf"({space_pattern}|{symbols})*"
w_pattern = r"([wWｗＷωっッっ゙ッ゙])"
reishou_pattern = re.compile(
    # 「お」の判定はギリシャ文字オミクロンの全角の大文字と小文字表記を含む
    rf"({u_pattern}{mid_pattern}{o_pattern}{mid_pattern}( |{w_pattern}|$|{symbols}))|(お{space_pattern}う{space_pattern}{w_pattern})|({left_bracket}((reishou)|(reisyou)){right_bracket})|({left_bracket}{space_pattern}((冷{space_pattern}笑)|(れ{space_pattern}い{space_pattern}し{space_pattern}ょ{space_pattern}う)){space_pattern}{right_bracket})"
)

# 参考:
# https://tech-blog.s-yoshiki.com/entry/303
blank_symbols = {
    "\u0009",
    "\u000a",
    "\u000b",
    "\u000c",
    "\u000d",
    "\u0020",
    "\u0085",
    "\u00a0",
    "\u1680",
    # "\u2000", # 半角スペース
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2009",
    "\u200a",
    "\u2028",
    "\u2029",
    "\u202f",
    "\u205f",
    # "\u3000", # 全角スペース
    "\u00ad",
    "\u034f",
    "\u061c",
    "\u180e",
    "\u200b",
    "\u200c",
    "\u200d",
    "\u200e",
    "\u200f",
    "\u2060",
    "\u2061",
    "\u2062",
    "\u2063",
    "\u2064",
    "\u2065",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
    "\ufeff",
    "\u115f",
    "\u1160",
    "\u2800",
    "\u3164",
    "\uffa0",
}


def remove_blanks(s: str) -> str:
    result = ""
    for c in s:
        if not (c in blank_symbols):
            result += c
    return result


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
        if reishou_pattern.search(remove_blanks(message.content)):
            await message.add_reaction("\N{REVERSED HAND WITH MIDDLE FINGER EXTENDED}")
            await message.reply(":index_pointing_at_the_viewer:冷笑を検出しました！")

    return bot


token_name = "REISHOU_TOKEN"
