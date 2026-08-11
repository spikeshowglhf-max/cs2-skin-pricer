// cs2-skin-pricer — Cloudflare Worker
// Discord slash command /skin via HTTP interactions (no PC needed).
// Deploy: create a Worker on dash.cloudflare.com, paste this file,
// then set INTERACTIONS_ENDPOINT_URL in Discord Developer Portal
// to https://<worker-name>.<your-subdomain>.workers.dev

const GITHUB_RAW = 'https://raw.githubusercontent.com/spikeshowglhf-max/cs2-skin-pricer/main/search_index.tsv';
const STEAM_SEARCH = 'https://steamcommunity.com/market/search/render/?query={q}&appid=730&norender=1&count=8';
const STEAM_ICON = 'https://community.fastly.steamstatic.com/economy/image/{url}';

const FEES = { steam: 0.15, csmarket: 0.059 };
const LIS_FACTOR = 0.97;
const CURRENCY = { rub: '\u20BD', usd: '$' };

const WEAR_FULL = {
  fn: 'Factory New',
  mw: 'Minimal Wear',
  ft: 'Field-Tested',
  ww: 'Well-Worn',
  bs: 'Battle-Scarred',
};

const RU_WEAR = {
  'прямо с завода': 'Factory New',
  'немного поношенное': 'Minimal Wear',
  'после полевых испытаний': 'Field-Tested',
  'полевых испытаний': 'Field-Tested',
  'поношенное': 'Well-Worn',
  'закалённое в боях': 'Battle-Scarred',
};

const RU_WEAR_SHORT = {
  'фн': 'fn', 'fn': 'fn',
  'нп': 'mw', 'mw': 'mw', 'мв': 'mw',
  'ппи': 'ft', 'пп': 'ft', 'фт': 'ft', 'ft': 'ft',
  'п': 'ww', 'ww': 'ww',
  'звб': 'bs', 'бс': 'bs', 'bs': 'bs',
};

const RU_KNIVES = {
  'нож выживания': 'Survival Knife',
  'керамбит': 'Karambit',
  'карамбит': 'Karambit',
  'нож-бабочка': 'Butterfly Knife',
  'крюк-нож': 'Kukri Knife',
  'нож-кукри': 'Kukri Knife',
  'когти-нож': 'Talon Knife',
  'коготь-нож': 'Talon Knife',
  'стилет-нож': 'Stiletto Knife',
  'стилет': 'Stiletto Knife',
  'штык-нож м9': 'M9 Bayonet',
  'штык-нож': 'Bayonet',
  'охотничий нож': 'Hunting Knife',
  'нож охотника': 'Hunting Knife',
  'нож рыбака': 'Bowie Knife',
  'тесак': 'Bowie Knife',
  'нож-волк': 'Ursus Knife',
  'лук-нож': 'Navaja Knife',
  'нож-лук': 'Navaja Knife',
  'скелетон-нож': 'Skeleton Knife',
  'нож-скелетон': 'Skeleton Knife',
  'классический кинжал': 'Classic Knife',
  'фехтовальщик': 'Falchion Knife',
  'кунг-фу': 'Falchion Knife',
  'кинжал уличной банды': 'Gut Knife',
  'нож классик': 'Classic Knife',
  'три-фоут': 'Paracord Knife',
  'нож-паракорд': 'Paracord Knife',
  'нож амфибия': 'Nomad Knife',
  'кочевника': 'Nomad Knife',
};

