// cs2-skin-pricer — Cloudflare Worker
// Discord slash command /skin via HTTP interactions (no PC needed).
// Deploy: create a Worker on dash.cloudflare.com, paste this file,
// then set INTERACTIONS_ENDPOINT_URL in Discord Developer Portal
// to https://<worker-name>.<your-subdomain>.workers.dev

const GITHUB_RAW = 'https://raw.githubusercontent.com/spikeshowglhf-max/cs2-skin-pricer/main/search_index.tsv';
const GITHUB_DICT = 'https://raw.githubusercontent.com/spikeshowglhf-max/cs2-skin-pricer/main/ru_dict.json';
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
  'тычковые ножи': 'Stiletto Knife',
  'тычковый нож': 'Stiletto Knife',
  'складной нож': 'Flip Knife',
  'кинжалы-бабочки': 'Shadow Daggers',
  'кинжал-бабочка': 'Shadow Daggers',
  'теневые кинжалы': 'Shadow Daggers',
  'нож-наваха': 'Navaja Knife',
  'наваха': 'Navaja Knife',
  'медвежий нож': 'Ursus Knife',
  'нож-тесак': 'Bowie Knife',
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
  'скелетон нож': 'Skeleton Knife',
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
  'мрамор': 'Marble Fade',
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
  'африканская сетка': 'Safari Mesh',
  'африканская': 'Safari Mesh',
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
  'гипербист': 'Hyper Beast',
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
  'калашников': 'AK-47',
  'автомат': 'AK-47',
  'авп': 'AWP',
  'авик': 'AWP',
  'снайперка': 'AWP',
  'снайперская': 'AWP',
  'м4а4': 'M4A4',
  'м4': 'M4A4',
  'м4а1': 'M4A1-S',
  'м4а1-с': 'M4A1-S',
  'м4а1с': 'M4A1-S',
  'м4а1-s': 'M4A1-S',
  'пустынный орёл': 'Desert Eagle',
  'дезерт игл': 'Desert Eagle',
  'десерт игл': 'Desert Eagle',
  'дигл': 'Desert Eagle',
  'дегл': 'Desert Eagle',
  'усп': 'USP-S',
  'глок': 'Glock-18',
  'глок-18': 'Glock-18',
  'фамас': 'FAMAS',
  'галиль': 'Galil AR',
  'галил': 'Galil AR',
  'маг-7': 'MAG-7',
  'маг7': 'MAG-7',
  'п90': 'P90',
  'негев': 'Negev',
  'нэгев': 'Negev',
  'ск20': 'SCAR-20',
  'скар': 'SCAR-20',
  'скар-20': 'SCAR-20',
  'автопушка': 'AWP',
  'ауг': 'AUG',
  'авг': 'AUG',
  'сг553': 'SG 553',
  'сг-553': 'SG 553',
  'ссг': 'SSG 08',
  'ссг08': 'SSG 08',
  'ссг-08': 'SSG 08',
  'г3сг1': 'G3SG1',
  'г3': 'G3SG1',
  'мп9': 'MP9',
  'эмп9': 'MP9',
  'мп7': 'MP7',
  'эмп7': 'MP7',
  'мп5': 'MP5-SD',
  'эмп5': 'MP5-SD',
  'мп5-сд': 'MP5-SD',
  'мп5сд': 'MP5-SD',
  'мак-10': 'MAC-10',
  'мак10': 'MAC-10',
  'макаров': 'MAC-10',
  'умп': 'UMP-45',
  'умп-45': 'UMP-45',
  'умп45': 'UMP-45',
  'бизон': 'PP-Bizon',
  'пп-бизон': 'PP-Bizon',
  'пп-19': 'PP-Bizon',
  'пп19': 'PP-Bizon',
  'нова': 'Nova',
  'обрез': 'Sawed-Off',
  'савед-офф': 'Sawed-Off',
  'хм1014': 'XM1014',
  'м249': 'M249',
  'тек-9': 'Tec-9',
  'тек9': 'Tec-9',
  'п250': 'P250',
  'файв-севен': 'Five-SeveN',
  'файв': 'Five-SeveN',
  'цз75': 'CZ75-Auto',
  'цз-75': 'CZ75-Auto',
  'цз': 'CZ75-Auto',
  'чешка': 'CZ75-Auto',
  'дуал': 'Dual Berettas',
  'дуалы': 'Dual Berettas',
  'беретты': 'Dual Berettas',
  'р8': 'R8 Revolver',
  'р-8': 'R8 Revolver',
  'зевс': 'Zeus x27',
  'зеус': 'Zeus x27',
  'тезер': 'Zeus x27',
};

