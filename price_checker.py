from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
PRICES_PATH = APP_DIR / "prices.json"
WATCHLIST_PATH = APP_DIR / "watchlist.json"
STATE_PATH = APP_DIR / "state.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CS2SkinPricer/1.0"

STEAM_CSGO_APPID = 730
STEAM_SEARCH_URL = (
    "https://steamcommunity.com/market/search/render/"
    "?query={query}&appid=730&norender=1&count=8"
)
STEAM_ICON_URL = "https://community.fastly.steamstatic.com/economy/image/{url}"

CSMARKET_PRICES_URL = "https://market.csgo.com/api/v2/prices/{currency}.json"

FEES = {
    "steam": 0.15,
    "csmarket": 0.059,
}

LIS_ESTIMATE_FACTOR = 0.97


def lis_estimate_price(usd: float | None, rub: float | None) -> tuple[float | None, float | None]:
    def est(value: float | None) -> float | None:
        return None if value is None else value * LIS_ESTIMATE_FACTOR

    return est(usd), est(rub)

CURRENCY_SYMBOLS = {"rub": "₽", "usd": "$"}

HTML_TAG_RE = re.compile(r"<[^>]+>")
PRICE_TEXT_RE = re.compile(r"(\d{1,3}(?:[\s\xa0\u00a0]\d{3})+|\d+)(?:[.,](\d+))?")


def local_now() -> datetime:
    return datetime.now(timezone.utc)


def fmt_ts(ts_iso: str | None) -> str:
    if not ts_iso:
        return "нет данных"
    try:
        parsed = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        delta = local_now() - parsed
        mins = int(delta.total_seconds() // 60)
        if mins < 1:
            return "только что"
        if mins < 60:
            return f"{mins} мин назад"
        hours = mins // 60
        if hours < 24:
            return f"{hours} ч назад"
        return f"{hours // 24} дн назад"
    except ValueError:
        return ts_iso


def http_get_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_get_json(url: str, timeout: int = 30) -> Any:
    return json.loads(http_get_text(url, timeout))


def post_webhook(url: str, payload: dict[str, Any], timeout: int = 25) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json; charset=utf-8"},
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp.read()
                return
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 4:
                time.sleep(2.5 * (attempt + 1))
                continue
            if 500 <= exc.code < 600 and attempt < 4:
                time.sleep(2**attempt)
                continue
            raise


def parse_price_text(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = HTML_TAG_RE.sub("", str(text)).replace("\xa0", " ")
    match = PRICE_TEXT_RE.search(cleaned)
    if not match:
        return None
    int_part = match.group(1).replace(" ", "").replace("\u00a0", "")
    frac = match.group(2) or ""
    try:
        return float(f"{int_part}.{frac}" if frac else int_part)
    except ValueError:
        return None


def fetch_csmarket_prices() -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for currency in ("RUB", "USD"):
        url = CSMARKET_PRICES_URL.format(currency=currency)
        data = http_get_json(url)
        updated_ts = local_now().isoformat()
        for item in data.get("items", []):
            name = str(item.get("market_hash_name") or "").strip()
            if not name:
                continue
            price = item.get("price")
            try:
                price = float(price)
            except (TypeError, ValueError):
                continue
            entry = merged.setdefault(name, {})
            entry[currency.lower()] = price
            entry["updated_at"] = updated_ts
            image = item.get("image")
            if image:
                entry["image"] = image
    return merged


def steam_search(query: str) -> list[dict[str, Any]]:
    url = STEAM_SEARCH_URL.format(query=urllib.parse.quote(query))
    data = http_get_json(url)
    results: list[dict[str, Any]] = []
    for item in data.get("results", []):
        name = str(item.get("hash_name") or "").strip()
        if not name:
            continue
        price = parse_price_text(item.get("sell_price_text"))
        if price is None:
            continue
        icon_url = ""
        asset = item.get("asset_description") or {}
        if asset.get("icon_url"):
            icon_url = STEAM_ICON_URL.format(url=asset["icon_url"])
        results.append({"name": name, "price_usd": price, "image": icon_url})
    return results


def qty_qty_to_num(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_discord_embed(
    skin_name: str,
    prices: dict[str, Any],
    *,
    changed: bool = False,
    steam_results: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []

    def add_price(name: str, value: float | None, currency: str, fee: float) -> None:
        if value is None:
            fields.append({"name": name, "value": "нет цены", "inline": True})
            return
        net = value - value * fee
        sign = CURRENCY_SYMBOLS.get(currency, currency)
        fields.append(
            {
                "name": name,
                "value": (
                    f"**{value:,.2f} {sign}**\n"
                    f"комиссия −{fee * 100:.1f}% → **на руки {net:,.2f} {sign}**"
                ),
                "inline": True,
            }
        )

    add_price("CS.Market", prices.get("csmarket_usd"), "usd", FEES["csmarket"])
    add_price("CS.Market RUB", prices.get("csmarket_rub"), "rub", FEES["csmarket"])
    add_price("Steam", prices.get("steam_usd"), "usd", FEES["steam"])
    add_price("Steam RUB", prices.get("steam_rub"), "rub", FEES["steam"])

    title = "💰 " + skin_name
    if steam_results and len(steam_results) > 1:
        title += f" (+{len(steam_results) - 1} похожих)"
        alt_lines = [f"• {r['name']} — ${r['price_usd']:.2f}" for r in steam_results[1:4]]
        fields.append({"name": "Похожие варианты", "value": "\n".join(alt_lines), "inline": False})

    return [
        {
            "title": title[:256],
            "color": 0xF0883E if not changed else 0x3FB950,
            "fields": fields,
            "timestamp": local_now().isoformat(),
        }
    ]


def discord_links(embed: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 5,
                    "label": "CS.Market",
                    "url": "https://market.csgo.com/?search=",
                },
                {
                    "type": 2,
                    "style": 5,
                    "label": "Steam",
                    "url": "https://steamcommunity.com/market/search?appid=730&q=",
                },
            ],
        }
    ]


def send_discord(webhook_url: str, skin_name: str, prices: dict[str, Any], **kw: Any) -> None:
    embeds = build_discord_embed(skin_name, prices, **kw)
    payload = {
        "content": "",
        "embeds": embeds,
        "components": discord_links(embeds[0]),
    }
    post_webhook(webhook_url, payload)


def merge_steam_into_prices(prices: dict[str, dict[str, Any]], steam_results: list[dict[str, Any]]) -> None:
    updated_ts = local_now().isoformat()
    for r in steam_results:
        entry = prices.setdefault(r["name"], {"updated_at": updated_ts})
        entry["steam_usd"] = r["price_usd"]
        entry["updated_at"] = updated_ts
        if r["image"] and not entry.get("image"):
            entry["image"] = r["image"]


def save_prices(prices: dict[str, dict[str, Any]], updated_ts: str) -> None:
    payload = {
        "updated_at": updated_ts,
        "generator": "cs2-skin-pricer",
        "items": prices,
    }
    tmp = PRICES_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    tmp.replace(PRICES_PATH)


def load_watchlist() -> list[str]:
    if not WATCHLIST_PATH.exists():
        return []
    try:
        data = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8-sig"))
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, Any]) -> None:
    tmp = STATE_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp.replace(STATE_PATH)


