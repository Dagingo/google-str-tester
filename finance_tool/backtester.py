# finance_tool/backtester.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import logging
from typing import Dict, Any, Callable, Type, Optional

# Importiere neue Architekturkomponenten
from .strategy_definition import StrategyDefinition
from .strategy_engine import StrategyEvaluator
# data_pipeline wird als Funktion übergeben, nicht direkt importiert für die Klasse selbst,
# aber für den if __name__ == "__main__" Block.

logger = logging.getLogger(__name__)

class Backtester:
    """
    Führt Backtests für Handelsstrategien durch, die durch StrategyDefinition-Objekte definiert sind.
    Verwendet eine Datenpipeline zur Aufbereitung der Daten und eine Strategie-Engine zur Signalerzeugung.
    """
    def __init__(self,
                 initial_capital: float = 100000.0,
                 commission_per_trade: float = 0.0,
                 slippage_pct: float = 0.0):
        """
        Initialisiert den Backtester.

        Args:
            initial_capital (float, optional): Das anfängliche Kapital.
            commission_per_trade (float, optional): Kommission pro Trade (fixer Betrag).
            slippage_pct (float, optional): Prozentsatz für Slippage pro Trade.
        """
        if initial_capital <= 0:
            raise ValueError("Anfangskapital muss positiv sein.")
        if commission_per_trade < 0 or slippage_pct < 0:
            raise ValueError("Kommission und Slippage dürfen nicht negativ sein.")

        self.initial_capital = initial_capital
        self.commission_per_trade = commission_per_trade
        self.slippage_pct = slippage_pct

        # Diese werden pro Backtest-Lauf gesetzt
        self.strategy_def: Optional[StrategyDefinition] = None
        self.data_with_indicators: Optional[pd.DataFrame] = None
        self.signals: Optional[pd.Series] = None
        self.portfolio_history: Optional[pd.DataFrame] = None
        self.trades_log: Optional[pd.DataFrame] = None # Ersetzt self.results für Klarheit

        logger.debug(f"Backtester initialisiert mit Kapital: {initial_capital}, Kommission: {commission_per_trade}, Slippage: {slippage_pct}")


    def _apply_slippage(self, price: float, signal_type: str) -> float: # signal_type: 'buy' or 'sell'
        """ Wendet Slippage auf den Ausführungspreis an. """
        if signal_type == 'buy': # Kauf
            return price * (1 + self.slippage_pct)
        elif signal_type == 'sell': # Verkauf
            return price * (1 - self.slippage_pct)
        return price

    def run_backtest(self,
                     ticker: str,
                     start_date: str,
                     end_date: str,
                     interval: str,
                     strategy_def: StrategyDefinition,
                     data_pipeline_func: Callable, # z.B. prepare_data_for_strategy
                     strategy_engine_cls: Type[StrategyEvaluator], # z.B. StrategyEvaluator
                     shares_per_trade: Optional[int] = None,
                     capital_per_trade_pct: Optional[float] = None):
        """
        Führt den Backtest für eine gegebene Strategie und einen Ticker durch.

        Args:
            ticker (str): Das Tickersymbol.
            start_date (str): Startdatum für die Daten.
            end_date (str): Enddatum für die Daten.
            interval (str): Datenintervall (z.B. "1d").
            strategy_def (StrategyDefinition): Die zu testende Strategiedefinition.
            data_pipeline_func (Callable): Funktion zur Datenaufbereitung (z.B. prepare_data_for_strategy).
            strategy_engine_cls (Type[StrategyEvaluator]): Klasse der Strategie-Engine.
            shares_per_trade (int, optional): Anzahl der zu handelnden Aktien pro Trade.
            capital_per_trade_pct (float, optional): Kapitalanteil pro Trade (z.B. 0.1 für 10%).

        Raises:
            ValueError: Wenn Parameter ungültig sind.
        """
        logger.info(f"Starte Backtest für Strategie '{strategy_def.name}' auf Ticker '{ticker}' ({start_date} bis {end_date}).")
        self.strategy_def = strategy_def

        if (shares_per_trade is None and capital_per_trade_pct is None) or \
           (shares_per_trade is not None and capital_per_trade_pct is not None):
            raise ValueError("Entweder 'shares_per_trade' oder 'capital_per_trade_pct' muss angegeben werden, aber nicht beide.")
        if shares_per_trade is not None and shares_per_trade <= 0:
            raise ValueError("shares_per_trade muss positiv sein.")
        if capital_per_trade_pct is not None and (capital_per_trade_pct <= 0 or capital_per_trade_pct > 1):
            raise ValueError("capital_per_trade_pct muss zwischen 0 (exklusiv) und 1 (inklusiv) liegen.")

        # 1. Daten aufbereiten (inkl. Indikatoren)
        logger.debug("Rufe Datenpipeline auf...")
        self.data_with_indicators = data_pipeline_func(
            ticker=ticker, start_date=start_date, end_date=end_date,
            interval=interval, strategy_def=strategy_def
        )
        if self.data_with_indicators is None or self.data_with_indicators.empty:
            logger.error("Datenpipeline lieferte keine Daten. Backtest abgebrochen.")
            # Setze leere Ergebnisse, damit calculate_performance_metrics nicht fehlschlägt
            self.portfolio_history = pd.DataFrame(columns=['holdings', 'cash', 'total_value', 'shares', 'positions'])
            self.trades_log = pd.DataFrame(columns=['timestamp', 'type', 'price', 'shares', 'cost', 'profit'])
            return

        # Sicherstellen, dass die Preisspalte für die Simulation existiert (normalerweise 'close')
        # Die StrategyEngine verwendet die Spaltennamen aus der strategy_def,
        # aber die Backtest-Simulation selbst braucht einen Referenzpreis.
        sim_price_col = 'close' # Annahme: 'close' ist immer der Simulationspreis
        if sim_price_col not in self.data_with_indicators.columns:
             logger.error(f"Simulationspreisspalte '{sim_price_col}' nicht im DataFrame der Pipeline gefunden. Backtest abgebrochen.")
             # Setze leere Ergebnisse
             self.portfolio_history = pd.DataFrame(columns=['holdings', 'cash', 'total_value', 'shares', 'positions'])
             self.trades_log = pd.DataFrame(columns=['timestamp', 'type', 'price', 'shares', 'cost', 'profit'])
             return


        # 2. Signale generieren
        logger.debug("Initialisiere und verwende Strategie-Engine zur Signalerzeugung...")
        evaluator = strategy_engine_cls(strategy_def) # price_data_cols wird von Engine verwendet
        self.signals = evaluator.generate_signals(self.data_with_indicators)

        if self.signals is None or self.signals.empty:
            logger.error("Strategie-Engine lieferte keine Signale. Backtest abgebrochen.")
            self.portfolio_history = pd.DataFrame(columns=['holdings', 'cash', 'total_value', 'shares', 'positions'])
            self.trades_log = pd.DataFrame(columns=['timestamp', 'type', 'price', 'shares', 'cost', 'profit'])
            return

        # Sicherstellen, dass data und signals denselben Index haben und ausgerichtet sind
        if not isinstance(self.signals, pd.Series):
            logger.error(f"Strategie-Engine lieferte keinen pd.Series als Signale, sondern {type(self.signals)}. Backtest abgebrochen.")
            self.portfolio_history = pd.DataFrame(columns=['holdings', 'cash', 'total_value', 'shares', 'positions'])
            self.trades_log = pd.DataFrame(columns=['timestamp', 'type', 'price', 'shares', 'cost', 'profit'])
            return

        self.signals.name = "signal" # Stelle sicher, dass die Serie einen Namen hat für sauberes Logging etc.

        # Align data (DataFrame) and signals (Series)
        # align gibt zwei Objekte zurück, die denselben (inneren) Index haben.
        # aligned_signals_series wird eine Series sein.
        aligned_data, aligned_signals_series = self.data_with_indicators.align(self.signals, join='inner', axis=0)

        if aligned_data.empty or aligned_signals_series.empty:
            logger.error("Nach Angleichung von Daten und Signalen sind keine überlappenden Datenpunkte vorhanden. Backtest abgebrochen.")
            self.portfolio_history = pd.DataFrame(columns=['holdings', 'cash', 'total_value', 'shares', 'positions'])
            self.trades_log = pd.DataFrame(columns=['timestamp', 'type', 'price', 'shares', 'cost', 'profit'])
            return

        self.data_with_indicators = aligned_data
        self.signals = aligned_signals_series # Ist bereits die ausgerichtete Signal-Series


        # 3. Trade-Simulation (Logik größtenteils von alter Version übernommen)
        logger.debug("Starte Trade-Simulation...")
        self.portfolio_history = pd.DataFrame(index=self.data_with_indicators.index)
        self.portfolio_history['holdings'] = 0.0
        self.portfolio_history['cash'] = float(self.initial_capital)
        self.portfolio_history['total_value'] = float(self.initial_capital)
        self.portfolio_history['shares'] = 0.0
        self.portfolio_history['positions'] = 0 # 0=Neutral, 1=Long, -1=Short

        current_position = 0
        trades_list = [] # Für self.trades_log

        for i in range(len(self.data_with_indicators)):
            timestamp = self.data_with_indicators.index[i]
            current_price = self.data_with_indicators[sim_price_col].iloc[i]
            signal = self.signals.iloc[i]

            # Werte vom Vortag übernehmen
            if i > 0:
                self.portfolio_history.loc[timestamp, 'cash'] = self.portfolio_history['cash'].iloc[i-1]
                self.portfolio_history.loc[timestamp, 'shares'] = self.portfolio_history['shares'].iloc[i-1]
            # 'positions' wird basierend auf Trades aktualisiert

            # Trade-Logik (vereinfacht: geht nur Long oder ist Neutral)
            # Die Signale (1=Buy, -1=Sell, 0=Hold/Neutral) werden interpretiert:
            # Signal 1: Wenn nicht Long, gehe Long. Wenn schon Long, halte.
            # Signal -1: Wenn Long, schließe Long-Position. Wenn nicht Long, ignoriere (kein Shorting hier).
            # Signal 0: Wenn Long, halte. Wenn nicht Long, bleibe neutral.
            # Für Shorting müsste dies erweitert werden.

            # KAUFEN (Signal 1 und aktuell nicht Long)
            if signal == 1 and current_position == 0:
                num_shares_to_buy = 0
                if shares_per_trade:
                    num_shares_to_buy = shares_per_trade
                elif capital_per_trade_pct:
                    capital_for_trade = self.portfolio_history['cash'].iloc[i-1] * capital_per_trade_pct if i > 0 else self.initial_capital * capital_per_trade_pct
                    buy_price_slippage = self._apply_slippage(current_price, 'buy')
                    if buy_price_slippage > 0:
                         num_shares_to_buy = int(capital_for_trade / buy_price_slippage)
                    else:
                         num_shares_to_buy = 0
                         logger.warning(f"Timestamp {timestamp}: Kaufpreis mit Slippage ist 0 oder negativ. Kein Kauf möglich.")

                if num_shares_to_buy > 0:
                    buy_price_final = self._apply_slippage(current_price, 'buy')
                    cost = num_shares_to_buy * buy_price_final + self.commission_per_trade
                    current_cash = self.portfolio_history['cash'].iloc[i-1] if i > 0 else self.initial_capital

                    if current_cash >= cost:
                        self.portfolio_history.loc[timestamp, 'cash'] -= cost
                        self.portfolio_history.loc[timestamp, 'shares'] += num_shares_to_buy
                        current_position = 1
                        trades_list.append({'timestamp': timestamp, 'type': 'Buy', 'price': buy_price_final,
                                           'shares': num_shares_to_buy, 'cost': cost, 'profit': np.nan})
                        logger.debug(f"Trade {timestamp}: BUY {num_shares_to_buy} @ {buy_price_final:.2f}")
                    else:
                        logger.debug(f"Trade {timestamp}: BUY Signal, aber nicht genug Kapital (Bedarf: {cost:.2f}, Vorhanden: {current_cash:.2f})")
                else:
                    logger.debug(f"Trade {timestamp}: BUY Signal, aber num_shares_to_buy ist 0.")

            # VERKAUFEN (Signal -1 und aktuell Long)
            elif signal == -1 and current_position == 1:
                sell_price_final = self._apply_slippage(current_price, 'sell')
                shares_to_sell = self.portfolio_history['shares'].iloc[i-1] # Alle Aktien verkaufen
                proceeds = shares_to_sell * sell_price_final - self.commission_per_trade

                self.portfolio_history.loc[timestamp, 'cash'] += proceeds
                self.portfolio_history.loc[timestamp, 'shares'] = 0.0 # Reset shares
                current_position = 0

                # Profit für diesen Trade berechnen
                # Finde den zugehörigen Kauf-Trade (vereinfacht: der letzte Kauf)
                entry_cost = np.nan
                entry_price = np.nan
                for t in reversed(trades_list):
                    if t['type'] == 'Buy' and t['shares'] == shares_to_sell: # Einfache Annahme
                        entry_cost = t['cost']
                        entry_price = t['price']
                        break
                profit = (proceeds + self.commission_per_trade) - (entry_cost - self.commission_per_trade) if not np.isnan(entry_cost) else np.nan

                trades_list.append({'timestamp': timestamp, 'type': 'Sell', 'price': sell_price_final,
                                   'shares': shares_to_sell, 'cost': -proceeds, 'profit': profit}) # Cost ist negativ (Einnahme)
                logger.debug(f"Trade {timestamp}: SELL {shares_to_sell} @ {sell_price_final:.2f}, Profit: {profit:.2f}")

            self.portfolio_history.loc[timestamp, 'positions'] = current_position
            current_holdings_value = self.portfolio_history['shares'].iloc[i] * current_price
            self.portfolio_history.loc[timestamp, 'holdings'] = current_holdings_value
            self.portfolio_history.loc[timestamp, 'total_value'] = self.portfolio_history['cash'].iloc[i] + current_holdings_value

        self.trades_log = pd.DataFrame(trades_list)
        logger.info("Trade-Simulation beendet.")


    def calculate_performance_metrics(self) -> Dict[str, Any]:
        """
        Berechnet verschiedene Performance-Metriken für den Backtest.
        (Logik größtenteils von alter Version übernommen, ggf. Anpassungen für Profit-Berechnung)
        """
        logger.debug("Berechne Performance-Metriken...")
        if self.portfolio_history is None or self.portfolio_history.empty:
            logger.warning("Kein Portfolio-Verlauf vorhanden, um Metriken zu berechnen.")
            return {"error": "Portfolio-Verlauf nicht vorhanden."}

        metrics = {}
        final_value = self.portfolio_history['total_value'].iloc[-1]
        metrics["final_portfolio_value"] = round(final_value, 2)
        metrics["total_return_pct"] = round((final_value - self.initial_capital) / self.initial_capital * 100, 2)

        duration_days = (self.portfolio_history.index[-1] - self.portfolio_history.index[0]).days
        if duration_days == 0 and len(self.portfolio_history) > 1: duration_days = 1 # Mind. 1 Tag für Berechnung, wenn mehrere Punkte

        if duration_days > 0:
            duration_years = duration_days / 365.25
            metrics["annualized_return_pct"] = round((( (1 + metrics["total_return_pct"]/100) ** (1/duration_years) ) - 1) * 100, 2)
        else:
            metrics["annualized_return_pct"] = 0.0 if len(self.portfolio_history) <=1 else metrics["total_return_pct"]


        daily_returns = self.portfolio_history['total_value'].pct_change().dropna()
        if not daily_returns.empty and daily_returns.std() != 0:
            metrics["sharpe_ratio"] = round((daily_returns.mean() / daily_returns.std()) * np.sqrt(252 if duration_days >=1 else 1), 3) # Annahme 252 Handelstage/Jahr
        else:
            metrics["sharpe_ratio"] = 0.0

        cumulative_returns = (1 + daily_returns).cumprod()
        peak = cumulative_returns.cummax()
        drawdown = (cumulative_returns - peak) / peak
        metrics["max_drawdown_pct"] = round(abs(drawdown.min() * 100), 2) if not drawdown.empty else 0.0

        if self.trades_log is not None and not self.trades_log.empty:
            closed_trades = self.trades_log[self.trades_log['type'] == 'Sell'] # Nur abgeschlossene Trades (Verkäufe)
            metrics["total_trades_closed"] = len(closed_trades)
            if not closed_trades.empty:
                winning_trades = closed_trades[closed_trades['profit'] > 0]
                metrics["winning_trades"] = len(winning_trades)
                metrics["win_rate_pct"] = round((len(winning_trades) / len(closed_trades)) * 100, 2) if len(closed_trades) > 0 else 0.0

                total_gains = closed_trades[closed_trades['profit'] > 0]['profit'].sum()
                total_losses = abs(closed_trades[closed_trades['profit'] <= 0]['profit'].sum())
                metrics["profit_factor"] = round(total_gains / total_losses, 2) if total_losses > 0 else float('inf') if total_gains > 0 else 0.0
            else:
                metrics["winning_trades"] = 0
                metrics["win_rate_pct"] = 0.0
                metrics["profit_factor"] = 0.0
        else:
            metrics["total_trades_closed"] = 0
            metrics["winning_trades"] = 0
            metrics["win_rate_pct"] = 0.0
            metrics["profit_factor"] = 0.0

        logger.info(f"Performance-Metriken berechnet: {metrics}")
        return metrics


    def plot_results(self, ticker_for_plot: Optional[str] = None):
        """
        Plottet die Ergebnisse des Backtests: Portfolio-Wert und ggf. Handelssignale.
        Diese Methode verwendet plt.show() und ist für direkte Modultests gedacht.
        Für GUI-Integration sollte eine Methode verwendet werden, die eine Figure zurückgibt.
        """
        logger.debug("Erstelle Ergebnis-Plot...")
        if self.portfolio_history is None or self.portfolio_history.empty or \
           self.data_with_indicators is None or self.data_with_indicators.empty:
            logger.warning("Keine ausreichenden Daten zum Plotten vorhanden.")
            print("Keine ausreichenden Daten zum Plotten vorhanden.")
            return

        fig, ax1 = plt.subplots(figsize=(14, 7), dpi=100)

        ax1.plot(self.portfolio_history.index, self.portfolio_history['total_value'], label='Portfolio Value', color='blue', lw=2)
        ax1.set_xlabel('Datum')
        ax1.set_ylabel('Portfolio Wert (€)', color='blue')
        ax1.tick_params(axis='y', labelcolor='blue')
        title = f'Backtest: {self.strategy_def.name if self.strategy_def else "Unbekannte Strategie"}'
        if ticker_for_plot: title += f' auf {ticker_for_plot}'
        ax1.set_title(title)
        ax1.grid(True, linestyle='--', alpha=0.7)

        ax2 = ax1.twinx()
        sim_price_col = 'close' # Annahme
        ax2.plot(self.data_with_indicators.index, self.data_with_indicators[sim_price_col], label=f'{ticker_for_plot or "Asset"} Preis', color='grey', alpha=0.6, lw=1)
        ax2.set_ylabel('Preis (€)', color='grey')
        ax2.tick_params(axis='y', labelcolor='grey')

        if self.trades_log is not None and not self.trades_log.empty:
            buys = self.trades_log[self.trades_log['type'] == 'Buy']
            sells = self.trades_log[self.trades_log['type'] == 'Sell']
            if not buys.empty:
                ax2.plot(buys['timestamp'], buys['price'], '^', markersize=8, color='green', lw=0, label='Kauf')
            if not sells.empty:
                ax2.plot(sells['timestamp'], sells['price'], 'v', markersize=8, color='red', lw=0, label='Verkauf')

        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc='upper left')

        fig.tight_layout()
        plt.show()
        logger.debug("Ergebnis-Plot angezeigt.")