const RU_PATTERNS = {
  'ночная полоса': 'Night Stripe',
  'ночной полосой': 'Night Stripe',
  'малиновый узор': 'Crimson Web',
  'малиновая паутина': 'Crimson Web',
  'кровавая паутина': 'Crimson Web',
  'в паутине': 'Crimson Web',
  'градиент': 'Fade',
  'перелив': 'Fade',
  'фейд': 'Fade',
  'феил': 'Fade',
  'доплер': 'Doppler',
  'фаза': 'Phase',
  'закалка': 'Case Hardened',
  'каленый': 'Case Hardened',
  'бойня': 'Slaughter',
  'тигриный зуб': 'Tiger Tooth',
  'мраморный градиент': 'Marble Fade',
  'марбл фад': 'Marble Fade',
  'предание': 'Lore',
  'гамма-доплер': 'Gamma Doppler',
  'автоматик': 'Autotronic',
  'изумруд': 'Emerald',
  'рубин': 'Ruby',
  'сапфир': 'Sapphire',
  'чёрный жемчуг': 'Black Pearl',
  'янтарь': 'Amber Fade',
  'ночь': 'Night',
  'зимняя ночь': 'Winter Night',
  'синяя сталь': 'Blue Steel',
  'ультрафиолет': 'Ultraviolet',
  'дамасская сталь': 'Damascus Steel',
  'ржавчина': 'Rust Coat',
  'рж авый': 'Rust Coat',
  'светлая вода': 'Bright Water',
  'сафари': 'Safari Mesh',
  'маскировка': 'Forest DDPAT',
  'джангл': 'Jungle DDPAT',
  'бурый след': 'DDPAT',
  'песчаная дюна': 'Sand Dune',
  'костяная маска': 'Bone Mask',
  'классический городской': 'Urban Masked',
  'следы краски': 'Stained',
  'гамма-волны': 'Gamma Waves',
  'смертоносная змея': 'Death By Snake',
  'джайпур': 'Jaipur',
  'смеш': 'Sport Gloves',
  'спортивные перчатки': 'Sport Gloves',
  'перчатки мотор': 'Motivational Gloves',
  'кованые перчатки': 'Wraps',
  'плетёные перчатки': 'Wraps',
  'перчатки-обмотки': 'Wraps',
  'спецрезерв': 'Specialist Gloves',
  'перчатки специалиста': 'Specialist Gloves',
  'четыре гаечных': 'Hand Wraps',
  'повязки': 'Hand Wraps',
  'перчатки кровавого давления': 'Bloodhound Gloves',
  'кровавый гончий': 'Bloodhound Gloves',
  'кровавый спорт': 'Blood Sport',
  'красная линия': 'Redline',
  'азимов': 'Asiimov',
  'асимов': 'Asiimov',
  'вулкан': 'Vulcan',
  'неоновая революция': 'Neon Revolution',
  'неон революция': 'Neon Revolution',
  'медуза': 'Medusa',
  'гидра': 'Hydra',
  'драконовый лор': 'Dragon Lore',
  'дракон лор': 'Dragon Lore',
  'лор': 'Dragon Lore',
  'убийца драконов': 'Blaze',
  'вепрь': 'Fire Serpent',
  'огненный змей': 'Fire Serpent',
  'золотая змея': 'Golden Snake',
  'золотой кот': 'Gold Coil',
  'хищник': 'Predator',
  'территория': 'Territory',
  'император': 'Emperor',
  'империл': 'Emperor',
  'смертельная маска': 'Death Mask',
  'маска смерти': 'Death Mask',
  'снежный леопард': 'Snow Leopard',
  'ледяной дракон': 'Icy Dragon',
  'бенгальский тигр': 'Bengal Tiger',
  'мутаген': 'Mutiny',
  'пандемониум': 'Pandamonium',
  'голубая молния': 'Lightning Strike',
  'удар молнии': 'Lightning Strike',
  'гипербит': 'Hyper Beast',
  'гипер-зверь': 'Hyper Beast',
  'зверь': 'Hyper Beast',
  'извилистая': 'Hot Rod',
  'горячий род': 'Hot Rod',
  'джаггернаут': 'Juggernaut',
  'проклятие': 'Curse',
};

const RU_GUNS = {
  'ак-47': 'AK-47',
  'ак47': 'AK-47',
  'калаш': 'AK-47',
  'авп': 'AWP',
  'м4а4': 'M4A4',
  'пустынный орёл': 'Desert Eagle',
  'дезерт игл': 'Desert Eagle',
  'дигл': 'Desert Eagle',
  'дегл': 'Desert Eagle',
  'усп': 'USP-S',
  'глок': 'Glock-18',
  'фамас': 'FAMAS',
  'галиль': 'Galil AR',
  'маг-7': 'MAG-7',
  'п90': 'P90',
  'нэгвар': 'Negev',
  'ск20': 'SCAR-20',
  'автопушка': 'AWP',
};

