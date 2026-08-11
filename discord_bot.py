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
    if not q or re.search(r"[а-яё]", q):
        return []
    q_flat = re.sub(r"[^a-z0-9]+", "", q)
    words = [w for w in re.split(r"[^a-z0-9]+", q) if len(w) >= 2]
    matches: list[dict] = []
    for name, info in prices.items():
        n_flat = re.sub(r"[^a-z0-9]+", "", name.lower())
        if q_flat and q_flat in n_flat:
            matches.append({"name": name, **info})
        elif len(words) >= 2 and all(w in n_flat for w in words):
            matches.append({"name": name, **info})
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
    lines = [
        price_field("CS.Market", entry.get("usd"), "usd", pc.FEES["csmarket"]),
        price_field("CS.Market RUB", entry.get("rub"), "rub", pc.FEES["csmarket"]),
        price_field("Steam", entry.get("steam_usd"), "usd", pc.FEES["steam"]),
    ]
    embed.add_field(name="Цены", value="\n".join(lines), inline=False)
    if entry.get("image"):
        embed.set_thumbnail(url=entry["image"])
    embed.set_footer(text=pc.fmt_ts(entry.get("updated_at")))
    return embed


WEAR_FULL_NAMES = {
    "fn": "Factory New",
    "mw": "Minimal Wear",
    "ft": "Field-Tested",
    "ww": "Well-Worn",
    "bs": "Battle-Scarred",
}

RU_WEAR = {
    "прямо с завода": "Factory New",
    "немного поношенное": "Minimal Wear",
    "после полевых испытаний": "Field-Tested",
    "полевых испытаний": "Field-Tested",
    "поношенное": "Well-Worn",
    "закалённое в боях": "Battle-Scarred",
}

RU_WEAR_SHORT = {
    "фн": "fn",
    "fn": "fn",
    "нп": "mw",
    "mw": "mw",
    "мв": "mw",
    "ппи": "ft",
    "пп": "ft",
    "фт": "ft",
    "ft": "ft",
    "п": "ww",
    "ww": "ww",
    "звб": "bs",
    "бс": "bs",
    "bs": "bs",
}

RU_KNIVES = {
    "нож выживания": "Survival Knife",
    "керамбит": "Karambit",
    "карамбит": "Karambit",
    "нож-бабочка": "Butterfly Knife",
    "крюк-нож": "Kukri Knife",
    "нож-кукри": "Kukri Knife",
    "когти-нож": "Talon Knife",
    "коготь-нож": "Talon Knife",
    "стилет-нож": "Stiletto Knife",
    "стилет": "Stiletto Knife",
    "штык-нож м9": "M9 Bayonet",
    "штык-нож": "Bayonet",
    "охотничий нож": "Hunting Knife",
    "нож охотника": "Hunting Knife",
    "нож рыбака": "Bowie Knife",
    "тесак": "Bowie Knife",
    "нож-волк": "Ursus Knife",
    "лук-нож": "Navaja Knife",
    "нож-лук": "Navaja Knife",
    "скелетон-нож": "Skeleton Knife",
    "нож-скелетон": "Skeleton Knife",
    "классический кинжал": "Classic Knife",
    "фехтовальщик": "Falchion Knife",
    "кунг-фу": "Falchion Knife",
    "кинжал уличной банды": "Gut Knife",
    "нож классик": "Classic Knife",
    "три-фоут": "Paracord Knife",
    "нож-паракорд": "Paracord Knife",
    "нож амфибия": "Nomad Knife",
    "кочевника": "Nomad Knife",
}

