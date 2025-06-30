# finance_tool/backtester.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from .strategies import TradingStrategy # Import base class for type hinting

class Backtester:
    """
    Führt Backtests für Handelsstrategien durch und berechnet Performance-Metriken.
    """
    def __init__(self, strategy: TradingStrategy, initial_capital: float = 100000.0,
                 commission_per_trade: float = 0.0, slippage_pct: float = 0.0):
        """
        Initialisiert den Backtester.

        Args:
            strategy (TradingStrategy): Eine Instanz einer Handelsstrategie.
            initial_capital (float, optional): Das anfängliche Kapital. Standard 100.000.
            commission_per_trade (float, optional): Kommission pro Trade (fixer Betrag). Standard 0.0.
            slippage_pct (float, optional): Prozentsatz für Slippage pro Trade. Standard 0.0.
        """
        if not isinstance(strategy, TradingStrategy):
            raise ValueError("Strategie muss eine Instanz von TradingStrategy sein.")
        if initial_capital <= 0:
            raise ValueError("Anfangskapital muss positiv sein.")
        if commission_per_trade < 0 or slippage_pct < 0:
            raise ValueError("Kommission und Slippage dürfen nicht negativ sein.")

        self.strategy = strategy
        self.initial_capital = initial_capital
        self.commission_per_trade = commission_per_trade
        self.slippage_pct = slippage_pct

        self.data = strategy.data.copy() # Daten aus der Strategie übernehmen
        self.signals = None
        self.results = None
        self.portfolio_history = None

    def _apply_slippage(self, price: float, signal: int) -> float:
        """ Wendet Slippage auf den Ausführungspreis an. """
        if signal == 1: # Kauf
            return price * (1 + self.slippage_pct)
        elif signal == -1: # Verkauf
            return price * (1 - self.slippage_pct)
        return price

    def run_backtest(self, shares_per_trade: int = None, capital_per_trade_pct: float = None):
        """
        Führt den Backtest durch. Es muss entweder `shares_per_trade` oder `capital_per_trade_pct` angegeben werden.

        Args:
            shares_per_trade (int, optional): Anzahl der zu handelnden Aktien pro Trade.
            capital_per_trade_pct (float, optional): Prozentsatz des aktuellen Kapitals, das pro Trade eingesetzt wird.
                                                     (z.B. 0.1 für 10%).

        Raises:
            ValueError: Wenn weder shares_per_trade noch capital_per_trade_pct angegeben wird,
                        oder wenn beide angegeben werden.
        """
        if (shares_per_trade is None and capital_per_trade_pct is None) or \
           (shares_per_trade is not None and capital_per_trade_pct is not None):
            raise ValueError("Entweder 'shares_per_trade' oder 'capital_per_trade_pct' muss angegeben werden, aber nicht beide.")
        if shares_per_trade is not None and shares_per_trade <= 0:
            raise ValueError("shares_per_trade muss positiv sein.")
        if capital_per_trade_pct is not None and (capital_per_trade_pct <= 0 or capital_per_trade_pct > 1):
            raise ValueError("capital_per_trade_pct muss zwischen 0 (exklusiv) und 1 (inklusiv) liegen.")


        self.signals = self.strategy.generate_signals()
        if 'signal' not in self.signals.columns:
            raise ValueError("Signale DataFrame muss eine 'signal'-Spalte enthalten.")

        # Sicherstellen, dass data und signals denselben Index haben und ausgerichtet sind
        self.data, self.signals = self.data.align(self.signals, join='inner', axis=0)

        # Portfolio-Initialisierung
        self.portfolio_history = pd.DataFrame(index=self.data.index)
        self.portfolio_history['holdings'] = 0.0  # Wert der gehaltenen Aktien
        self.portfolio_history['cash'] = float(self.initial_capital)
        self.portfolio_history['total_value'] = float(self.initial_capital)
        self.portfolio_history['shares'] = 0.0 # Anzahl der gehaltenen Aktien (float für Flexibilität)
        self.portfolio_history['positions'] = 0 # Aktuelle Position (1=Long, -1=Short, 0=Neutral)

        current_position = 0 # 0 = neutral, 1 = long, -1 = short (für Strategien, die Shorting erlauben)

        # Liste für Trades, um Performance-Metriken zu berechnen
        trades = []

        for i in range(len(self.data)):
            timestamp = self.data.index[i]
            current_price = self.data['Close'].iloc[i] # Für Berechnungen den Schlusskurs verwenden
            signal = self.signals['signal'].iloc[i]

            # Werte vom Vortag übernehmen, falls keine Aktion stattfindet
            if i > 0:
                self.portfolio_history.loc[timestamp, 'cash'] = self.portfolio_history['cash'].iloc[i-1]
                self.portfolio_history.loc[timestamp, 'shares'] = self.portfolio_history['shares'].iloc[i-1]
                self.portfolio_history.loc[timestamp, 'positions'] = self.portfolio_history['positions'].iloc[i-1]

            # Logik für Trade-Ausführung
            # Annahme: Signale sind persistente Zustände (1=long, -1=short, 0=neutral/keine Position)
            # Die Strategie sollte Signale so generieren, dass ein Wechsel des Signals einen Trade auslöst.

            # Wenn das Signal LONG ist und wir nicht bereits LONG sind
            if signal == 1 and current_position != 1:
                # Glattstellen einer eventuellen Short-Position
                if current_position == -1:
                    # Rückkauf (Short-Position schließen)
                    buy_price_short_cover = self._apply_slippage(current_price, 1) # Slippage beim Kauf
                    cash_change = self.portfolio_history['shares'].iloc[i-1] * buy_price_short_cover # shares sind negativ
                    self.portfolio_history.loc[timestamp, 'cash'] += cash_change - self.commission_per_trade
                    trades.append({'timestamp': timestamp, 'type': 'Cover Short', 'price': buy_price_short_cover,
                                   'shares': -self.portfolio_history['shares'].iloc[i-1], 'cost': -cash_change + self.commission_per_trade})
                    self.portfolio_history.loc[timestamp, 'shares'] = 0

                # Long-Position eröffnen
                available_cash = self.portfolio_history['cash'].iloc[i-1] if i > 0 else self.initial_capital

                num_shares_to_buy = 0
                if shares_per_trade:
                    num_shares_to_buy = shares_per_trade
                elif capital_per_trade_pct:
                    capital_for_trade = available_cash * capital_per_trade_pct
                    num_shares_to_buy = int(capital_for_trade / self._apply_slippage(current_price, 1))

                if num_shares_to_buy > 0 and available_cash >= num_shares_to_buy * self._apply_slippage(current_price, 1) + self.commission_per_trade:
                    buy_price = self._apply_slippage(current_price, 1)
                    cost = num_shares_to_buy * buy_price + self.commission_per_trade
                    self.portfolio_history.loc[timestamp, 'cash'] -= cost
                    self.portfolio_history.loc[timestamp, 'shares'] += num_shares_to_buy
                    self.portfolio_history.loc[timestamp, 'positions'] = 1
                    current_position = 1
                    trades.append({'timestamp': timestamp, 'type': 'Buy', 'price': buy_price,
                                   'shares': num_shares_to_buy, 'cost': cost})

            # Wenn das Signal SHORT ist und wir nicht bereits SHORT sind
            elif signal == -1 and current_position != -1:
                 # Glattstellen einer eventuellen Long-Position
                if current_position == 1:
                    sell_price_long_close = self._apply_slippage(current_price, -1) # Slippage beim Verkauf
                    cash_change = self.portfolio_history['shares'].iloc[i-1] * sell_price_long_close
                    self.portfolio_history.loc[timestamp, 'cash'] += cash_change - self.commission_per_trade
                    trades.append({'timestamp': timestamp, 'type': 'Sell', 'price': sell_price_long_close,
                                   'shares': self.portfolio_history['shares'].iloc[i-1], 'cost': -cash_change + self.commission_per_trade})
                    self.portfolio_history.loc[timestamp, 'shares'] = 0

                # Short-Position eröffnen (Annahme: Leerverkauf ist möglich)
                # Für dieses Beispiel: Shorting bedeutet, Aktien zu "leihen" und zu verkaufen.
                # Der Cash-Bestand erhöht sich, aber es entsteht eine Verbindlichkeit.
                # Die Anzahl der Aktien wird negativ.
                available_cash = self.portfolio_history['cash'].iloc[i-1] if i > 0 else self.initial_capital # Nicht direkt relevant für Shorting-Größe hier

                num_shares_to_short = 0
                if shares_per_trade:
                    num_shares_to_short = shares_per_trade
                elif capital_per_trade_pct:
                    # Bei Shorting ist "Kapital pro Trade" weniger direkt, da wir Geld erhalten.
                    # Wir könnten es als "Risiko" interpretieren oder eine feste Anzahl annehmen.
                    # Hier verwenden wir es, um eine "nominale" Größe zu bestimmen.
                    nominal_value_to_short = (self.portfolio_history['total_value'].iloc[i-1] if i > 0 else self.initial_capital) * capital_per_trade_pct
                    num_shares_to_short = int(nominal_value_to_short / self._apply_slippage(current_price, -1))

                if num_shares_to_short > 0 : # (Keine direkte Cash-Prüfung für Short-Eröffnung hier)
                    sell_price_short = self._apply_slippage(current_price, -1)
                    proceeds = num_shares_to_short * sell_price_short - self.commission_per_trade
                    self.portfolio_history.loc[timestamp, 'cash'] += proceeds
                    self.portfolio_history.loc[timestamp, 'shares'] -= num_shares_to_short # Negative Aktienanzahl
                    self.portfolio_history.loc[timestamp, 'positions'] = -1
                    current_position = -1
                    trades.append({'timestamp': timestamp, 'type': 'Short Sell', 'price': sell_price_short,
                                   'shares': num_shares_to_short, 'cost': -proceeds})


            # Wenn das Signal NEUTRAL (0) ist und wir eine Position halten
            elif signal == 0 and current_position != 0:
                if current_position == 1: # Long-Position schließen
                    sell_price = self._apply_slippage(current_price, -1)
                    cash_change = self.portfolio_history['shares'].iloc[i-1] * sell_price
                    self.portfolio_history.loc[timestamp, 'cash'] += cash_change - self.commission_per_trade
                    trades.append({'timestamp': timestamp, 'type': 'Sell', 'price': sell_price,
                                   'shares': self.portfolio_history['shares'].iloc[i-1], 'cost': -cash_change + self.commission_per_trade})
                elif current_position == -1: # Short-Position schließen (Rückkauf)
                    buy_price = self._apply_slippage(current_price, 1)
                    cash_change = self.portfolio_history['shares'].iloc[i-1] * buy_price # shares ist negativ
                    self.portfolio_history.loc[timestamp, 'cash'] += cash_change - self.commission_per_trade # cash_change ist negativ
                    trades.append({'timestamp': timestamp, 'type': 'Cover Short', 'price': buy_price,
                                   'shares': -self.portfolio_history['shares'].iloc[i-1], 'cost': -cash_change + self.commission_per_trade})

                self.portfolio_history.loc[timestamp, 'shares'] = 0
                self.portfolio_history.loc[timestamp, 'positions'] = 0
                current_position = 0

            # Update des Portfolio-Werts
            current_holdings_value = self.portfolio_history['shares'].iloc[i] * current_price
            self.portfolio_history.loc[timestamp, 'holdings'] = current_holdings_value
            self.portfolio_history.loc[timestamp, 'total_value'] = self.portfolio_history['cash'].iloc[i] + current_holdings_value

        self.results = pd.DataFrame(trades)

    def calculate_performance_metrics(self) -> dict:
        """
        Berechnet verschiedene Performance-Metriken für den Backtest.

        Returns:
            dict: Ein Dictionary mit den berechneten Metriken:
                - total_return_pct (float): Gesamtrendite in Prozent.
                - annualized_return_pct (float): Annualisierte Rendite in Prozent.
                - sharpe_ratio (float): Sharpe Ratio (risikoadjustierte Rendite, rf-rate=0 angenommen).
                - max_drawdown_pct (float): Maximaler Drawdown des Portfolios in Prozent.
                - win_rate_pct (float): Prozentsatz der gewinnenden Trades von allen abgeschlossenen Trades.
                - profit_factor (float): Verhältnis von Bruttogewinn zu Bruttoverlust.
                - total_trades (int): Gesamtzahl der abgeschlossenen Trades.
                - average_trade_duration_days (float): Durchschnittliche Haltedauer eines Trades in Tagen.
        """
        if self.portfolio_history is None or self.portfolio_history.empty:
            raise ValueError("Backtest muss zuerst ausgeführt werden ('run_backtest').")
        if self.results is None or self.results.empty:
            return { # Keine Trades, also viele Metriken sind 0 oder nicht anwendbar
                "total_return_pct": 0.0,
                "annualized_return_pct": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown_pct": 0.0, # Keine Trades -> kein Drawdown vom Trading
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "total_trades": 0,
                "average_trade_duration": pd.Timedelta(0)
            }

        # Gesamtrendite
        final_value = self.portfolio_history['total_value'].iloc[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital
        total_return_pct = total_return * 100

        # Annualisierte Rendite
        duration_years = (self.portfolio_history.index[-1] - self.portfolio_history.index[0]).days / 365.25
        if duration_years == 0: duration_years = 1 # Vermeide Division durch Null, wenn Dauer < 1 Tag
        annualized_return = ((1 + total_return)**(1/duration_years) - 1) if duration_years > 0 else 0
        annualized_return_pct = annualized_return * 100

        # Tägliche Renditen für Sharpe Ratio und Max Drawdown
        daily_returns = self.portfolio_history['total_value'].pct_change().dropna()

        # Sharpe Ratio (angenommener risikofreier Zinssatz von 0)
        # Es gibt 252 Handelstage in einem typischen Jahr
        sharpe_ratio = 0
        if daily_returns.std() != 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if not daily_returns.empty else 0.0


        # Max Drawdown
        cumulative_returns = (1 + daily_returns).cumprod()
        peak = cumulative_returns.cummax()
        drawdown = (cumulative_returns - peak) / peak
        max_drawdown_pct = abs(drawdown.min() * 100) if not drawdown.empty else 0.0

        # Metriken basierend auf Trades
        num_trades = len(self.results) // 2 # Jeder Trade hat Kauf und Verkauf (oder Short und Cover)

        profits = []
        trade_durations = []
        last_entry_price = 0
        last_entry_timestamp = None
        last_entry_shares = 0

        # Einfache Logik zur Profitberechnung für Long/Short Trades
        # Diese Logik muss eventuell verfeinert werden, je nachdem wie Trades in `self.results` gespeichert sind.
        # Hier wird angenommen, dass Trades paarweise (Entry/Exit) auftreten.
        # Eine robustere Lösung würde Trades explizit als Objekte mit Entry/Exit verwalten.

        # Vereinfachte Profitberechnung:
        # Wir betrachten die Veränderung des 'total_value' zwischen den Trades,
        # oder aggregieren Gewinne/Verluste aus der 'cost'-Spalte der Trades.
        # Für eine genauere Win-Rate und Profit-Faktor müssen wir abgeschlossene Trades betrachten.

        # Hier eine vereinfachte Logik basierend auf der 'cost' Spalte in self.results
        # 'cost' ist positiv für Käufe (Geldabfluss) und negativ für Verkäufe (Geldzufluss)
        # Ein positiver Trade (Gewinn) hat also einen negativen Gesamt-Cost (mehr Zufluss als Abfluss)

        # Diese Logik ist noch nicht perfekt für Win-Rate und Profit-Faktor, da sie nicht explizit Trades paart.
        # Für eine präzisere Berechnung müssten Entry- und Exit-Trades gematcht werden.
        # Fürs Erste: Annahme, dass `self.results` die Kosten/Erlöse korrekt erfasst.

        total_profit = 0
        winning_trades = 0
        losing_trades = 0
        total_gains = 0
        total_losses = 0

        closed_trades_profits = []
        trade_durations = []

        current_long_trade = None
        current_short_trade = None

        # Iterate through the recorded trades to pair entries and exits
        for _, row in self.results.iterrows():
            if row['type'] == 'Buy':
                # This assumes any previous short is covered by strategy logic before a buy.
                # If a long trade is already open, this logic would overwrite it.
                # For simplicity, we assume the strategy generates clean entry signals.
                current_long_trade = {
                    'price': row['price'],
                    'shares': row['shares'],
                    'timestamp': row['timestamp'],
                    'commission': self.commission_per_trade # Commission for entry
                }
            elif row['type'] == 'Short Sell':
                current_short_trade = {
                    'price': row['price'],
                    'shares': row['shares'],
                    'timestamp': row['timestamp'],
                    'commission': self.commission_per_trade # Commission for entry
                }
            elif row['type'] == 'Sell': # Closing a long position
                if current_long_trade and current_long_trade['shares'] == row['shares']: # Ensure selling same amount as bought
                    profit = (row['price'] - current_long_trade['price']) * current_long_trade['shares'] \
                             - current_long_trade['commission'] \
                             - self.commission_per_trade # Commission for exit
                    closed_trades_profits.append(profit)
                    trade_durations.append(row['timestamp'] - current_long_trade['timestamp'])
                    current_long_trade = None # Trade closed
            elif row['type'] == 'Cover Short': # Closing a short position
                if current_short_trade and current_short_trade['shares'] == row['shares']: # Ensure covering same amount as shorted
                    profit = (current_short_trade['price'] - row['price']) * current_short_trade['shares'] \
                             - current_short_trade['commission'] \
                             - self.commission_per_trade # Commission for exit
                    closed_trades_profits.append(profit)
                    trade_durations.append(row['timestamp'] - current_short_trade['timestamp'])
                    current_short_trade = None # Trade closed

        if closed_trades_profits:
            winning_trades = sum(1 for p in closed_trades_profits if p > 0)
            losing_trades = sum(1 for p in closed_trades_profits if p < 0)
            total_gains = sum(p for p in closed_trades_profits if p > 0)
            total_losses = abs(sum(p for p in closed_trades_profits if p < 0)) # Verluste als positiver Wert

        num_closed_trades = len(closed_trades_profits)
        win_rate_pct = (winning_trades / num_closed_trades * 100) if num_closed_trades > 0 else 0
        profit_factor = (total_gains / total_losses) if total_losses > 0 else float('inf') if total_gains > 0 else 0

        avg_trade_duration = pd.Series(trade_durations).mean() if trade_durations else pd.Timedelta(0)


        return {
            "total_return_pct": round(total_return_pct, 2),
            "annualized_return_pct": round(annualized_return_pct, 2),
            "sharpe_ratio": round(sharpe_ratio, 3) if sharpe_ratio != float('inf') and sharpe_ratio != float('-inf') else 'N/A',
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "win_rate_pct": round(win_rate_pct, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else 'inf',
            "total_trades": num_closed_trades,
            "average_trade_duration_days": round(avg_trade_duration.total_seconds() / (24*3600), 2) if pd.notnull(avg_trade_duration) else 0
        }

    def plot_results(self, plot_signals: bool = True):
        """
        Plottet die Ergebnisse des Backtests: Portfolio-Wert und ggf. Handelssignale.

        Args:
            plot_signals (bool): Ob die Handelssignale (Kauf/Verkaufspunkte) im Chart angezeigt werden sollen.
        """
        if self.portfolio_history is None or self.portfolio_history.empty:
            print("Keine Ergebnisse zum Plotten vorhanden. Führen Sie zuerst run_backtest().")
            return

        fig, ax1 = plt.subplots(figsize=(14, 7), dpi=100)

        # Portfolio-Wert
        ax1.plot(self.portfolio_history.index, self.portfolio_history['total_value'], label='Portfolio Value', color='blue', lw=2)
        ax1.set_xlabel('Datum')
        ax1.set_ylabel('Portfolio Wert (€)', color='blue')
        ax1.tick_params(axis='y', labelcolor='blue')
        ax1.set_title(f'Backtest Ergebnisse: {self.strategy.__class__.__name__}')
        ax1.grid(True, linestyle='--', alpha=0.7)

        # Preisdaten auf einer zweiten Y-Achse (optional, aber oft nützlich)
        ax2 = ax1.twinx()
        ax2.plot(self.data.index, self.data['Close'], label='Close Preis', color='grey', alpha=0.6, lw=1)
        ax2.set_ylabel('Aktienkurs (€)', color='grey')
        ax2.tick_params(axis='y', labelcolor='grey')

        if plot_signals and self.results is not None and not self.results.empty:
            buys = self.results[self.results['type'] == 'Buy']
            sells = self.results[self.results['type'] == 'Sell']
            short_sells = self.results[self.results['type'] == 'Short Sell']
            cover_shorts = self.results[self.results['type'] == 'Cover Short']

            if not buys.empty:
                ax2.plot(buys['timestamp'], buys['price'], '^', markersize=8, color='green', lw=0, label='Kauf')
            if not sells.empty:
                ax2.plot(sells['timestamp'], sells['price'], 'v', markersize=8, color='red', lw=0, label='Verkauf')
            if not short_sells.empty:
                ax2.plot(short_sells['timestamp'], short_sells['price'], 'v', markersize=8, color='orange', lw=0, label='Short')
            if not cover_shorts.empty:
                ax2.plot(cover_shorts['timestamp'], cover_shorts['price'], '^', markersize=8, color='purple', lw=0, label='Cover')

        # Legenden kombinieren
        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc='upper left')

        fig.tight_layout()
        plt.show()

# --- Beispiel für die Verwendung ---
if __name__ == "__main__":
    # Temporäre Anpassung für direkten Skriptaufruf
    import sys
    import os
    # Füge das Elternverzeichnis zum Python-Pfad hinzu, um relative Importe zu ermöglichen
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    from finance_tool.data_fetcher import fetch_data
    from finance_tool.strategies import MovingAverageCrossoverStrategy, RSIStrategy, setup_strategy

    # 1. Daten abrufen
    # ticker = "AAPL" # Apple
    ticker = "MSFT" # Microsoft, um andere Daten zu haben
    start_date = "2022-01-01"
    end_date = "2023-12-31"
    price_data = fetch_data(ticker, start_date, end_date)

    if price_data is None or price_data.empty:
        print(f"Keine Daten für {ticker} abrufbar. Beispiel wird beendet.")
        exit()

    print(f"\n--- Backtest für MA Crossover Strategie auf {ticker} ---")
    ma_params = {'short_window': 20, 'long_window': 50}
    # ma_strategy = MovingAverageCrossoverStrategy(price_data.copy(), ma_params)
    ma_strategy = setup_strategy("MA_Crossover", price_data.copy(), ma_params)


    if ma_strategy:
        backtester_ma = Backtester(ma_strategy, initial_capital=10000, commission_per_trade=5, slippage_pct=0.001)
        # backtester_ma.run_backtest(shares_per_trade=10)
        backtester_ma.run_backtest(capital_per_trade_pct=0.5) # 50% des Kapitals pro Trade

        print("\nPortfolio Zeitverlauf (MA Crossover, letzte 5 Tage):")
        print(backtester_ma.portfolio_history.tail())

        print("\nTrades (MA Crossover, erste 5):")
        if backtester_ma.results is not None and not backtester_ma.results.empty:
            print(backtester_ma.results.head())
        else:
            print("Keine Trades ausgeführt.")

        ma_metrics = backtester_ma.calculate_performance_metrics()
        print("\nPerformance Metriken (MA Crossover):")
        for metric, value in ma_metrics.items():
            print(f"  {metric.replace('_', ' ').capitalize()}: {value}")

        backtester_ma.plot_results()

    print(f"\n--- Backtest für RSI Strategie auf {ticker} ---")
    rsi_params = {'rsi_window': 14, 'rsi_oversold': 30, 'rsi_overbought': 70}
    # rsi_strategy = RSIStrategy(price_data.copy(), rsi_params)
    rsi_strategy = setup_strategy("RSI", price_data.copy(), rsi_params)

    if rsi_strategy:
        backtester_rsi = Backtester(rsi_strategy, initial_capital=10000, commission_per_trade=1, slippage_pct=0.0005)
        # backtester_rsi.run_backtest(shares_per_trade=5)
        backtester_rsi.run_backtest(capital_per_trade_pct=0.9) # 90% des Kapitals pro Trade

        print("\nPortfolio Zeitverlauf (RSI, letzte 5 Tage):")
        print(backtester_rsi.portfolio_history.tail())

        print("\nTrades (RSI, erste 5):")
        if backtester_rsi.results is not None and not backtester_rsi.results.empty:
            print(backtester_rsi.results.head())
        else:
            print("Keine Trades ausgeführt.")


        rsi_metrics = backtester_rsi.calculate_performance_metrics()
        print("\nPerformance Metriken (RSI):")
        for metric, value in rsi_metrics.items():
            print(f"  {metric.replace('_', ' ').capitalize()}: {value}")

        backtester_rsi.plot_results()

    print("\n--- Testfall: Keine Trades ---")
    # Erzeuge eine Strategie, die wahrscheinlich keine Signale generiert (z.B. sehr lange Fenster)
    no_trade_params = {'short_window': 200, 'long_window': 250} # Lange Fenster, weniger Crossovers
    no_trade_strategy = MovingAverageCrossoverStrategy(price_data.copy(), no_trade_params)
    backtester_no_trades = Backtester(no_trade_strategy, initial_capital=10000)
    backtester_no_trades.run_backtest(shares_per_trade=10)
    no_trades_metrics = backtester_no_trades.calculate_performance_metrics()
    print("Performance Metriken (No Trades):")
    for metric, value in no_trades_metrics.items():
            print(f"  {metric.replace('_', ' ').capitalize()}: {value}")
    # backtester_no_trades.plot_results() # Sollte zeigen, dass sich der Wert nicht ändert

    print("\n--- Testfall: Nur Shorting (hypothetisch, RSI-Signal umkehren) ---")
    class AlwaysShortRSIStrategy(RSIStrategy): # Beispiel für eine Strategie, die eher short geht
        def generate_signals(self) -> pd.DataFrame:
            signals_df = super().generate_signals()
            # Kehre die Signale um: Long wird Short, Short wird Long (vereinfacht)
            signals_df['signal'] = signals_df['signal'] * -1
            return signals_df

    short_rsi_strategy = AlwaysShortRSIStrategy(price_data.copy(), rsi_params)
    backtester_short_rsi = Backtester(short_rsi_strategy, initial_capital=10000, commission_per_trade=2)
    backtester_short_rsi.run_backtest(shares_per_trade=10) # Feste Anzahl Aktien für Shorting

    print("\nTrades (Always Short RSI, erste 5):")
    if backtester_short_rsi.results is not None and not backtester_short_rsi.results.empty:
        print(backtester_short_rsi.results.head())
    else:
        print("Keine Trades ausgeführt.")

    short_rsi_metrics = backtester_short_rsi.calculate_performance_metrics()
    print("\nPerformance Metriken (Always Short RSI):")
    for metric, value in short_rsi_metrics.items():
            print(f"  {metric.replace('_', ' ').capitalize()}: {value}")
    backtester_short_rsi.plot_results()