function subAll(text, table) {
  const low = text.toLowerCase();
  for (const [ru, en] of Object.entries(table)) {
    if (low.includes(ru.toLowerCase())) {
      text = text.replace(new RegExp(escapeRegex(ru), 'gi'), en);
    }
  }
  return text;
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function ruToEn(query) {
  let q = query.trim().replace(/\s+/g, ' ');
  q = subAll(q, RU_WEAR);
  q = subAll(q, RU_GUNS);
  for (const [ru, en] of Object.entries(RU_KNIVES)) {
    if (q.toLowerCase().includes(ru.toLowerCase())) {
      q = q.replace(new RegExp(escapeRegex(ru), 'gi'), en);
      break;
    }
  }
  q = subAll(q, RU_PATTERNS);
  return q.trim().replace(/\s+/g, ' ');
}

function hasCyrillic(s) {
  return /[а-яА-ЯёЁ]/.test(s);
}

function normalizeQuery(query, wear) {
  let q = ruToEn(query);
  if (!wear) {
    const tokens = q.toLowerCase().match(/(?<![a-zа-я])[a-zа-я]{1,4}(?![a-zа-я])/g) || [];
    for (const tok of tokens) {
      if (RU_WEAR_SHORT[tok]) {
        wear = RU_WEAR_SHORT[tok];
        q = q.replace(new RegExp('(?<![a-zа-я])' + escapeRegex(tok) + '(?![a-zа-я])', 'gi'), ' ');
        q = q.trim().replace(/\s+/g, ' ');
        break;
      }
    }
  }
  if (hasCyrillic(q)) return q;
  if (!wear) return q;
  const wearFull = WEAR_FULL[wear.toLowerCase()];
  if (!wearFull) return q;
  const open = q.indexOf('(');
  if (open !== -1) q = q.slice(0, open).trim();
  return `${q} (${wearFull})`;
}

// ---- data ----

let indexCache = { text: null, at: 0 };

async function getIndexText() {
  const now = Date.now();
  if (indexCache.text !== null && now - indexCache.at < 15 * 60 * 1000) {
    return indexCache.text;
  }
  const res = await fetch(`${GITHUB_RAW}?t=${now}`, {
    headers: { 'User-Agent': 'cs2-skin-pricer-worker' },
  });
  if (!res.ok) throw new Error(`index fetch ${res.status}`);
  const text = await res.text();
  indexCache = { text, at: now };
  return text;
}

function searchIndex(query) {
  const q = query.toLowerCase().trim();
  if (!q || hasCyrillic(q)) return [];
  const qFlat = q.replace(/[^a-z0-9]+/g, '');
  const words = q.split(/[^a-z0-9]+/).filter((w) => w.length >= 2);
  const hits = [];
  const lines = indexCache.text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line) continue;
    const tab = line.indexOf('\t');
    if (tab <= 0) continue;
    const flat = line.slice(0, tab);
    if ((qFlat && flat.includes(qFlat)) || (words.length >= 2 && words.every((w) => flat.includes(w)))) {
      const parts = line.split('\t');
      hits.push({
        name: parts[1] || '',
        usd: parseFloat(parts[2]) || null,
        rub: parseFloat(parts[3]) || null,
        flat,
      });
    }
  }
  hits.sort((a, b) => (a.usd || 1e9) - (b.usd || 1e9));
  return hits.slice(0, 6);
}

async function steamSearch(query) {
  try {
    const url = STEAM_SEARCH.replace('{q}', encodeURIComponent(query));
    const res = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) cs2-skin-pricer/1.0' },
    });
    if (!res.ok) return [];
    const data = await res.json();
    const out = [];
    for (const item of (data.results || []).slice(0, 8)) {
      const name = String(item.hash_name || '').trim();
      if (!name) continue;
      const priceText = String(item.sell_price_text || '').replace(/<[^>]+>/g, '');
      const m = priceText.match(/(\d[\d\s]*)(?:[.,](\d+))?/);
      if (!m) continue;
      const price = parseFloat(m[1].replace(/\s/g, '') + '.' + (m[2] || '0'));
      const asset = item.asset_description || {};
      out.push({
        name,
        price_usd: price,
        image: asset.icon_url ? STEAM_ICON.replace('{url}', asset.icon_url) : '',
      });
    }
    return out;
  } catch {
    return [];
  }
}

function flatOf(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '');
}

function lisEstimate(usd, rub) {
  return {
    usd: usd == null ? null : usd * LIS_FACTOR,
    rub: rub == null ? null : rub * LIS_FACTOR,
  };
}