def cmd_full_refresh() -> None:
    print("Fetching CS.Market prices (RUB + USD)...")
    prices = fetch_csmarket_prices()
    updated_ts = local_now().isoformat()
    save_prices(prices, updated_ts)
    n = write_search_index(prices)
    print(f"Saved {len(prices):,} skins to prices.json")
    print(f"Saved {n:,} lines to search_index.tsv")


def cmd_refresh_watchlist(webhook_url: str) -> None:
    watchlist = load_watchlist()
    if not watchlist:
        print("Watchlist is empty. Add skin names to watchlist.json")
        return
    prices = fetch_csmarket_prices()
    updated_ts = local_now().isoformat()

    state = load_state()
    prev = state.get("prices", {})
    changed_sent = 0

    for skin in watchlist:
        exact = prices.get(skin)
        steam_results = []
        if exact is None:
            steam_results = steam_search(skin)
            if steam_results:
                merge_steam_into_prices(prices, steam_results)
        else:
            steam_results = steam_search(skin)
            merge_steam_into_prices(prices, steam_results)

        entry = prices.get(skin)
        if entry is None:
            print(f"[skip] {skin}: not found")
            continue

        current_steam = entry.get("steam_usd")
        old = prev.get(skin, {})
        old_steam = old.get("steam_usd")
        changed = old_steam is not None and current_steam is not None and abs(float(current_steam) - float(old_steam)) >= 0.01

        if changed:
            send_discord(webhook_url, skin, entry, changed=True, steam_results=steam_results)
            changed_sent += 1
            print(f"[sent] {skin}: steam ${current_steam} (was ${old_steam})")

    state["prices"] = {skin: prices.get(skin, {}) for skin in watchlist}
    state["updated_at"] = updated_ts
    save_state(state)
    save_prices(prices, updated_ts)
    print(f"Watchlist checked: {len(watchlist)} skins, sent {changed_sent} changes")


