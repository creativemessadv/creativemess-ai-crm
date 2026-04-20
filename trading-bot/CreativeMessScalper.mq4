//+------------------------------------------------------------------+
//|                                       CreativeMessScalper.mq4    |
//|                                        CreativeMess ADV © 2026   |
//|  Mean-reversion scalper: RSI + Bollinger Bands                   |
//|  Target giornaliero configurabile, stop giornaliero, spread      |
//|  filter, orari di trading, gestione rischio.                     |
//|                                                                  |
//|  AVVERTENZA: Nessun EA garantisce profitti. Testa sempre in      |
//|  demo per almeno 4 settimane prima di passare al conto reale.    |
//+------------------------------------------------------------------+
#property copyright "CreativeMess ADV"
#property link      "https://creativemess.it"
#property version   "1.00"
#property strict
#property description "Scalper mean-reversion con target giornaliero e stop di protezione."

//--- Input: gestione capitale
input double InpLotSize              = 0.01;   // Lotto fisso (0.01 = micro lot)
input bool   InpUseAutoLot           = false;  // Calcolo lotto da % equity
input double InpRiskPercent          = 0.5;    // Rischio % per trade (se AutoLot)

//--- Input: obiettivi giornalieri
input double InpDailyProfitTarget    = 50.0;   // Target profitto giornaliero (valuta conto)
input double InpDailyLossLimit       = 30.0;   // Max perdita giornaliera (valuta conto)

//--- Input: TP/SL in points (5-digit: 1 pip = 10 points)
input int    InpStopLossPoints       = 200;    // Stop Loss in points (20 pip)
input int    InpTakeProfitPoints     = 100;    // Take Profit in points (10 pip)
input bool   InpUseTrailingStop      = true;   // Attiva trailing stop
input int    InpTrailingStartPoints  = 60;     // Points di profitto per attivare trailing
input int    InpTrailingStepPoints   = 30;     // Distanza trailing stop (points)

//--- Input: filtri di ingresso
input int    InpMaxSpreadPoints      = 25;     // Spread massimo (points) per aprire trade
input int    InpMaxOpenTrades        = 2;      // Trade simultanei max
input int    InpMinSecondsBetween    = 60;     // Secondi minimi tra ingressi

//--- Input: orari (server time del broker)
input bool   InpUseTimeFilter        = true;   // Abilita filtro orario
input int    InpStartHour            = 8;      // Ora inizio trading
input int    InpEndHour              = 20;     // Ora fine trading
input bool   InpTradeFriday          = true;   // Consenti trading venerdì
input int    InpFridayEndHour        = 18;     // Ora stop il venerdì

//--- Input: indicatori
input int    InpRSIPeriod            = 14;     // Periodo RSI
input int    InpRSIOversold          = 28;     // Soglia ipervenduto
input int    InpRSIOverbought        = 72;     // Soglia ipercomprato
input int    InpBBPeriod             = 20;     // Periodo Bollinger Bands
input double InpBBDeviation          = 2.0;    // Deviazione standard BB
input ENUM_TIMEFRAMES InpTimeframe   = PERIOD_M5; // Timeframe analisi

//--- Input: identificazione
input int    InpMagicNumber          = 20260420; // Magic number
input int    InpSlippage             = 3;        // Slippage (points)
input string InpTradeComment         = "CMScalper";

//--- Variabili globali
datetime g_lastTradeTime  = 0;
datetime g_currentDay     = 0;
double   g_dayStartEquity = 0.0;
bool     g_dayStopped     = false;
string   g_stopReason     = "";

//+------------------------------------------------------------------+
//| Inizializzazione                                                 |
//+------------------------------------------------------------------+
int OnInit()
{
   g_currentDay     = iTime(Symbol(), PERIOD_D1, 0);
   g_dayStartEquity = AccountEquity();
   g_dayStopped     = false;
   g_stopReason     = "";

   if(InpStopLossPoints <= 0 || InpTakeProfitPoints <= 0)
   {
      Print("ERRORE: SL e TP devono essere > 0");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpDailyLossLimit <= 0 || InpDailyProfitTarget <= 0)
   {
      Print("ERRORE: limiti giornalieri devono essere > 0");
      return(INIT_PARAMETERS_INCORRECT);
   }

   Print("CreativeMessScalper avviato su ", Symbol(),
         " | Target giornaliero: ", InpDailyProfitTarget,
         " | Stop giornaliero: -", InpDailyLossLimit);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Deinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("CreativeMessScalper fermato. Motivo: ", reason);
}