function priceLine(name, value, currency, fee) {
  if (value == null) return `**${name}**: нет цены`;
  const net = value - value * fee;
  const sign = CURRENCY[currency] || currency;
  return `**${name}**: ${value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${sign} → на руки **${net.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${sign}**`;
}

function buildEmbed(name, entry) {
  const lines = [
    priceLine('CS.Market', entry.usd, 'usd', FEES.csmarket),
    priceLine('CS.Market RUB', entry.rub, 'rub', FEES.csmarket),
    priceLine('Steam', entry.steam_usd, 'usd', FEES.steam),
  ];
  const lis = lisEstimate(entry.usd, entry.rub);
  if (lis.usd == null) {
    lines.push('**LIS-Skins**: нет цены');
  } else {
    const fmt = (v) => v.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    lines.push(`**LIS-Skins ≈**: ${fmt(lis.usd)} $ / ${fmt(lis.rub)} \u20BD *(оценка)*`);
  }
  const embed = {
    title: `\uD83D\uDCB0 ${name}`,
    color: 0xf0883e,
    fields: [{ name: 'Цены', value: lines.join('\n'), inline: false }],
    footer: { text: 'LIS-Skins — оценка от CS.Market (×0.97) · данные CS.Market обновляются каждый час' },
  };
  if (entry.image) embed.thumbnail = { url: entry.image };
  return embed;
}

async function doSearch(query, wear) {
  const qnorm = normalizeQuery(query, wear);
  if (hasCyrillic(qnorm)) return { qnorm, results: [] };
  await getIndexText();
  let cs = searchIndex(qnorm);
  const steam = await steamSearch(qnorm);
  if (cs.length === 0 && steam.length === 0) return { qnorm, results: [] };

  const results = [];
  const seen = new Set();
  for (const m of cs) {
    if (seen.has(m.name)) continue;
    seen.add(m.name);
    const st = steam.find((s) => flatOf(s.name) === m.flat);
    const entry = { name: m.name, usd: m.usd, rub: m.rub, steam_usd: st ? st.price_usd : null, image: '' };
    results.push(entry);
    if (results.length >= 4) break;
  }
  if (results.length < 4) {
    for (const s of steam) {
      if (seen.has(s.name)) continue;
      seen.add(s.name);
      results.push({ name: s.name, usd: null, rub: null, steam_usd: s.price_usd, image: s.image });
      if (results.length >= 4) break;
    }
  }
  return { qnorm, results };
}

async function handleSkin(interaction, env) {
  const appId = interaction.application_id;
  const token = interaction.token;
  const patchUrl = `https://discord.com/api/v10/webhooks/${appId}/${token}/messages/@original`;
  const opts = (interaction.data.options || []).reduce((acc, o) => {
    acc[o.name] = o.value;
    return acc;
  }, {});
  const query = String(opts.query || '');
  const wear = opts.wear ? String(opts.wear) : null;

  const patch = (payload) =>
    fetch(patchUrl, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).catch(() => {});

  try {
    const { qnorm, results } = await doSearch(query, wear);
    if (results.length === 0) {
      await patch({
        content: `Ничего не нашлось по запросу **${qnorm}**. Попробуй точнее, например \`AK-47 | Redline (Field-Tested)\``,
      });
      return;
    }
    const embeds = results.map((r) => buildEmbed(r.name, r));
    const msg = { embeds };
    if (embeds.length > 1) {
      msg.content = `Нашёл ${embeds.length} вариантов по запросу **${qnorm}**:`;
    }
    await patch(msg);
  } catch (err) {
    await patch({ content: `Ошибка поиска: ${String(err.message || err).slice(0, 300)}` });
  }
}

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') {
      return new Response('cs2-skin-pricer worker is alive', { status: 200 });
    }
    let interaction;
    try {
      interaction = await request.json();
    } catch {
      return json({ error: 'bad json' }, 400);
    }
    if (interaction.type === 1) {
      return json({ type: 1 });
    }
    if (interaction.type === 2 && interaction.data && interaction.data.name === 'skin') {
      ctx.waitUntil(handleSkin(interaction, env));
      return json({ type: 5 });
    }
    return json({ type: 4, data: { content: 'Неизвестная команда' } });
  },
};

export const _test = {
  normalizeQuery,
  searchIndex,
  setIndexText: (t) => {
    indexCache = { text: t, at: Date.now() };
  },
};