RU_PATTERNS = {
    "ночная полоса": "Night Stripe",
    "ночной полосой": "Night Stripe",
    "малиновый узор": "Crimson Web",
    "малиновая паутина": "Crimson Web",
    "кровавая паутина": "Crimson Web",
    "в паутине": "Crimson Web",
    "градиент": "Fade",
    "перелив": "Fade",
    "фейд": "Fade",
    "феил": "Fade",
    "доплер": "Doppler",
    "фаза": "Phase",
    "закалка": "Case Hardened",
    "каленый": "Case Hardened",
    "бойня": "Slaughter",
    "тигриный зуб": "Tiger Tooth",
    "мраморный градиент": "Marble Fade",
    "марбл фад": "Marble Fade",
    "предание": "Lore",
    "гамма-доплер": "Gamma Doppler",
    "автоматик": "Autotronic",
    "изумруд": "Emerald",
    "рубин": "Ruby",
    "сапфир": "Sapphire",
    "чёрный жемчуг": "Black Pearl",
    "янтарь": "Amber Fade",
    "ночь": "Night",
    "зимняя ночь": "Winter Night",
    "синяя сталь": "Blue Steel",
    "ультрафиолет": "Ultraviolet",
    "дамасская сталь": "Damascus Steel",
    "ржавчина": "Rust Coat",
    "рж авый": "Rust Coat",
    "светлая вода": "Bright Water",
    "сафари": "Safari Mesh",
    "маскировка": "Forest DDPAT",
    "джангл": "Jungle DDPAT",
    "бурый след": "DDPAT",
    "песчаная дюна": "Sand Dune",
    "костяная маска": "Bone Mask",
    "классический городской": "Urban Masked",
    "следы краски": "Stained",
    "гамма-волны": "Gamma Waves",
    "смертоносная змея": "Death By Snake",
    "джайпур": "Jaipur",
    "смеш": "Sport Gloves",
    "спортивные перчатки": "Sport Gloves",
    "перчатки мотор": "Motivational Gloves",
    "кованые перчатки": "Wraps",
    "плетёные перчатки": "Wraps",
    "перчатки-обмотки": "Wraps",
    "спецрезерв": "Specialist Gloves",
    "перчатки специалиста": "Specialist Gloves",
    "четыре гаечных": "Hand Wraps",
    "повязки": "Hand Wraps",
    "перчатки кровавого давления": "Bloodhound Gloves",
    "кровавый гончий": "Bloodhound Gloves",
    "кровавый спорт": "Blood Sport",
    "красная линия": "Redline",
    "азимов": "Asiimov",
    "асимов": "Asiimov",
    "вулкан": "Vulcan",
    "неоновая революция": "Neon Revolution",
    "неон революция": "Neon Revolution",
    "медуза": "Medusa",
    "гидра": "Hydra",
    "драконовый лор": "Dragon Lore",
    "дракон лор": "Dragon Lore",
    "лор": "Dragon Lore",
    "убийца драконов": "Blaze",
    "вепрь": "Fire Serpent",
    "огненный змей": "Fire Serpent",
    "золотая змея": "Golden Snake",
    "золотой кот": "Gold Coil",
    "хищник": "Predator",
    "песчаная дюна": "Sand Dune",
    "территория": "Territory",
    "император": "Emperor",
    "империл": "Emperor",
    "смертельная маска": "Death Mask",
    "маска смерти": "Death Mask",
    "снежный леопард": "Snow Leopard",
    "ледяной дракон": "Icy Dragon",
    "бенгальский тигр": "Bengal Tiger",
    "мутаген": "Mutiny",
    "пандемониум": "Pandamonium",
    "голубая молния": "Lightning Strike",
    "удар молнии": "Lightning Strike",
    "гипербит": "Hyper Beast",
    "гипер-зверь": "Hyper Beast",
    "зверь": "Hyper Beast",
    "извилистая": "Hot Rod",
    "горячий род": "Hot Rod",
    "джаггернаут": "Juggernaut",
    "проклятие": "Curse",
}

RU_GUNS = {
    "ак-47": "AK-47",
    "ак47": "AK-47",
    "калаш": "AK-47",
    "авп": "AWP",
    "м4а4": "M4A4",
    "пустынный орёл": "Desert Eagle",
    "дезерт игл": "Desert Eagle",
    "дигл": "Desert Eagle",
    "дегл": "Desert Eagle",
    "усп": "USP-S",
    "глок": "Glock-18",
    "фамас": "FAMAS",
    "галиль": "Galil AR",
    "маг-7": "MAG-7",
    "п90": "P90",
    "нэгвар": "Negev",
    "ск20": "SCAR-20",
    "автопушка": "AWP",
}

RU_MISC = {
    "нож": "",
    "перчатки": "",
    "(после полевых испытаний)": "",
}


def _sub_all(text: str, table: dict[str, str]) -> str:
    low = text.lower()
    for ru, en in table.items():
        if ru.lower() in low:
            text = re.sub(re.escape(ru), en, text, flags=re.IGNORECASE)
    return text


def ru_to_en(query: str) -> str:
    q = re.sub(r"\s+", " ", query.strip())
    translated = _sub_all(q, RU_WEAR)
    translated = _sub_all(translated, RU_GUNS)
    for ru, en in RU_KNIVES.items():
        if ru.lower() in translated.lower():
            translated = re.sub(re.escape(ru), en, translated, flags=re.IGNORECASE)
            break
    translated = _sub_all(translated, RU_PATTERNS)
    return re.sub(r"\s+", " ", translated).strip()


def normalize_query(query: str, wear: str | None) -> str:
    translated = ru_to_en(query)
    q = re.sub(r"\s+", " ", translated.strip())
    if not wear:
        tokens = re.findall(r"(?<![a-zа-я])[a-zа-я]{1,4}(?![a-zа-я])", q.lower())
        for tok in tokens:
            if tok in RU_WEAR_SHORT:
                wear = RU_WEAR_SHORT[tok]
                q = re.sub(r"(?<![a-zа-я])" + re.escape(tok) + r"(?![a-zа-я])", " ", q, flags=re.IGNORECASE)
                q = re.sub(r"\s+", " ", q).strip()
                break
    is_cyrillic = bool(re.search(r"[а-яА-ЯёЁ]", q))
    if is_cyrillic:
        return q
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