if __name__ == "__main__":
    if not logging.getLogger().hasHandlers():
        import sys
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])

    from .data_pipeline import prepare_data_for_strategy # Für den Test
    from .strategy_definition import StrategyDefinition as TestStrategyDef, Rule as TestRule, Condition as TestCond # Eindeutige Namen für Test

    logger.info("--- Test des überarbeiteten Backtester-Moduls ---")

    # Beispiel-Strategiedefinition (muss mit den von der Pipeline erzeugten Spaltennamen übereinstimmen)
    cond_b1 = TestCond("RSI", "RSI_length14_rsi", "<", 30, params1={"length": 14})
    cond_b2 = TestCond("SMA", "SMA_length20_sma", "CrossesAbove", None,
                       indicator2_name="SMA", output_field2="SMA_length50_sma",
                       params1={"length": 20}, params2={"length": 50})
    rule_b = TestRule([cond_b1, cond_b2], "OR", "BUY", "RSI < 30 OR SMA20 crosses SMA50")

    cond_s1 = TestCond("Price", "close", "CrossesBelow", None,
                       indicator2_name="SMA", output_field2="SMA_length20_sma",
                       params2={"length": 20}) # Price vs SMA20
    rule_s = TestRule([cond_s1], "AND", "SELL", "Price crosses below SMA20")

    test_strat_def = TestStrategyDef(
        name="BacktesterTestStrategy_RSI_SMA",
        description="Teststrategie für den überarbeiteten Backtester.",
        buy_rules=[rule_b],
        sell_rules=[rule_s]
    )

    backtester_instance = Backtester(initial_capital=10000, commission_per_trade=1.0, slippage_pct=0.001)

    ticker = "MSFT" # Microsoft
    start = (pd.Timestamp.now() - pd.Timedelta(days=730)).strftime('%Y-%m-%d') # Letzte 2 Jahre
    end = pd.Timestamp.now().strftime('%Y-%m-%d')

    logger.info(f"Starte Backtest für {ticker} von {start} bis {end} mit Strategie '{test_strat_def.name}'.")

    try:
        backtester_instance.run_backtest(
            ticker=ticker,
            start_date=start,
            end_date=end,
            interval="1d",
            strategy_def=test_strat_def,
            data_pipeline_func=prepare_data_for_strategy, # Übergebe die Funktion
            strategy_engine_cls=StrategyEvaluator,      # Übergebe die Klasse
            capital_per_trade_pct=0.25 # Beispiel: 25% des Kapitals pro Trade
        )

        if backtester_instance.portfolio_history is not None and not backtester_instance.portfolio_history.empty:
            logger.info("\nPortfolio Zeitverlauf (letzte 5 Tage):")
            logger.info(backtester_instance.portfolio_history.tail().to_string())

            logger.info("\nTrades Log (erste 5 und letzte 5):")
            if backtester_instance.trades_log is not None and not backtester_instance.trades_log.empty:
                logger.info(backtester_instance.trades_log.head().to_string())
                if len(backtester_instance.trades_log) > 5:
                    logger.info("...")
                    logger.info(backtester_instance.trades_log.tail().to_string())
            else:
                logger.info("Keine Trades ausgeführt.")

            metrics_results = backtester_instance.calculate_performance_metrics()
            logger.info("\nPerformance Metriken:")
            for metric, value in metrics_results.items():
                logger.info(f"  {metric.replace('_', ' ').capitalize()}: {value}")

            logger.info("Zeige Plot an (wenn matplotlib verfügbar und GUI-Kontext erlaubt)...")
            backtester_instance.plot_results(ticker_for_plot=ticker)
        else:
            logger.warning("Backtest lieferte keinen Portfolio-Verlauf.")

    except Exception as e:
        logger.critical(f"Fehler während des Backtest-Laufs im Test: {e}", exc_info=True)

    logger.info("--- Test des überarbeiteten Backtester-Moduls beendet ---")