const HOMOGLYPHS = {
  'а': 'a', 'е': 'e', 'ё': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y',
  'х': 'x', 'к': 'k', 'м': 'm', 'т': 't', 'в': 'b', 'н': 'n',
  'А': 'a', 'Е': 'e', 'Ё': 'e', 'О': 'o', 'Р': 'p', 'С': 'c', 'У': 'y',
  'Х': 'x', 'К': 'k', 'М': 'm', 'Т': 't', 'В': 'b', 'Н': 'n',
};

function canon(s) {
  return s
    .split('')
    .map((ch) => HOMOGLYPHS[ch] || ch)
    .join('')
    .toLowerCase();
}

const RU_GUNS_LATIN = {
  'usp': 'USP-S',
  'deagle': 'Desert Eagle',
  'deag': 'Desert Eagle',
};

function subAllWord(text, table) {
  let low = canon(text);
  const entries = Object.entries(table).sort((a, b) => b[0].length - a[0].length);
  for (const [ru, en] of entries) {
    const pos = low.indexOf(canon(ru));
    if (pos === -1) continue;
    const before = pos > 0 ? low[pos - 1] : ' ';
    const after = pos + ru.length < low.length ? low[pos + ru.length] : ' ';
    if (/[a-z0-9-]/.test(before) || /[a-z0-9-]/.test(after)) continue;
    text = text.slice(0, pos) + en + text.slice(pos + ru.length);
    low = canon(text);
  }
  return text;
}

function boundaryOk(low, pos, length, blockDash = false) {
  const before = pos > 0 ? low[pos - 1] : ' ';
  const after = pos + length < low.length ? low[pos + length] : ' ';
  if (/[a-zа-яё0-9]/.test(before) || /[a-zа-яё0-9]/.test(after)) return false;
  if (blockDash && (before === '-' || after === '-')) return false;
  return true;
}

