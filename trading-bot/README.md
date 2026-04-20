# CreativeMess Scalper EA (MT4 / TMGM)

Expert Advisor per MetaTrader 4 con strategia **mean-reversion** (RSI + Bollinger Bands), studiato per obiettivi modesti e realistici (target giornaliero €50 su conto adeguato).

> **Avvertenza onesta.** Nessun Expert Advisor garantisce profitti. Lo scalping ad alta frequenza su broker retail paga spread e commissioni ad ogni trade: anche perdite "minime" moltiplicate per molti trade erodono il capitale. Usa **sempre** demo per almeno 4 settimane e fai backtest su dati reali prima del live.

---

## Contenuto

- `CreativeMessScalper.mq4` — Expert Advisor MQL4

---

## Come funziona

**Strategia:** mean-reversion classica.
- **BUY** quando il prezzo rompe sotto la banda di Bollinger inferiore **e** RSI < 28.
- **SELL** quando il prezzo rompe sopra la banda di Bollinger superiore **e** RSI > 72.

**Protezioni incluse:**
- Stop Loss e Take Profit automatici.
- **Target giornaliero** (default €50): appena raggiunto, chiude tutto e si ferma fino al giorno dopo.
- **Stop loss giornaliero** (default €30): se la perdita del giorno supera la soglia, chiude tutto e si ferma.
- **Filtro spread:** non apre trade se lo spread corrente è maggiore del limite.
- **Filtro orario:** opera solo nelle ore di alta liquidità (default 08–20).
- **Trailing stop** opzionale per bloccare profitti.
- **Lotto fisso** o **auto-lot** in base alla % di rischio sull'equity.
- **Limite trade simultanei** e intervallo minimo tra ingressi.

---

## Installazione in MT4

1. Apri MT4 connesso al conto TMGM.
2. Menu **File → Apri cartella dati** (Open Data Folder).
3. Copia `CreativeMessScalper.mq4` in `MQL4/Experts/`.
4. In MT4 premi **Ctrl+N** (Navigator) → tasto destro su "Expert Advisors" → **Aggiorna**.
5. Apri un grafico (es. EURUSD M5) e trascina sopra l'EA.
6. Nella scheda **Common** abilita: "Allow live trading" e "Allow DLL imports" non serve.
7. Verifica che in alto a destra nel grafico ci sia lo **smile** (AutoTrading attivo). Pulsante **AutoTrading** nella toolbar deve essere verde.

---

## Parametri consigliati per partire (demo!)

| Parametro | Valore | Note |
|---|---|---|
| InpLotSize | 0.01 | Micro lotto. Su conto da €500–1000. |
| InpDailyProfitTarget | 50.0 | Target giornaliero in valuta conto. |
| InpDailyLossLimit | 30.0 | Perdita max accettata in un giorno. |
| InpStopLossPoints | 200 | 20 pip su broker 5-digit. |
| InpTakeProfitPoints | 100 | 10 pip. Rapporto 2:1 compensato da win rate alto. |
| InpMaxSpreadPoints | 25 | Scarta trade con spread > 2.5 pip. |
| InpMaxOpenTrades | 2 | |
| InpStartHour / InpEndHour | 8 / 20 | Server time del broker (spesso GMT+2 o GMT+3). |
| InpTimeframe | PERIOD_M5 | M5 più stabile di M1 per scalping. |

### Simboli suggeriti
- **EURUSD**, **USDJPY**, **GBPUSD** (spread bassi su conto ECN TMGM).
- Evita all'inizio: XAUUSD (oro) e indici — movimenti ampi, SL/TP vanno ritarati.

---

## Quanto capitale serve realisticamente per €50/giorno?

Con lotto 0.01 (1 micro lot), 1 pip su EURUSD ≈ €0.10.
Per fare €50 servirebbero **500 pip di profitto netto** al giorno → impossibile con 1 micro lot.

**Scenari realistici:**

| Capitale | Lotto sensato | Target €50 richiede | Fattibilità |
|---|---|---|---|
| €500 | 0.01 | 500 pip/giorno | Irrealistico |
| €2.000 | 0.05 | 100 pip/giorno | Ambizioso |
| €5.000 | 0.10 | 50 pip/giorno | Ragionevole |
| €10.000 | 0.20 | 25 pip/giorno | Sostenibile |

Conclusione: €50/giorno in modo sostenibile richiede **almeno €5.000 di capitale** e aspettative su un **ritorno annuo del ~30–50%** (già ottimo se reale).

---

## Backtest obbligatorio prima del live

1. In MT4: **View → Strategy Tester** (Ctrl+R).
2. Expert Advisor: `CreativeMessScalper`.
3. Symbol: EURUSD. Period: M5. Model: "Every tick".
4. Date range: almeno ultimi 6 mesi.
5. Scarica dati storici di qualità (Tools → History Center).
6. Lancia, analizza drawdown e profit factor. **Profit factor > 1.3** e **drawdown < 20%** sono soglie minime decenti.

Se il backtest è negativo → **NON metterlo in reale.** Ritara i parametri o cambia strategia.

---

## Cosa l'EA NON fa (volutamente)

- Non usa martingala né grid (perdono tutto prima o poi).
- Non apre 1000 trade al giorno: lo spread ti mangerebbe il capitale.
- Non promette guadagni. È uno strumento, non una macchina da soldi.

---

## Disclaimer legale

Questo software è fornito "così com'è" a scopo educativo. L'autore non è responsabile di perdite finanziarie. Il trading di strumenti a leva comporta rischio elevato di perdita totale del capitale. Valuta la tua situazione finanziaria prima di operare.
