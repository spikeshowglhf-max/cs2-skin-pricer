"""Build ru_dict.json: Russian names for ALL CS2 skin patterns.

Pattern sources (union):
  1. CS.Market prices/RUB.json — live list of every skin on the market,
     so brand-new skins are picked up automatically as soon as they appear.
  2. Official csgo_english.txt (SteamDatabase/GameTracking-CS2) — canonical
     pattern names.
Each unique pattern is translated en->ru via Google Translate (gtx, no key).
The weapon word is kept in English and translated at runtime by the curated
RU_GUNS/RU_KNIVES tables.

Output: {"RU pattern": "EN pattern", ...} — used by price_checker.py (sync)
and worker.js (Cloudflare, fetched from GitHub raw).
"""

from __future__ import annotations

import concurrent.futures
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
OUT_PATH = APP_DIR / "ru_dict.json"

CSGO_ENGLISH_URL = (
    "https://raw.githubusercontent.com/SteamDatabase/GameTracking-CS2/"
    "master/game/csgo/pak01_dir/resource/csgo_english.txt"
)
CSMARKET_URL = "https://market.csgo.com/api/v2/prices/RUB.json"

GTX_URL = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q={q}"

PREFIXES = ("StatTrak™ ", "Souvenir ", "★ ")

NON_SKIN_WORDS = (
    "music kit", "sticker", "charm", "graffiti", "agent", "patch",
    "souvenir package", "collectible", "case", "capsule", "emblem",
)

LOC_KEY_RE = re.compile(r'^\s*"([^"]+)"\s+"([^"]*)"\s*$')


def fetch(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CS2SkinPricer/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_paint_kits(text: str) -> set[str]:
    patterns: set[str] = set()
    for line in text.splitlines():
        m = LOC_KEY_RE.match(line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if not (key.startswith("PaintKit_") and key.endswith("_Tag")):
            continue
        name = value.strip()
        if name and name != "Unnamed Paint Kit":
            patterns.add(name)
    return patterns


def parse_csmarket(data: list) -> set[str]:
    patterns: set[str] = set()
    for item in data:
        if isinstance(item, dict):
            name = str(item.get("market_hash_name") or "")
        elif isinstance(item, (list, tuple)) and item:
            name = str(item[0])
        else:
            continue
        if " | " not in name:
            continue
        for prefix in PREFIXES:
            if name.startswith(prefix):
                name = name[len(prefix) :]
                break
        weapon, pattern = name.split(" | ", 1)
        weapon = weapon.strip()
        pattern = re.sub(r"\s*\([^)]*\)\s*$", "", pattern).strip()
        if not pattern:
            continue
        weapon_low = weapon.lower()
        if "(" in weapon or any(w in weapon_low for w in NON_SKIN_WORDS):
            continue
        patterns.add(pattern)
    return patterns


def translate_one(pattern: str) -> str | None:
    url = GTX_URL.format(q=urllib.parse.quote(pattern))
    for attempt in range(3):
        try:
            data = json.loads(fetch(url))
            parts = data[0]
            if not parts or not parts[0]:
                return None
            text = "".join(p[0] or "" for p in parts if isinstance(p, list))
            text = text.strip()
            return text or None
        except (OSError, ValueError, IndexError):
            if attempt < 2:
                time.sleep(1.0 + attempt)
    return None


def main() -> int:
    patterns: set[str] = set()
    try:
        print("fetching csgo_english.txt ...")
        patterns |= parse_paint_kits(fetch(CSGO_ENGLISH_URL))
    except OSError as exc:
        print(f"localization fetch failed: {exc}")
    try:
        print("fetching CS.Market prices ...")
        data = json.loads(fetch(CSMARKET_URL))
        patterns |= parse_csmarket(data.get("items", []))
    except (OSError, ValueError) as exc:
        print(f"csmarket fetch failed: {exc}")
    print(f"unique patterns: {len(patterns)}")

    ru_to_en: dict[str, str] = {}
    failed: list[str] = []

    def work(pattern: str) -> tuple[str | None, str]:
        ru = translate_one(pattern)
        return (ru, pattern)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(work, p): p for p in sorted(patterns)}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            ru, pattern = fut.result()
            if ru and re.search(r"[а-яА-ЯёЁ]", ru) and ru != pattern:
                ru_low = ru.lower()
                if ru_low not in ru_to_en:
                    ru_to_en[ru_low] = pattern
            else:
                failed.append(pattern)
            if i % 100 == 0:
                print(f"  {i}/{len(patterns)}")

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(ru_to_en, f, ensure_ascii=False, indent=0, sort_keys=True)

    print(f"translated: {len(ru_to_en)}, failed: {len(failed)}")
    if failed:
        print("failed samples:", ", ".join(failed[:10]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())