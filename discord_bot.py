from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

import discord
from discord import app_commands

sys.path.insert(0, str(Path(__file__).resolve().parent))
import price_checker as pc

APP_DIR = Path(__file__).resolve().parent
TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
PRICES_PATH = APP_DIR / "prices.json"

intents = discord.Intents.default()

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


def load_prices_cache() -> dict[str, dict]:
    if not PRICES_PATH.exists():
        return {}
    try:
        data = json.loads(PRICES_PATH.read_text(encoding="utf-8"))
        return data.get("items", {})
    except (json.JSONDecodeError, OSError):
        return {}


def price_field(name: str, value: float | None, currency: str, fee: float) -> str:
    if value is None:
        return f"**{name}**: нет цены"
    net = value - value * fee
    sign = pc.CURRENCY_SYMBOLS.get(currency, currency)
    return f"**{name}**: {value:,.2f} {sign} → на руки **{net:,.2f} {sign}**"


def render_result(name: str, entry: dict) -> discord.Embed:
    embed = discord.Embed(title=f"💰 {name}", color=0xF0883E)
    lines = [
        price_field("CS.Market", entry.get("usd"), "usd", pc.FEES["csmarket"]),
        price_field("CS.Market RUB", entry.get("rub"), "rub", pc.FEES["csmarket"]),
        price_field("Steam", entry.get("steam_usd"), "usd", pc.FEES["steam"]),
    ]
    lis_usd, lis_rub = pc.lis_estimate_price(entry.get("usd"), entry.get("rub"))
    if lis_usd is None:
        lines.append("**LIS-Skins**: нет цены")
    else:
        lines.append(f"**LIS-Skins ≈**: {lis_usd:,.2f} $ / {lis_rub:,.2f} ₽ *(оценка)*")
    embed.add_field(name="Цены", value="\n".join(lines), inline=False)
    if entry.get("image"):
        embed.set_thumbnail(url=entry["image"])
    embed.set_footer(text=pc.fmt_ts(entry.get("updated_at")) + " · LIS-Skins — оценка от CS.Market (×0.97)")
    return embed


@tree.command(name="skin", description="Найти цену скина CS2 (название + флот, например: AK-47 Redline FT)")
@app_commands.describe(
    query="Например: AK-47 Redline или AWP Asiimov",
    wear="Флот (необязательно): FN / MW / FT / WW / BS",
)
@app_commands.choices(
    wear=[
        app_commands.Choice(name="Factory New (FN)", value="fn"),
        app_commands.Choice(name="Minimal Wear (MW)", value="mw"),
        app_commands.Choice(name="Field-Tested (FT)", value="ft"),
        app_commands.Choice(name="Well-Worn (WW)", value="ww"),
        app_commands.Choice(name="Battle-Scarred (BS)", value="bs"),
    ]
)
async def skin_cmd(interaction: discord.Interaction, query: str, wear: str | None = None) -> None:
    await interaction.response.defer()
    query, found = await asyncio.to_thread(pc.search_skins, query, wear)

    results: list[discord.Embed] = [render_result(r["name"], r) for r in found]

    if not results:
        await interaction.followup.send(f"Ничего не нашлось по запросу **{query}**. Попробуй точнее, например `AK-47 | Redline (Field-Tested)`")
        return

    if len(results) == 1:
        await interaction.followup.send(embed=results[0])
    else:
        await interaction.followup.send(f"Нашёл {len(results)} вариантов по запросу **{query}**:", embeds=results)


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user} (ID {bot.user.id})")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} commands: {[c.name for c in synced]}")
    except Exception as exc:
        print(f"Command sync failed: {exc}", file=sys.stderr)
    print("Ready. Use /skin <skin name>")


def main() -> None:
    if not TOKEN:
        print(
            "Set DISCORD_BOT_TOKEN environment variable with your bot token.\n"
            "Create a bot at https://discord.com/developers/applications",
            file=sys.stderr,
        )
        raise SystemExit(1)
    bot.run(TOKEN)


if __name__ == "__main__":
    main()