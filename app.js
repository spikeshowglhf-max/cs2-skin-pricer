"use strict";

const PRICES_URL =
  "https://raw.githubusercontent.com/spikeshowglhf-max/cs2-skin-pricer/main/prices.json";
const STEAM_SEARCH_URL = (q) =>
  `https://steamcommunity.com/market/search/render/?query=${encodeURIComponent(q)}&appid=730&norender=1&count=8`;
const FEES = {
  steam: 0.15,
  csmarket: 0.059,
};
const CURRENCY_SIGN = {
  rub: "₽",
  usd: "$",
};

let priceIndex = null;

const statusEl = document.getElementById("status");
const searchInput = document.getElementById("search");
const searchBtn = document.getElementById("search-btn");
const resultsEl = document.getElementById("results");

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = "status" + (cls ? " " + cls : "");
}

async function loadPrices() {
  const cacheName = "cs2-price-cache-v1";
  let cache = null;
  try {
    cache = await caches.open(cacheName);
    const cached = await cache.match(PRICES_URL);
    if (cached && !navigator.onLine) return await cached.json();
  } catch (_) {
    /* caches могут быть недоступны */
  }

  const resp = await fetch(PRICES_URL, { cache: "no-store" });
  const data = await resp.json();
  try {
    if (cache) await cache.put(PRICES_URL, new Response(JSON.stringify(data)));
  } catch (_) { /* ignore */ }
  return data;
}

function searchIndex(query, index) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const items = Object.entries(index.items || {});
  const out = [];
  for (const [name, info] of items) {
    if (name.toLowerCase().includes(q)) {
      out.push({ name, ...info });
      if (out.length >= 25) break;
    }
  }
  return out;
}

function netAmount(price, fee) {
  return price - price * fee;
}

function makePriceTag(label, price, currency, fee) {
  const net = netAmount(price, fee);
  const sign = CURRENCY_SIGN[currency] || currency;
  return `
    <div class="price-tag">
      <b>${label}</b> ${price.toLocaleString("ru-RU")} ${sign}
      <br><span class="fee">комиссия −${(fee * 100).toFixed(1)}%</span>
      <br><span class="net">≈ получите ${net.toLocaleString("ru-RU")} ${sign}</span>
    </div>`;
}

function renderResults(query, csItems) {
  if (query && !csItems.length) {
    resultsEl.innerHTML = `<div class="no-results">Ничего не нашлось. Проверь название: например <b>AK-47 | Redline (Field-Tested)</b></div>`;
    return;
  }

  const html = csItems
    .map((item) => {
      const tags = [];
      const hasCs = item.csmarket && item.csmarket.usd;
      const hasSteam = item.steam && item.steam.usd;

      if (hasCs) {
        const { usd, rub } = item.csmarket;
        tags.push(makePriceTag("CS.Market", usd, "usd", FEES.csmarket));
        if (rub) tags.push(makePriceTag("CS.Market RUB", rub, "rub", FEES.csmarket));
      }
      if (hasSteam) {
        const { usd, rub } = item.steam;
        tags.push(makePriceTag("Steam", usd, "usd", FEES.steam));
        if (rub) tags.push(makePriceTag("Steam RUB", rub, "rub", FEES.steam));
      }
      if (!tags.length) tags.push(`<div class="price-tag">нет цены</div>`);

      const freshness = item.updated_at
        ? `<div class="ribbon ${isFresh(item.updated_at)}">${formatFresh(item.updated_at)}</div>`
        : "";
      const img = item.csmarket && item.csmarket.image
        ? item.csmarket.image
        : item.steam && item.steam.image
          ? item.steam.image
          : "";

      return `
        <div class="item-card">
          ${img ? `<img src="${img}" alt="">` : ""}
          <div class="item-info">
            <div class="item-name">${escapeHtml(item.name)}</div>
            <div class="item-prices">${tags.join("")}</div>
          </div>
          ${freshness}
        </div>`;
    })
    .join("");

  resultsEl.innerHTML = html;
}

async function searchSteamLive(names) {
  const results = {};
  await Promise.all(
    names.map(async (name) => {
      try {
        const resp = await fetch(STEAM_SEARCH_URL(name), {
          headers: { "User-Agent": "Mozilla/5.0" },
        });
        if (!resp.ok) return;
        const data = await resp.json();
        for (const r of (data.results || []).slice(0, 3)) {
          const key = (r.hash_name || "").trim();
          const priceUsd = parsePriceUsd(r.sell_price_text);
          if (!key || priceUsd == null) continue;
          results[key] = {
            ...(results[key] || {}),
            steam: {
              usd: priceUsd,
              image: r.asset_description && r.asset_description.icon_url
                ? `https://community.fastly.steamstatic.com/economy/image/${r.asset_description.icon_url}`
                : "",
              updated_at: new Date().toISOString(),
            },
          };
        }
      } catch (_) { /* live search не работает — показываем кеш */ }
    })
  );
  return results;
}

function parsePriceUsd(text) {
  if (!text) return null;
  const m = text.replace(/\s/g, "").match(/(\d+[.,]\d+|\d+)/);
  if (!m) return null;
  return parseFloat(m[1].replace(",", "."));
}

async function doSearch() {
  const query = searchInput.value.trim();
  if (!query) return;

  searchBtn.disabled = true;
  searchBtn.innerHTML = `<span class="spinner"></span>Ищу…`;

  let csItems = [];
  if (priceIndex) {
    csItems = searchIndex(query, priceIndex);
    renderResults(query, csItems);
  }

  const csNames = csItems.map((i) => i.name);
  const liveSteam = await searchSteamLive(csNames.length ? csNames : [query]);

  if (Object.keys(liveSteam).length) {
    const merged = csItems
      .map((item) => ({
        ...item,
        steam: liveSteam[item.name] ? liveSteam[item.name].steam : item.steam,
      }))
      .filter((item) => item.csmarket || liveSteam[item.name]);
    const extra = Object.entries(liveSteam)
      .filter(([name]) => !csItems.some((i) => i.name === name))
      .map(([name, info]) => ({ name, ...info }));
    renderResults(query, [...merged, ...extra]);
  }

  searchBtn.disabled = false;
  searchBtn.textContent = "Найти";
}

function formatFresh(iso) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "только что";
  if (mins < 60) return `${mins} мин назад`;
  return `${Math.round(mins / 60)} ч назад`;
}

function isFresh(iso) {
  return Date.now() - new Date(iso).getTime() < 3 * 3600 * 1000 ? "fresh" : "";
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

(async function init() {
  try {
    const idx = await loadPrices();
    priceIndex = idx;
    const total = Object.keys(idx.items || {}).length;
    const mins = Math.round((Date.now() - new Date(idx.updated_at || 0).getTime()) / 60000);
    setStatus(`Прайс загружен: ${total.toLocaleString("ru-RU")} скинов, цены ${formatFresh(idx.updated_at)}`, "ok");
  } catch (err) {
    setStatus("Не удалось загрузить прайс. Проверь интернет.", "err");
  }

  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doSearch();
  });
  searchBtn.addEventListener("click", doSearch);
})();