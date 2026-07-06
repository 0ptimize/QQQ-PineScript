# QQQ-PineScript — Dealer-State Levels for TradingView (Pine Seeds)

Auto-publishes the QQQ **dealer-state structural levels** (from the Maneki engine) into
TradingView via [Pine Seeds](https://github.com/tradingview-pine-seeds/docs), so they
plot as lines on your chart and refresh once a day with no manual work.

> These levels are **market-structure context** (magnets / bounds), **not trade signals**.
> Direction is not predictable from this data — see the Maneki research conclusion.

## Symbols

| Seed symbol    | Meaning                              |
|----------------|--------------------------------------|
| `QQQ_FLIP`     | Zero-gamma flip (dealer pivot)       |
| `QQQ_CALLWALL` | Call wall (upside magnet/resistance) |
| `QQQ_PUTWALL`  | Put wall (downside magnet/support)   |
| `QQQ_EM_HI`    | Spot + 1-week implied move           |
| `QQQ_EM_LO`    | Spot − 1-week implied move           |

`pricescale` = 100 (2 decimals). Data is **EOD only** — one row per trading day.

## Repo layout
```
symbol_info/QQQ-PineScript.json   # symbol metadata (filename must equal repo name)
data/QQQ_FLIP.csv ...             # one CSV per symbol: YYYYMMDDT,O,H,L,C,V (flat OHLC, V=0)
qqq_levels.pine                   # the TradingView indicator (add this to your chart)
publisher/publish_levels.py       # nightly: computes levels on the mini + commits/pushes
```

## One-time TradingView onboarding (only you can do this)
Pine Seeds requires TradingView to connect this **public** repo to your account before
`request.seed()` resolves:
1. Follow the setup in <https://github.com/tradingview-pine-seeds/docs> and email
   **pine.seeds@tradingview.com** to request onboarding for `0ptimize/QQQ-PineScript`.
2. After approval, confirm the exact source string (typically `seed_0ptimize_QQQ-PineScript`)
   and set it as `SRC` in `qqq_levels.pine`.
3. Add `qqq_levels.pine` as an indicator on your QQQ chart.

## Automatic daily updates
`publisher/publish_levels.py` runs on the Mac mini (where the Maneki DB lives), mirrors
`tests/dashboard.py` exactly, upserts today's row into each `data/*.csv`, and pushes.
TradingView ingests the push within ~15 min; the chart shows it next session.

```bash
# dry run (no push)
SEEDS_PUSH=0 /Users/darksweep/maneki-venv/bin/python publisher/publish_levels.py
# cron (after the settled chain lands): example 18:10 ET
10 18 * * 1-5  cd /Users/darksweep/QQQ-PineScript && SEEDS_REPO=$PWD /Users/darksweep/maneki-venv/bin/python publisher/publish_levels.py >> /tmp/seeds_publish.log 2>&1
```

**Data dependency:** levels come from the settled **options-chain** ingestion. While that
feed is stale, the publisher keeps rewriting the last good date (no false "fresh" rows) and
resumes automatically when the chain advances.