//+------------------------------------------------------------------+
//| Tick                                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   CheckNewDay();

   ManageOpenPositions();

   if(g_dayStopped)
      return;

   if(!CheckDailyLimits())
      return;

   if(InpUseTimeFilter && !IsTradingTime())
      return;

   if(MarketInfo(Symbol(), MODE_SPREAD) > InpMaxSpreadPoints)
      return;

   if(CountOpenOrders() >= InpMaxOpenTrades)
      return;

   if(TimeCurrent() - g_lastTradeTime < InpMinSecondsBetween)
      return;

   int signal = GetSignal();
   if(signal == OP_BUY || signal == OP_SELL)
      OpenTrade(signal);
}

//+------------------------------------------------------------------+
//| Reset dati alla nuova sessione giornaliera                       |
//+------------------------------------------------------------------+
void CheckNewDay()
{
   datetime today = iTime(Symbol(), PERIOD_D1, 0);
   if(today != g_currentDay)
   {
      g_currentDay     = today;
      g_dayStartEquity = AccountEquity();
      g_dayStopped     = false;
      g_stopReason     = "";
      Print("Nuova giornata. Equity iniziale: ", DoubleToString(g_dayStartEquity, 2));
   }
}

//+------------------------------------------------------------------+
//| Verifica target/limite giornaliero                               |
//+------------------------------------------------------------------+
bool CheckDailyLimits()
{
   double pnl = AccountEquity() - g_dayStartEquity;

   if(pnl >= InpDailyProfitTarget)
   {
      g_dayStopped = true;
      g_stopReason = "Target giornaliero raggiunto: +" + DoubleToString(pnl, 2);
      Print(g_stopReason, ". Chiudo posizioni e mi fermo fino a domani.");
      CloseAllMyOrders();
      return false;
   }
   if(pnl <= -InpDailyLossLimit)
   {
      g_dayStopped = true;
      g_stopReason = "Stop loss giornaliero: " + DoubleToString(pnl, 2);
      Print(g_stopReason, ". Chiudo posizioni e mi fermo fino a domani.");
      CloseAllMyOrders();
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Filtro orario                                                    |
//+------------------------------------------------------------------+
bool IsTradingTime()
{
   int dayOfWeek = TimeDayOfWeek(TimeCurrent());
   int hour      = TimeHour(TimeCurrent());

   if(dayOfWeek == 0 || dayOfWeek == 6) return false; // domenica/sabato

   if(dayOfWeek == 5)
   {
      if(!InpTradeFriday) return false;
      if(hour >= InpFridayEndHour) return false;
   }

   if(hour < InpStartHour || hour >= InpEndHour) return false;

   return true;
}

//+------------------------------------------------------------------+
//| Segnale: mean-reversion RSI + Bollinger Bands                    |
//+------------------------------------------------------------------+
int GetSignal()
{
   double rsi     = iRSI(Symbol(), InpTimeframe, InpRSIPeriod, PRICE_CLOSE, 1);
   double bbUpper = iBands(Symbol(), InpTimeframe, InpBBPeriod, InpBBDeviation, 0, PRICE_CLOSE, MODE_UPPER, 1);
   double bbLower = iBands(Symbol(), InpTimeframe, InpBBPeriod, InpBBDeviation, 0, PRICE_CLOSE, MODE_LOWER, 1);
   double close1  = iClose(Symbol(), InpTimeframe, 1);

   // BUY: prezzo sotto BB inferiore e RSI ipervenduto
   if(close1 < bbLower && rsi < InpRSIOversold)
      return OP_BUY;

   // SELL: prezzo sopra BB superiore e RSI ipercomprato
   if(close1 > bbUpper && rsi > InpRSIOverbought)
      return OP_SELL;

   return -1;
}

//+------------------------------------------------------------------+
//| Calcolo lotto dinamico                                           |
//+------------------------------------------------------------------+
double CalculateLot()
{
   if(!InpUseAutoLot) return NormalizeLot(InpLotSize);

   double riskMoney  = AccountEquity() * InpRiskPercent / 100.0;
   double tickValue  = MarketInfo(Symbol(), MODE_TICKVALUE);
   double slMoney    = InpStopLossPoints * tickValue;
   if(slMoney <= 0) return NormalizeLot(InpLotSize);

   double lot = riskMoney / slMoney;
   return NormalizeLot(lot);
}

double NormalizeLot(double lot)
{
   double minLot  = MarketInfo(Symbol(), MODE_MINLOT);
   double maxLot  = MarketInfo(Symbol(), MODE_MAXLOT);
   double lotStep = MarketInfo(Symbol(), MODE_LOTSTEP);

   lot = MathFloor(lot / lotStep) * lotStep;
   if(lot < minLot) lot = minLot;
   if(lot > maxLot) lot = maxLot;
   return NormalizeDouble(lot, 2);
}

//+------------------------------------------------------------------+
//| Apertura trade                                                   |
//+------------------------------------------------------------------+
void OpenTrade(int cmd)
{
   double lot     = CalculateLot();
   double price   = (cmd == OP_BUY) ? Ask : Bid;
   double point   = Point;
   double sl      = 0, tp = 0;

   if(cmd == OP_BUY)
   {
      sl = price - InpStopLossPoints * point;
      tp = price + InpTakeProfitPoints * point;
   }
   else
   {
      sl = price + InpStopLossPoints * point;
      tp = price - InpTakeProfitPoints * point;
   }

   sl = NormalizeDouble(sl, Digits);
   tp = NormalizeDouble(tp, Digits);

   int ticket = OrderSend(Symbol(), cmd, lot, price, InpSlippage, sl, tp,
                          InpTradeComment, InpMagicNumber, 0,
                          (cmd == OP_BUY) ? clrDodgerBlue : clrOrangeRed);

   if(ticket < 0)
      Print("OrderSend fallito. Err=", GetLastError(), " cmd=", cmd, " lot=", lot);
   else
      g_lastTradeTime = TimeCurrent();
}

//+------------------------------------------------------------------+
//| Gestione trailing stop sulle posizioni aperte                    |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   if(!InpUseTrailingStop) return;

   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderMagicNumber() != InpMagicNumber)        continue;
      if(OrderSymbol() != Symbol())                   continue;

      double openPrice = OrderOpenPrice();
      double sl        = OrderStopLoss();
      double newSL;

      if(OrderType() == OP_BUY)
      {
         if(Bid - openPrice >= InpTrailingStartPoints * Point)
         {
            newSL = NormalizeDouble(Bid - InpTrailingStepPoints * Point, Digits);
            if(newSL > sl)
            {
               if(!OrderModify(OrderTicket(), openPrice, newSL, OrderTakeProfit(), 0, clrYellow))
                  Print("Trailing BUY fallito. Err=", GetLastError());
            }
         }
      }
      else if(OrderType() == OP_SELL)
      {
         if(openPrice - Ask >= InpTrailingStartPoints * Point)
         {
            newSL = NormalizeDouble(Ask + InpTrailingStepPoints * Point, Digits);
            if(newSL < sl || sl == 0)
            {
               if(!OrderModify(OrderTicket(), openPrice, newSL, OrderTakeProfit(), 0, clrYellow))
                  Print("Trailing SELL fallito. Err=", GetLastError());
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Conta ordini aperti dell'EA sul simbolo                          |
//+------------------------------------------------------------------+
int CountOpenOrders()
{
   int count = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderMagicNumber() != InpMagicNumber)        continue;
      if(OrderSymbol() != Symbol())                   continue;
      count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| Chiude tutti gli ordini aperti dell'EA                           |
//+------------------------------------------------------------------+
void CloseAllMyOrders()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderMagicNumber() != InpMagicNumber)        continue;
      if(OrderSymbol() != Symbol())                   continue;

      double closePrice = (OrderType() == OP_BUY) ? Bid : Ask;
      if(!OrderClose(OrderTicket(), OrderLots(), closePrice, InpSlippage, clrWhite))
         Print("Chiusura fallita ticket ", OrderTicket(), " Err=", GetLastError());
   }
}
//+------------------------------------------------------------------+