def cmd_lookup(webhook_url: str, query: str) -> None:
    prices = fetch_csmarket_prices()
    steam_results = steam_search(query)

    matches = [m for m in steam_results if m["name"].lower() == query.lower().strip()]
    if matches:
        steam_results.insert(0, matches[0])
        steam_results = [r for i, r in enumerate(steam_results) if r is not matches[0] or i == 0]

    if not steam_results:
        print(f"No results for {query!r}")
        return

    best = steam_results[0]
    skin = best["name"]
    entry = prices.get(skin, {"updated_at": local_now().isoformat()})
    if best["price_usd"] is not None:
        entry["steam_usd"] = best["price_usd"]
        entry["steam_rub"] = best["price_usd"] * get_usd_rate()
    if best["image"]:
        entry["image"] = best["image"]

    send_discord(webhook_url, skin, entry, steam_results=steam_results)
    print(f"Sent Discord report for {skin}")


USD_RATE_CACHE: list[float] = []


def get_usd_rate() -> float:
    if USD_RATE_CACHE:
        return USD_RATE_CACHE[0]
    try:
        data = http_get_json("https://open.er-api.com/v6/latest/USD", timeout=20)
        rate = float(data["rates"]["RUB"])
        USD_RATE_CACHE.append(rate)
        return rate
    except Exception:
        return 88.0


# --- RU->EN query translation & search (shared with Discord bot) ---

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
    if re.search(r"[а-яА-ЯёЁ]", q):
        return q
    if not wear:
        return q
    wear_full = WEAR_FULL_NAMES.get(wear.lower())
    if not wear_full:
        return q
    if "(" in q:
        q = q.rsplit("(", 1)[0].strip()
    return f"{q} ({wear_full})"


def search_csmarket_online(query: str) -> list[dict[str, Any]]:
    prices = fetch_csmarket_prices()
    q = query.lower().strip()
    if not q or re.search(r"[а-яё]", q):
        return []
    q_flat = re.sub(r"[^a-z0-9]+", "", q)
    words = [w for w in re.split(r"[^a-z0-9]+", q) if len(w) >= 2]
    matches: list[dict[str, Any]] = []
    for name, info in prices.items():
        n_flat = re.sub(r"[^a-z0-9]+", "", name.lower())
        if q_flat and q_flat in n_flat:
            matches.append({"name": name, **info})
        elif len(words) >= 2 and all(w in n_flat for w in words):
            matches.append({"name": name, **info})
    return sorted(matches, key=lambda m: m.get("usd") or 10**9)[:6]


def match_steam_online(query: str) -> list[dict[str, Any]]:
    try:
        return steam_search(query)[:4]
    except Exception:
        return []


def search_skins(query: str, wear: str | None = None) -> tuple[str, list[dict[str, Any]]]:
    query = normalize_query(query, wear)
    cs_items = search_csmarket_online(query)
    steam_items = match_steam_online(query)
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in cs_items:
        name = m["name"]
        if name in seen:
            continue
        seen.add(name)
        steam = next((s for s in steam_items if s["name"].lower() == name.lower()), None)
        if steam:
            m["steam_usd"] = steam["price_usd"]
        results.append(m)
        if len(results) >= 4:
            break
    if len(results) < 4:
        for s in steam_items:
            name = s["name"]
            if name in seen:
                continue
            seen.add(name)
            results.append(
                {
                    "name": name,
                    "usd": None,
                    "rub": None,
                    "steam_usd": s["price_usd"],
                    "image": s["image"],
                    "updated_at": local_now().isoformat(),
                }
            )
            if len(results) >= 4:
                break
    return query, results


SEARCH_INDEX_PATH = APP_DIR / "search_index.tsv"


def write_search_index(prices: dict[str, dict[str, Any]]) -> int:
    lines: list[str] = []
    for name, info in prices.items():
        flat = re.sub(r"[^a-z0-9]+", "", name.lower())
        if not flat:
            continue
        usd = info.get("usd")
        rub = info.get("rub")
        usd_s = f"{usd:.2f}" if isinstance(usd, (int, float)) else ""
        rub_s = f"{rub:.2f}" if isinstance(rub, (int, float)) else ""
        lines.append(f"{flat}\t{name}\t{usd_s}\t{rub_s}")
    tmp = SEARCH_INDEX_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    tmp.replace(SEARCH_INDEX_PATH)
    return len(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="CS2 skin price checker with Discord webhook")
    parser.add_argument("command", choices=("refresh", "watch", "lookup"))
    parser.add_argument("--query", help="Skin name to look up")
    parser.add_argument("--webhook", default=os.environ.get("DISCORD_WEBHOOK_URL", ""), help="Discord webhook URL")
    args = parser.parse_args()

    if args.command == "refresh":
        cmd_full_refresh()
        return 0

    webhook = args.webhook.strip()
    if not webhook or "discord.com/api/webhooks/" not in webhook:
        print("Set DISCORD_WEBHOOK_URL or pass --webhook with a Discord webhook URL", file=sys.stderr)
        return 2

    if args.command == "watch":
        cmd_refresh_watchlist(webhook)
        return 0

    if args.command == "lookup":
        if not args.query:
            print("--query is required for lookup", file=sys.stderr)
            return 2
        cmd_lookup(webhook, args.query)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())