function subAll(text, table, wordBoundary = false) {
  let low = canon(text);
  const entries = Object.entries(table).sort((a, b) => b[0].length - a[0].length);
  for (const [ru, en] of entries) {
    const key = canon(ru);
    for (;;) {
      const pos = low.indexOf(key);
      if (pos === -1) break;
      if (wordBoundary && !boundaryOk(low, pos, ru.length)) break;
      text = text.slice(0, pos) + en + text.slice(pos + ru.length);
      low = canon(text);
    }
  }
  return text;
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function replaceBest(text, table, wordBoundary = false, blockDash = false) {
  const low = canon(text);
  const entries = Object.entries(table).sort((a, b) => b[0].length - a[0].length);
  const matches = [];
  for (const [ru, en] of entries) {
    const pos = low.indexOf(canon(ru));
    if (pos === -1) continue;
    if (wordBoundary && !boundaryOk(low, pos, ru.length, blockDash)) continue;
    matches.push([pos, pos + ru.length, ru, en]);
  }
  if (!matches.length) return text;
  let best = matches[0];
  let bi = 0;
  matches.forEach((m, i) => {
    if (m[1] - m[0] > best[1] - best[0]) { best = m; bi = i; }
  });
  const bestEn = best[3];
  const segs = [[best[0], best[1], bestEn]];
  const taken = [[best[0], best[1]]];
  for (let i = 0; i < matches.length; i++) {
    if (i === bi) continue;
    const [s, e, , en] = matches[i];
    if (s < best[1] && best[0] < e) continue;
    if (en !== bestEn) continue;
    if (taken.some(([ts, te]) => s < te && ts < e)) continue;
    taken.push([s, e]);
    segs.push([s, e, '']);
  }
  segs.sort((a, b) => a[0] - b[0]);
  let out = '';
  let prev = 0;
  for (const [s, e, repl] of segs) {
    out += text.slice(prev, s) + repl;
    prev = e;
  }
  return out + text.slice(prev);
}

const RU_MISC = {
  'нож': '',
  'перчатки': '',
  '(после полевых испытаний)': '',
  'х27': '',
};

function ruToEn(query, patterns) {
  let q = query.trim().replace(/\s+/g, ' ');
  q = subAll(q, RU_WEAR);
  q = replaceBest(q, RU_GUNS);
  q = replaceBest(q, RU_GUNS_LATIN, true, true);
  let lowK = canon(q);
  for (const [ru, en] of Object.entries(RU_KNIVES)) {
    const pos = lowK.indexOf(canon(ru));
    if (pos !== -1) {
      q = q.slice(0, pos) + en + q.slice(pos + ru.length);
      break;
    }
  }
  q = subAll(q, patterns || RU_PATTERNS, true);
  q = subAll(q, RU_MISC, true);
  return q.trim().replace(/\s+/g, ' ');
}

function hasCyrillic(s) {
  return /[а-яА-ЯёЁ]/.test(s);
}

function suggestFromRu(qnorm, table) {
  const ruTokens = (qnorm.match(/[а-яё]+/gi) || [])
    .map((t) => t.toLowerCase())
    .filter((t) => t.length >= 3);
  if (ruTokens.length === 0) return [];
  const scores = new Map();
  for (const [ru, en] of Object.entries(table)) {
    const ruLow = ru.toLowerCase();
    let sc = 0;
    for (const tok of ruTokens) {
      if (ruLow.includes(tok)) {
        sc += 3;
      } else {
        for (let i = 4; i <= Math.min(6, tok.length); i++) {
          if (ruLow.includes(tok.slice(0, i))) {
            sc += 1;
            break;
          }
        }
      }
    }
    if (sc > 0) scores.set(en, (scores.get(en) || 0) + sc);
  }
  return [...scores.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([en]) => en);
}

function normalizeQuery(query, wear, patterns) {
  if (wear) {
    const we = String(wear).toLowerCase().trim();
    if (RU_WEAR_SHORT[we]) {
      wear = RU_WEAR_SHORT[we];
    } else {
      const toks = we.match(/(?<![a-zа-я])[a-zа-я]{1,4}(?![a-zа-я])/g) || [];
      for (const t of toks) {
        if (RU_WEAR_SHORT[t]) {
          wear = RU_WEAR_SHORT[t];
          break;
        }
      }
    }
  }
  let q = ruToEn(query, patterns);
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
let dictCache = { table: null, at: 0 };

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

async function getRuDict() {
  const now = Date.now();
  if (dictCache.table !== null && now - dictCache.at < 15 * 60 * 1000) {
    return dictCache.table;
  }
  let generated = {};
  try {
    const res = await fetch(`${GITHUB_DICT}?t=${now}`, {
      headers: { 'User-Agent': 'cs2-skin-pricer-worker' },
    });
    if (res.ok) generated = await res.json();
  } catch {
    generated = {};
  }
  const table = { ...generated, ...RU_PATTERNS };
  dictCache = { table, at: now };
  return table;
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
  const patterns = await getRuDict();
  const qnorm = normalizeQuery(query, wear, patterns);
  if (hasCyrillic(qnorm)) return { qnorm, results: [], suggestions: suggestFromRu(qnorm, patterns) };
  await getIndexText();
  let cs = searchIndex(qnorm);
  const steam = await steamSearch(qnorm);
  if (cs.length === 0 && steam.length === 0) return { qnorm, results: [], suggestions: [] };

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
  return { qnorm, results, suggestions: [] };
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
    const { qnorm, results, suggestions } = await doSearch(query, wear);
    if (results.length === 0) {
      let content = `Ничего не нашлось по запросу **${qnorm}**.`;
      if (suggestions.length > 0) {
        content += `\nВозможно, имелось в виду: \`${suggestions.join('`, `')}\`.`;
      } else {
        content += ` Попробуй точнее, например \`AK-47 | Redline (Field-Tested)\`.`;
      }
      await patch({ content });
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

function hexToBytes(hex) {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}

async function verifySignature(env, timestamp, signatureHex, rawBody) {
  if (!env || !env.DISCORD_PUBLIC_KEY || !timestamp || !signatureHex) return false;
  try {
    const key = await crypto.subtle.importKey(
      'raw',
      hexToBytes(env.DISCORD_PUBLIC_KEY),
      { name: 'Ed25519' },
      false,
      ['verify']
    );
    const valid = await crypto.subtle.verify(
      { name: 'Ed25519' },
      key,
      hexToBytes(signatureHex),
      new TextEncoder().encode(timestamp + rawBody)
    );
    return valid;
  } catch (err) {
    return false;
  }
}

export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') {
      return new Response('cs2-skin-pricer worker is alive', { status: 200 });
    }
    const rawBody = await request.text();
    const signature = request.headers.get('X-Signature-Ed25519') || '';
    const timestamp = request.headers.get('X-Signature-Timestamp') || '';
    const verified = await verifySignature(env, timestamp, signature, rawBody);
    if (!verified) {
      return new Response('invalid request signature', { status: 401 });
    }
    let interaction;
    try {
      interaction = JSON.parse(rawBody);
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
  verifySignature,
};
