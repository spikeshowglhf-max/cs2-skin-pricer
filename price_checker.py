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
    print(f"Saved {len(prices):,} skins to prices.json")


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