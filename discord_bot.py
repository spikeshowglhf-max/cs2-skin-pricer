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


def search_csmarket_online(query: str) -> list[dict]:
    try:
        prices = pc.fetch_csmarket_prices()
    except Exception:
        return []
    q = query.lower().strip()
    if not q:
        return []
    matches = [{"name": name, **info} for name, info in prices.items() if q in name.lower()]
    return sorted(matches, key=lambda m: m.get("usd") or 10**9)[:6]


def match_steam_online(query: str) -> list[dict]:
    try:
        return [r for r in pc.steam_search(query)[:4]]
    except Exception:
        return []


def price_field(name: str, value: float | None, currency: str, fee: float) -> str:
    if value is None:
        return f"**{name}**: нет цены"
    net = value - value * fee
    sign = pc.CURRENCY_SYMBOLS.get(currency, currency)
    return f"**{name}**: {value:,.2f} {sign} → на руки **{net:,.2f} {sign}**"


def render_result(name: str, entry: dict) -> discord.Embed:
    embed = discord.Embed(title=f"💰 {name}", color=0xF0883E)
    embed.add_field(name="", value=price_field("CS.Market", entry.get("usd"), "usd", pc.FEES["csmarket"]) + "\n" + price_field("CS.Market ₽", entry.get("rub"), "rub", pc.FEES["csmarket"]) + "\n" + price_field("Steam", entry.get("steam_usd"), "usd", pc.FEES["steam"]), inline=False)
    if entry.get("image"):
        embed.set_thumbnail(url=entry["image"])
    embed.add_field(name="", value=pc.fmt_ts(entry.get("updated_at")), inline=False)
    return embed


WEAR_FULL_NAMES = {
    "fn": "Factory New",
    "mw": "Minimal Wear",
    "ft": "Field-Tested",
    "ww": "Well-Worn",
    "bs": "Battle-Scarred",
}


def normalize_query(query: str, wear: str | None) -> str:
    q = re.sub(r"\s+", " ", query.strip())
    if not wear:
        return q
    wear_full = WEAR_FULL_NAMES.get(wear.lower())
    if not wear_full:
        return q
    if "(" in q:
        q = q.rsplit("(", 1)[0].strip()
    return f"{q} ({wear_full})"


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
    query = normalize_query(query, wear)

    cs_items = await asyncio.to_thread(search_csmarket_online, query)
    steam_items = await asyncio.to_thread(match_steam_online, query)

    results: list[discord.Embed] = []
    seen_names: set[str] = set()

    for m in cs_items:
        name = m["name"]
        if name in seen_names:
            continue
        seen_names.add(name)
        steam = next((s for s in steam_items if s["name"].lower() == name.lower()), None)
        if steam:
            m["steam_usd"] = steam["price_usd"]
        results.append(render_result(name, m))
        if len(results) >= 4:
            break

    if len(results) < 4:
        for s in steam_items:
            name = s["name"]
            if name in seen_names:
                continue
            seen_names.add(name)
            entry = {"usd": None, "rub": None, "steam_usd": s["price_usd"], "image": s["image"], "updated_at": pc.local_now().isoformat()}
            results.append(render_result(name, entry))
            if len(results) >= 4:
                break

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