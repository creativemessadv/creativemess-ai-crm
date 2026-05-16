# Trading bot — micro-gains framework

Scheletro di trading bot Python pensato per **backtest** e **paper trading**
di strategie che cercano molti piccoli profitti. Nessun ordine reale viene
inviato. Nessuna API key. Tutto simulato.

> ⚠️ Questo NON è consulenza finanziaria e NON è una macchina per fare soldi.
> Leggi la sezione "Aspettative realistiche" prima di credere a numeri rosa.

## Cosa fa

- Strategia plug-in (default: mean-reversion su RSI, scalping intraday)
- Backtest deterministico con commissioni e slippage configurabili
- Risk manager con: position sizing percentuale, max posizioni concorrenti,
  stop-loss giornaliero, cap di trade/giorno
- Paper trading 24/7 contro i dati pubblici di Binance
- Generatore di dati sintetici per provare il sistema offline

## Struttura

```
trading-bot/
├── config.yaml              # tutti i parametri
├── bot/
│   ├── backtester.py        # event loop bar-per-bar
│   ├── broker/paper.py      # simulatore di fill (TP/SL intra-bar)
│   ├── data.py              # downloader Binance + dati sintetici
│   ├── risk.py              # position sizing & limiti giornalieri
│   ├── reporting.py         # statistiche di output
│   └── strategies/
│       ├── base.py
│       └── mean_reversion_rsi.py
├── scripts/
│   ├── download_data.py
│   ├── run_backtest.py
│   └── run_paper.py
└── tests/
```

## Quick start

```bash
cd trading-bot
pip install -r requirements.txt

# 1) Demo offline su dati sintetici (1 mese di candele 1m)
python scripts/run_backtest.py --config config.yaml --synthetic --synthetic-days 30

# 2) Backtest su dati reali
python scripts/download_data.py --symbol BTCUSDT --interval 1m \
    --start 2025-01-01 --end 2025-02-01 \
    --out data/BTCUSDT_1m_2025-01.parquet
python scripts/run_backtest.py --config config.yaml \
    --data data/BTCUSDT_1m_2025-01.parquet \
    --csv-out reports/trades.csv

# 3) Paper trading h24 (Ctrl-C per fermare)
python scripts/run_paper.py --config config.yaml --poll 10
```

## Aspettative realistiche

L'obiettivo "200 €/giorno fissi con micro-trade da 1-2 €" sembra banale ma è
matematicamente molto duro. Tre vincoli che il framework rende visibili:

1. **Le commissioni mangiano.** Con `fee_pct=0.075%` (Binance taker), ogni
   round-trip su 1.000 € di nozionale costa **1,50 €**. Per fare 2 €
   *netti* devi catturare almeno 3,5 € lordi → un movimento dello 0,35%.
   Non è "banale".

2. **Win-rate richiesto.** Con TP=SL la matematica vuole >50% di vittorie
   *al netto dei costi*. Le strategie tipo grid o martingala "vincono sempre"
   finché un giorno azzerano il conto. Il `RiskManager` in `bot/risk.py`
   pone un tetto giornaliero apposta per evitarlo.

3. **Slippage.** Su 1.000 trade/giorno, anche 1 tick di slippage in più
   diventa il fattore dominante. Il backtester applica slippage
   configurabile sia in entrata sia in uscita.

Il report finale stampa esplicitamente *quanti giorni hanno raggiunto la
soglia target* (default 200 €) rispetto al totale dei giorni testati —
non un numero medio gonfiato.

## Come si tara

I parametri sensibili sono in `config.yaml`:

| Parametro | Effetto |
|-----------|---------|
| `strategy.params.rsi_oversold` / `rsi_overbought` | Quanti segnali al giorno (più stretti = meno trade, più selettivi) |
| `strategy.params.take_profit_pct` / `stop_loss_pct` | Rapporto rischio/rendimento. TP > SL alza il break-even win-rate |
| `risk.risk_per_trade_pct` | % capitale a rischio per trade. 0.5% è prudente |
| `risk.max_daily_loss_pct` | Quando supera questo, il bot smette di aprire fino al giorno dopo |
| `execution.fee_pct` | **Da impostare al valore VERO** del tuo broker, altrimenti il backtest mente |

## Da broker simulato a TMGM

Quando avrai una strategia validata su mesi di backtest **fuori sample**:

1. Implementa un nuovo broker in `bot/broker/` (es. `mt5.py`) con la stessa
   interfaccia di `PaperBroker.open()` / `step()`.
2. Per TMGM la via standard è MetaTrader 5 via il pacchetto `MetaTrader5`
   (solo Windows) oppure un bridge come `mt5linux`.
3. Esegui prima su account **demo** TMGM per settimane, non per ore.
4. Solo dopo: account reale, size minima.

## Note di onestà

- Le strategie semplici (mean reversion, grid) sono **arbitraggiate via**
  da anni dai market maker. Non aspettarti edge stabile su asset liquidi.
- Un backtest che sembra perfetto è quasi sempre overfit. Testa su un
  periodo, valida su un altro mai visto.
- Nessuno regala 200 €/giorno. Se questa cifra fosse facile, l'avrebbe
  già automatizzata qualcuno con più capitale di te.
