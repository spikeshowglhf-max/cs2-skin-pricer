"""Build ru_dict.json: Russian names for ALL CS2 skin patterns.

Source: official csgo_english.txt (SteamDatabase/GameTracking-CS2) for the full
list of EN pattern names, then Google Translate (gtx, no key) en->ru for each
unique pattern. The weapon word is kept in English and translated at runtime
by the curated RU_GUNS/RU_KNIVES tables.

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

GTX_URL = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q={q}"


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
    print("fetching csgo_english.txt ...")
    text = fetch(CSGO_ENGLISH_URL)
    patterns = parse_paint_kits(text)
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