# cs2-skin-pricer

CS2 skin price tracker: Steam, CS.Market + Discord bot.

## Что это

- **GitHub Pages сайт** — `https://spikeshowglhf-max.github.io/cs2-skin-pricer/`
- **GitHub Actions** (каждый час) — качает цены CS.Market (RUB+USD), коммитит `prices.json` и `search_index.tsv`
- **Discord бот** — команда `/skin`, ищет цены (CS.Market + Steam + оценка LIS-Skins)

## Локальный запуск бота (на ПК)

```bat
set DISCORD_BOT_TOKEN=ваш_токен
python -X utf8 -u discord_bot.py
```

или просто запустить `run_bot.bat`.

## Облачная версия бота (Cloudflare Workers) — без ПК, 24/7

Бот работает через HTTP-интеракции Discord — серверное приложение не нужно, PC можно выключить или переустановить Windows.

1. Зарегистрируйся на https://dash.cloudflare.com (бесплатно)
2. **Workers & Pages → Create → Worker** (любое имя, например `cs2-skin-pricer`)
3. Открой **Edit code**, удали дефолтный код и вставь содержимое файла `worker.js` из этого репозитория → **Deploy**
4. Открой свой воркер → **Settings → Triggers**, скопируй URL вида `https://cs2-skin-pricer.<твой-поддомен>.workers.dev`
5. В **Discord Developer Portal → твоё приложение → General Information**, в поле **Interactions Endpoint URL** вставь этот URL → **Save** (Discord проверит соединение PING-ом, воркер ответит автоматически)
6. Готово. Теперь `/skin` работает из облака; локального бота можно выключить

Как это работает: воркер отвечает команде мгновенно («Думаю...»), ищет по `search_index.tsv` (обновляется каждый час workflow-ем) + Steam вживую, и присылает цены. Ответ занимает ~2-5 секунд.

Примечание: endpoint без проверки подписи Discord (бот только считает цены — безопасно для личного использования).

## Ручной запуск проверки цен через Actions

В репозитории на GitHub: **Actions → CS2 Skin Pricer → Run workflow**:

- `check-watchlist` — проверить список из `watchlist.json`, прислать изменения в Discord (webhook)
- `refresh-prices` — обновить `prices.json` + `search_index.tsv`
- `lookup-skin` + `query` — найти скин и прислать в Discord по webhook
